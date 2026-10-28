"""Authenticated surface map. The crawl runs on the attack box, never from Layla itself."""
from __future__ import annotations

import json
import re
from urllib.parse import urlsplit

ROLES = ("anon", "user", "other")
_URL = re.compile(r"^https?://[A-Za-z0-9._:-]+(?:/[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]*)?$")
_PATH = re.compile(r"^[A-Za-z0-9_./-]{0,300}$")

_CRAWL = r'''
import json, re, ssl
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

class Links(HTMLParser):
    def __init__(self):
        super().__init__(); self.hrefs=[]; self.scripts=[]; self.fields=[]; self.posts=[]
    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag == "a" and d.get("href"):
            self.hrefs.append(d["href"])
        if tag == "form":
            action = d.get("action") or ""
            if action:
                self.hrefs.append(action)
                if (d.get("method") or "get").lower() == "post":
                    self.posts.append(action)
        if tag == "script" and d.get("src"):
            self.scripts.append(d["src"])
        if tag in ("input", "textarea", "select") and d.get("name"):
            self.fields.append(d["name"][:40])

def jar_header(path):
    if not path: return ""
    pairs = []
    try:
        for line in open(path, encoding="utf-8", errors="replace"):
            if not line.strip() or line.startswith("#"): continue
            parts = line.split("\t")
            if len(parts) >= 7: pairs.append(parts[5] + "=" + parts[6].strip())
    except OSError:
        return ""
    return "; ".join(pairs)

def fetch(url, cookie):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Upgrade-Insecure-Requests": "1",
    }
    if cookie: headers["Cookie"] = cookie
    try:
        with urlopen(Request(url, headers=headers), timeout=12) as res:
            return res.status, res.headers.get_content_type(), res.read(180000).decode("utf-8", "replace"), res.geturl()
    except Exception as exc:
        return getattr(exc, "code", 0) or 0, "", "", url

ROUTE = re.compile(r"""["'](/(?:[A-Za-z0-9][A-Za-z0-9_./-]{0,100}))["']""")
host = urlsplit(START).hostname
cookie = jar_header(JAR)
queue, seen, rows, scripts = [(START, 0)], set(), [], 8
while queue and len(seen) < 60:
    url, depth = queue.pop(0)
    url = url.split("#")[0]
    if url in seen or urlsplit(url).hostname != host or depth > 3: continue
    seen.add(url)
    status, ctype, text, final = fetch(url, cookie)
    path = urlsplit(final).path or "/"
    params = [part[:40] for part in urlsplit(final).query.split("&") if part][:8]
    row = {"path": path[:180], "status": status, "role": ROLE}
    if params: row["params"] = params
    if "html" not in ctype:
        rows.append(row)
        continue
    parser = Links(); parser.feed(text)
    if parser.fields:
        row["fields"] = parser.fields[:12]
    rows.append(row)
    for action in parser.posts:
        posted = urljoin(final, action).split("#")[0]
        if urlsplit(posted).hostname != host: continue
        rows.append({"path": (urlsplit(posted).path or "/")[:180], "status": None, "role": ROLE, "method": "POST", "fields": parser.fields[:12]})
    if depth >= 3: continue
    for href in parser.hrefs:
        nxt = urljoin(final, href).split("#")[0]
        if urlsplit(nxt).hostname == host and nxt not in seen: queue.append((nxt, depth + 1))
    for src in parser.scripts:
        if scripts <= 0: break
        js_url = urljoin(final, src)
        if urlsplit(js_url).hostname != host: continue
        scripts -= 1
        _, _, js, _ = fetch(js_url, "")
        for match in ROUTE.findall(js):
            if match.startswith("//"): continue
            rows.append({"path": match[:180], "status": None, "role": ROLE, "from": "js"})
print("LAYLA_SURFACE " + json.dumps(rows[:120], ensure_ascii=False))
'''

_COMPARE = r'''
import hashlib, json, ssl
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

def jar_header(path):
    if not path: return ""
    pairs = []
    try:
        for line in open(path, encoding="utf-8", errors="replace"):
            if not line.strip() or line.startswith("#"): continue
            parts = line.split("\t")
            if len(parts) >= 7: pairs.append(parts[5] + "=" + parts[6].strip())
    except OSError:
        return ""
    return "; ".join(pairs)

def read_of(url, cookie):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "*/*", "Accept-Language": "en-US,en;q=0.9",
    }
    if cookie: headers["Cookie"] = cookie
    try:
        with urlopen(Request(url, headers=headers), timeout=12) as res:
            body = res.read(8000)
            return res.status, hashlib.sha256(body).hexdigest()[:16], body.decode("utf-8", "replace")
    except Exception as exc:
        code = getattr(exc, "code", 0) or 0
        raw = b""
        if hasattr(exc, "read"):
            try: raw = exc.read(8000)
            except Exception: raw = b""
        return code, hashlib.sha256(raw).hexdigest()[:16] if raw else "", raw.decode("utf-8", "replace")

user, other = jar_header(USER_JAR), jar_header(OTHER_JAR)
rows = []
for path in PATHS[:80]:
    url = urljoin(BASE, path)
    if urlsplit(url).hostname != urlsplit(BASE).hostname: continue
    anon_s, anon_h, anon_b = read_of(url, "")
    user_s, user_h, user_b = read_of(url, user)
    other_s, other_h, other_b = read_of(url, other)
    leak = bool(USER_MARK and USER_MARK in other_b) or bool(OTHER_MARK and OTHER_MARK in user_b)
    row = {"path": path, "anon": anon_s, "user": user_s, "other": other_s, "hash": {"anon": anon_h, "user": user_h, "other": other_h}}
    if leak: row["leak"] = True
    rows.append(row)
print("LAYLA_SURFACE " + json.dumps(rows, ensure_ascii=False))
'''


_MARK = re.compile(r"^[A-Za-z0-9_.:-]{4,80}$")


def marker(value: str) -> str:
    text = (value or "").strip()
    if text and not _MARK.fullmatch(text):
        raise ValueError("Маркер: 4–80 символов, буквы, цифры, точка, двоеточие, _ и -")
    return text


def paths_from(content: str) -> tuple[list[str], str, str, str, str]:
    text = content.strip()
    if text.startswith("{"):
        spec = json.loads(text)
        if not isinstance(spec, dict):
            raise ValueError("compare_roles ждёт JSON со списком paths")
        paths = spec.get("paths") or []
        if not isinstance(paths, list):
            raise ValueError("paths должен быть списком")
        return (
            [str(item) for item in paths],
            str(spec.get("user_jar") or ""),
            str(spec.get("other_jar") or ""),
            marker(str(spec.get("user_marker") or "")),
            marker(str(spec.get("other_marker") or "")),
        )
    return [line.strip() for line in text.splitlines() if line.strip()], "", "", "", ""


def origin(target: str) -> str:
    raw = target.strip()
    parsed = urlsplit(raw if "://" in raw else "https://" + raw)
    if not parsed.hostname or (parsed.scheme and parsed.scheme not in ("http", "https")):
        raise ValueError("Нужен адрес цели")
    scheme = parsed.scheme or "https"
    port = f":{parsed.port}" if parsed.port else ""
    return f"{scheme}://{parsed.hostname}{port}/"


def host_of(value: str) -> str:
    return urlsplit(origin(value)).hostname or ""


def page_url(target: str, url: str) -> str:
    host = host_of(target)
    full = url.strip() or f"https://{host}/"
    if not _URL.match(full) or urlsplit(full).hostname != host:
        raise ValueError("Стартовая страница должна быть http(s) на этой же цели")
    return full


def jar_path(path: str) -> str:
    if path and not _PATH.match(path):
        raise ValueError("Путь к cookie jar может содержать только буквы, цифры, точку, слэш, _ и -")
    return path


def command(source: str) -> str:
    return "python3 - << 'PY'\n" + source + "\nPY\n"


def crawl_command(target: str, url: str, jar: str, role: str) -> str:
    if role not in ROLES:
        raise ValueError("Роль: anon, user или other")
    prelude = f"START={json.dumps(page_url(target, url))}\nJAR={json.dumps(jar_path(jar))}\nROLE={json.dumps(role)}\n"
    return command(prelude + _CRAWL)


def compare_command(target: str, paths: list[str], user_jar: str, other_jar: str, user_marker: str = "", other_marker: str = "") -> str:
    host = host_of(target)
    clean = []
    for path in paths:
        item = path.strip()
        if not item.startswith("/") or item.startswith("//") or ".." in item or not _PATH.match(item):
            raise ValueError("Путь для сравнения должен начинаться с /")
        clean.append(item[:180])
    if not clean:
        raise ValueError("compare_roles требует хотя бы один путь")
    prelude = (
        f"BASE={json.dumps(origin(target))}\n"
        f"PATHS={json.dumps(clean[:80])}\n"
        f"USER_JAR={json.dumps(jar_path(user_jar))}\n"
        f"OTHER_JAR={json.dumps(jar_path(other_jar))}\n"
        f"USER_MARK={json.dumps(marker(user_marker))}\n"
        f"OTHER_MARK={json.dumps(marker(other_marker))}\n"
    )
    return command(prelude + _COMPARE)


def parse_report(output: str) -> list[dict]:
    for line in output.splitlines():
        if line.startswith("LAYLA_SURFACE "):
            data = json.loads(line.removeprefix("LAYLA_SURFACE "))
            return data if isinstance(data, list) else []
    return []


def verdict(path: str, anon, user, other, *, leak: bool = False, same_body=None) -> str:
    """What the three replies mean. A candidate is not a confirmed finding."""
    if leak:
        return "idor-candidate"
    if any(code == 0 for code in (anon, user, other) if isinstance(code, int)):
        return "blocked"
    private = {401, 403, 404}
    has_id = bool(re.search(r"/(\d+|[0-9a-fA-F-]{8,})(?:/|$)", path))
    if user == 200 and other == 200 and anon in private and has_id:
        return "idor-candidate"
    if user == 200 and other in private:
        return "separated"
    if user == 200 and anon in private:
        return "auth-only"
    present = [code for code in (anon, user, other) if isinstance(code, int)]
    if len(present) >= 2 and len(set(present)) == 1:
        if same_body is False:
            return "differs"
        return "same"
    return "found"


def _same_body(item: dict):
    hashes = item.get("hash") if isinstance(item.get("hash"), dict) else {}
    if hashes.get("user") and hashes.get("other"):
        return hashes["user"] == hashes["other"]
    return None


def absorb(rows: list[dict]) -> list[dict]:
    grouped: dict[str, dict] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        path = str(row.get("path") or "/")[:180]
        if not path.startswith("/"):
            path = "/" + path
        item = grouped.setdefault(path, {"path": path, "surface": True})
        if "status" not in row and any(name in row for name in ROLES):
            for name in ROLES:
                if isinstance(row.get(name), int):
                    item[name] = row[name]
            if isinstance(row.get("hash"), dict):
                item["hash"] = {name: str(row["hash"].get(name) or "")[:16] for name in ROLES}
            if row.get("leak"):
                item["leak"] = True
        else:
            role = row.get("role")
            if role in ROLES and isinstance(row.get("status"), int):
                item[role] = row["status"]
            if row.get("from") == "js":
                item["from"] = "js"
            for key in ("fields", "params"):
                if isinstance(row.get(key), list) and row[key]:
                    item[key] = [str(part)[:40] for part in row[key][:12]]
            if str(row.get("method") or "").upper() == "POST":
                item["method"] = "POST"
        item["verdict"] = verdict(path, item.get("anon"), item.get("user"), item.get("other"), leak=bool(item.get("leak")), same_body=_same_body(item))
    return list(grouped.values())
