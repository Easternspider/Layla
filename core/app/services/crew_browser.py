"""One persistent browser for an Orchestra chat.

The lead opens public HTTPS pages, reads what a person would see, clicks, types
and looks at pictures. Cookies stay in this process until the desk is idle.
Local and private hosts are refused.
"""
from __future__ import annotations

import asyncio
import base64
import ipaddress
import re
import time
from pathlib import Path
from urllib.parse import urlsplit

from app.services import files, provider_client, web_research

_DESKS: dict[str, "Desk"] = {}
_MAX = 3
_IDLE = 1200
_KEYS = {
    "Enter", "Tab", "Escape", "Backspace", "Delete", "Space",
    "ArrowDown", "ArrowUp", "ArrowLeft", "ArrowRight", "Home", "End", "PageDown", "PageUp",
}
_SNAP = """() => {
  const visible = (el) => {
    const r = el.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) return false;
    const style = getComputedStyle(el);
    return style.visibility !== 'hidden' && style.display !== 'none';
  };
  const textOf = (el) => (el.innerText || el.getAttribute('aria-label') || el.getAttribute('placeholder')
    || el.getAttribute('alt') || el.getAttribute('value') || '').replace(/\\s+/g, ' ').trim().slice(0, 140);
  document.querySelectorAll('[data-layla-n]').forEach((el) => el.removeAttribute('data-layla-n'));
  const items = [];
  for (const el of document.querySelectorAll('a, button, input, textarea, select, img, [role="button"], [role="link"]')) {
    if (!visible(el)) continue;
    const n = items.length + 1;
    el.setAttribute('data-layla-n', String(n));
    items.push({
      n,
      tag: el.tagName.toLowerCase(),
      type: el.getAttribute('type') || '',
      name: el.getAttribute('name') || '',
      text: textOf(el),
      href: (el.href || '').slice(0, 300),
      alt: (el.getAttribute('alt') || '').slice(0, 160),
    });
    if (items.length >= 60) break;
  }
  return {
    url: location.href,
    title: document.title || '',
    text: (document.body && document.body.innerText || '').replace(/\\n{3,}/g, '\\n\\n').slice(0, 6000),
    items,
  };
}"""
_REF = re.compile(r"^(?:n:|ref:)?(\d+)$")
_NTH = re.compile(r"^([a-zA-Z][\w-]*)(?::nth-of-type|:nth-child)\((\d+)\)$")
_CAPTCHA_CLICK = re.compile(r"^(click|клик|checkbox)\b", re.I)
_CAPTCHA_TILES = re.compile(r"(?:tiles|клетки|номера)\s*[:\-]?\s*([0-9,\s]+)", re.I)
_MISS = "Элемент не найден. Укажи номер n из items, например 3, или видимый текст. Не выдумывай css:a:nth-of-type."


def interpret_captcha(answer: str) -> dict:
    """Turn a vision reply into a click, tile clicks, or the characters to type."""
    text = (answer or "").strip()
    if not text:
        return {"kind": "unknown"}
    if _CAPTCHA_CLICK.match(text) or text.upper() == "CLICK":
        return {"kind": "click"}
    tiles = _CAPTCHA_TILES.search(text)
    if tiles:
        numbers = [int(item) for item in re.findall(r"\d+", tiles.group(1))]
        numbers = [item for item in numbers if 1 <= item <= 16][:9]
        if numbers:
            return {"kind": "tiles", "tiles": numbers}
    line = text.splitlines()[0].strip().strip("\"'`[]")
    line = re.sub(r"^(ответ|answer|text|код)\s*[:\-]\s*", "", line, flags=re.I).strip()
    if 1 <= len(line) <= 16 and " " not in line:
        return {"kind": "type", "text": line}
    return {"kind": "unknown", "text": text[:200]}


def ref_number(target: str) -> int | None:
    match = _REF.fullmatch((target or "").strip())
    return int(match.group(1)) if match else None


def nth_hint(target: str) -> tuple[str, int] | None:
    raw = (target or "").strip().removeprefix("css:").strip()
    match = _NTH.fullmatch(raw)
    if not match:
        return None
    return match.group(1).lower(), int(match.group(2))


def private_host(host: str | None) -> bool:
    if not host:
        return True
    name = host.lower().rstrip(".")
    if name in {"localhost"} or name.endswith(".local") or name.endswith(".internal") or name.endswith(".localhost"):
        return True
    try:
        address = ipaddress.ip_address(name)
    except ValueError:
        return False
    return not address.is_global or address.is_multicast


def check_navigation(url: str) -> str:
    _target, host = web_research.validate_url(url)
    if private_host(host):
        raise ValueError("Локальные и служебные адреса недоступны")
    return host


def image_mime(raw: bytes) -> str:
    if raw[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if raw[:6] in {b"GIF87a", b"GIF89a"}:
        return "image/gif"
    if raw[:4] == b"RIFF" and len(raw) >= 12 and raw[8:12] == b"WEBP":
        return "image/webp"
    return ""


async def _describe(provider, key, model: str, raw: bytes, question: str) -> str:
    mime = image_mime(raw)
    if not mime or provider is None or provider_client._is_anthropic_native(provider):
        return ""
    secret = key.current if hasattr(key, "current") else key
    uri = f"data:{mime};base64," + base64.b64encode(raw[:1_500_000]).decode()
    messages = [{"role": "user", "content": [
        {"type": "text", "text": question[:500]},
        {"type": "image_url", "image_url": {"url": uri}},
    ]}]
    try:
        text = await asyncio.wait_for(provider_client.complete(provider, secret, model, messages), 45)
    except Exception:
        return ""
    return (text or "").strip()[:4000]


class Desk:
    def __init__(self, key: str, root: Path):
        self.key = key
        self.root = Path(root)
        self.used = time.monotonic()
        self._lock = asyncio.Lock()
        self._playwright = None
        self._browser = None
        self._page = None
        self._expiry: asyncio.Task | None = None

    def _touch(self) -> None:
        self.used = time.monotonic()
        if self._expiry is not None and not self._expiry.done():
            self._expiry.cancel()
        self._expiry = asyncio.create_task(self._expire())

    async def _expire(self) -> None:
        try:
            await asyncio.sleep(_IDLE)
        except asyncio.CancelledError:
            return
        if time.monotonic() - self.used >= _IDLE:
            await self.close()

    async def close(self) -> None:
        _DESKS.pop(self.key, None)
        browser, playwright = self._browser, self._playwright
        self._page = self._browser = self._playwright = None
        if self._expiry is not None and not self._expiry.done():
            self._expiry.cancel()
        try:
            if browser is not None:
                await browser.close()
        except Exception:
            pass
        try:
            if playwright is not None:
                await playwright.stop()
        except Exception:
            pass

    async def _route(self, route) -> None:
        url = route.request.url
        if url.startswith(("data:", "blob:", "about:")):
            await route.continue_()
            return
        if private_host(urlsplit(url).hostname):
            await route.abort()
            return
        await route.continue_()

    async def _ensure(self):
        if self._page is not None:
            return self._page
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise ValueError("Chromium для браузера не установлен") from exc
        try:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=True, args=["--disable-dev-shm-usage", "--no-sandbox"])
            context = await self._browser.new_context(
                viewport={"width": 1280, "height": 800}, locale="ru-RU", timezone_id="Europe/Moscow")
            self._page = await context.new_page()
            self._page.set_default_timeout(15000)
            await self._page.route("**/*", self._route)
        except Exception as exc:
            await self.close()
            raise ValueError("Браузер не запустился") from exc
        return self._page

    async def _shot(self, page, locator=None) -> tuple[bytes, str]:
        folder = self.root / "crew" / "browser"
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / "latest.jpg"
        if locator is None:
            png = await page.screenshot(type="jpeg", quality=55)
        else:
            png = await locator.screenshot(type="jpeg", quality=55)
        target.write_bytes(png)
        return png, "crew/browser/latest.jpg"

    async def _snapshot(self, page, png: bytes | None = None, seen: str = "") -> dict:
        data = await page.evaluate(_SNAP)
        if not isinstance(data, dict):
            data = {"url": page.url, "title": "", "text": "", "items": []}
        data["shot"] = "crew/browser/latest.jpg"
        if seen:
            data["seen"] = seen
        elif png:
            data["seen"] = ""
        data["text"] = str(data.get("text") or "")[:6000]
        data["items"] = list(data.get("items") or [])[:60]
        return data

    def _css(self, target: str) -> bool:
        return target.startswith(("css:", "#", ".", "[", "/")) or " > " in target

    async def _nth(self, page, tag: str, number: int):
        listed = page.locator(tag)
        total = await listed.count()
        if 1 <= number <= total:
            return listed.nth(number - 1)
        raise ValueError(f"На странице нет {number}-го элемента {tag}. {_MISS}")

    async def _resolve(self, page, target: str, *, field: bool = False):
        number = ref_number(target)
        if number is not None:
            locator = page.locator(f'[data-layla-n="{number}"]')
            if await locator.count() == 0:
                raise ValueError(f"Номера {number} нет на последнем снимке. {_MISS}")
            return locator
        hint = nth_hint(target)
        if hint:
            return await self._nth(page, hint[0], hint[1])
        if self._css(target):
            return page.locator(target.removeprefix("css:")).first
        if not field:
            return page.get_by_text(target, exact=False).first
        locator = page.get_by_label(target).first
        if await locator.count() == 0:
            locator = page.get_by_placeholder(target).first
        if await locator.count() == 0:
            locator = page.get_by_role("textbox", name=target).first
        if await locator.count() == 0:
            locator = page.locator(f"input[name='{target}'], textarea[name='{target}']").first
        return locator

    async def _click(self, locator) -> None:
        try:
            await locator.scroll_into_view_if_needed(timeout=2000)
            await locator.click(timeout=4000)
        except Exception as exc:
            raise ValueError(_MISS + " " + str(exc).split("Call log:", 1)[0].strip()[:160]) from exc

    async def _field(self, page, target: str):
        locator = await self._resolve(page, target, field=True)
        try:
            await locator.wait_for(state="visible", timeout=4000)
        except Exception as exc:
            raise ValueError(_MISS) from exc
        return locator

    async def open(self, url: str) -> dict:
        host = check_navigation(url)
        await web_research.public_addresses(host)
        async with self._lock:
            self._touch()
            page = await self._ensure()
            await page.goto(url, wait_until="domcontentloaded", timeout=25000)
            png, _path = await self._shot(page)
            return await self._snapshot(page, png)

    async def look(self) -> dict:
        async with self._lock:
            self._touch()
            page = await self._ensure()
            png, _path = await self._shot(page)
            return await self._snapshot(page, png)

    async def click(self, target: str) -> dict:
        async with self._lock:
            self._touch()
            page = await self._ensure()
            locator = await self._resolve(page, target)
            await self._click(locator)
            png, _path = await self._shot(page)
            return await self._snapshot(page, png)

    async def captcha(self, provider, key, model: str) -> dict:
        async with self._lock:
            self._touch()
            page = await self._ensure()
            box = await page.evaluate("""() => {
              const nodes = [...document.querySelectorAll('img, canvas, iframe, [class*="captcha" i], [id*="captcha" i]')];
              const hit = nodes.find((el) => {
                const blob = `${el.getAttribute('src') || ''} ${el.getAttribute('alt') || ''} ${el.className || ''} ${el.id || ''}`.toLowerCase();
                return /captcha|капч|recaptcha|hcaptcha|turnstile/.test(blob);
              });
              if (!hit) return null;
              hit.scrollIntoView({ block: 'center', inline: 'center' });
              const r = hit.getBoundingClientRect();
              if (r.width < 8 || r.height < 8) return null;
              return { x: Math.max(0, r.x), y: Math.max(0, r.y), w: Math.min(r.width, 800), h: Math.min(r.height, 600) };
            }""")
            if isinstance(box, dict):
                png = await page.screenshot(type="jpeg", quality=55, clip={
                    "x": box["x"], "y": box["y"], "width": box["w"], "height": box["h"]})
            else:
                png, _path = await self._shot(page)
            question = (
                "Это проверка на странице. Ответь одной строкой и ничем больше. "
                "Если на картинке символы, напиши только их. "
                "Если это галочка «я не робот», напиши CLICK. "
                "Если сетка картинок, напиши TILES: и номера клеток слева направо сверху вниз, которые нужно нажать."
            )
            seen = await _describe(provider, key, model, png, question)
            action = interpret_captcha(seen)
            done = "не разобрана"
            if action["kind"] == "type":
                field = page.locator("input[type='text'], input:not([type]), textarea").first
                if await field.count():
                    await field.fill(action["text"][:16])
                    done = "введено " + action["text"]
                else:
                    done = "прочитано " + action["text"] + ", поля для ввода нет"
            elif action["kind"] == "click":
                if isinstance(box, dict):
                    await page.mouse.click(box["x"] + min(28, box["w"] / 2), box["y"] + box["h"] / 2)
                    done = "нажата галочка"
                else:
                    done = "галочка не найдена"
            elif action["kind"] == "tiles" and isinstance(box, dict):
                cols = 3
                for number in action["tiles"]:
                    row, col = divmod(number - 1, cols)
                    await page.mouse.click(
                        box["x"] + (col + 0.5) * box["w"] / cols,
                        box["y"] + (row + 0.5) * box["h"] / cols)
                done = "нажаты клетки " + ",".join(str(item) for item in action["tiles"])
            elif action["kind"] == "unknown" and not seen:
                done = "модель не разглядела картинку"
            shot = await self._snapshot(page, png, seen)
            shot["captcha"] = done
            return shot

    async def type_text(self, target: str, text: str, submit: bool) -> dict:
        async with self._lock:
            self._touch()
            page = await self._ensure()
            locator = await self._field(page, target)
            await locator.fill(text)
            if submit:
                await locator.press("Enter")
            png, _path = await self._shot(page)
            return await self._snapshot(page, png)

    async def press(self, key: str) -> dict:
        if key not in _KEYS:
            raise ValueError("Клавиша: Enter, Tab, Escape, стрелки, Backspace, Delete, Home, End, PageUp, PageDown, Space")
        async with self._lock:
            self._touch()
            page = await self._ensure()
            await page.keyboard.press(key)
            png, _path = await self._shot(page)
            return await self._snapshot(page, png)

    async def select(self, target: str, value: str) -> dict:
        async with self._lock:
            self._touch()
            page = await self._ensure()
            locator = await self._field(page, target)
            try:
                await locator.select_option(label=value)
            except Exception:
                await locator.select_option(value)
            png, _path = await self._shot(page)
            return await self._snapshot(page, png)

    async def scroll(self, direction: str) -> dict:
        async with self._lock:
            self._touch()
            page = await self._ensure()
            if direction == "top":
                await page.evaluate("window.scrollTo(0, 0)")
            else:
                amount = 700 if direction == "down" else -700
                await page.mouse.wheel(0, amount)
            png, _path = await self._shot(page)
            return await self._snapshot(page, png)

    async def back(self) -> dict:
        async with self._lock:
            self._touch()
            page = await self._ensure()
            await page.go_back(wait_until="domcontentloaded", timeout=15000)
            png, _path = await self._shot(page)
            return await self._snapshot(page, png)

    async def upload(self, target: str, path: str) -> dict:
        local = files.safe_join(self.root, path)
        if not local.is_file():
            raise ValueError("Файл не найден в рабочей папке")
        async with self._lock:
            self._touch()
            page = await self._ensure()
            locator = await self._field(page, target)
            await locator.set_input_files(str(local))
            png, _path = await self._shot(page)
            return await self._snapshot(page, png)

    async def see(self, target: str, provider, key, model: str) -> dict:
        async with self._lock:
            self._touch()
            page = await self._ensure()
            if target.startswith("https://"):
                host = check_navigation(target)
                addresses = await web_research.public_addresses(host)
                status, _content_type, body, _headers = await web_research.perform(target, host, addresses[0], 2_000_000)
                mime = image_mime(body)
                if status != 200 or not mime:
                    raise ValueError("По ссылке нет картинки")
                folder = self.root / "crew" / "browser"
                folder.mkdir(parents=True, exist_ok=True)
                (folder / "picture").write_bytes(body[:2_000_000])
                question = "Опиши изображение подробно: объекты, текст на нём, числа. Не выдумывай того, чего не видно."
                seen = await _describe(provider, key, model, body[:1_500_000], question)
                shot = await self._snapshot(page)
                shot["seen"] = seen or "Модель не описала картинку. Файл сохранён: crew/browser/picture"
                shot["image"] = "crew/browser/picture"
                return shot
            locator = await self._resolve(page, target) if target else None
            png, _path = await self._shot(page, locator)
            question = "Опиши экран как человек: что видно, какие поля и кнопки, есть ли ошибки. Текст цитируй только если он читается."
            seen = await _describe(provider, key, model, png, question)
            return await self._snapshot(page, png, seen)


async def desk_for(key: str, root: Path) -> Desk:
    current = _DESKS.get(key)
    if current is not None:
        return current
    while len(_DESKS) >= _MAX:
        oldest = min(_DESKS.values(), key=lambda item: item.used)
        await oldest.close()
    desk = Desk(key, root)
    _DESKS[key] = desk
    return desk
