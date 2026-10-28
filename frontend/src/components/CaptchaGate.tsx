"use client";

import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

type Challenge = { id: string; url: string; host: string; mode: "browser" | "external" };

const apiBase = process.env.NEXT_PUBLIC_API_BASE || "/api";

export function CaptchaGate() {
  const [tick, setTick] = useState(0);
  const [text, setText] = useState("");
  const [note, setNote] = useState("");
  const challenges = useQuery({
    queryKey: ["research-challenges"],
    queryFn: () => api.get<Challenge[]>("/research/challenges"),
    refetchInterval: 2000,
  });
  const pending = challenges.data || [];
  useEffect(() => {
    if (!pending.length) return;
    const timer = window.setInterval(() => setTick(value => value + 1), 1500);
    return () => window.clearInterval(timer);
  }, [pending.length]);
  if (!pending.length) return null;
  return <div className="mx-4 mb-3 space-y-3">
    {pending.map(item => <section key={item.id} className="rounded-2xl bg-[#1c1c1e] p-3">
      <p className="text-sm font-semibold">Сайт просит проверку</p>
      <p className="mt-1 text-xs text-neutral-400">{item.host}. Решите её здесь, агент подождёт и продолжит чтение.</p>
      {item.mode === "browser" ? <>
        <button className="mt-3 block w-full overflow-hidden rounded-xl bg-black" onClick={async event => {
          const rect = event.currentTarget.getBoundingClientRect();
          const click = event.nativeEvent;
          await api.post(`/research/challenges/${item.id}/click`, {
            x: ((click.clientX - rect.left) / rect.width) * 1100,
            y: ((click.clientY - rect.top) / rect.height) * 780,
          });
          setTick(value => value + 1);
        }}>
          <img alt="Проверка сайта" src={`${apiBase}/research/challenges/${item.id}/shot?t=${tick}`} className="max-h-96 w-full object-contain" />
        </button>
        <form className="mt-2 flex gap-2" onSubmit={async event => {
          event.preventDefault();
          if (!text.trim()) return;
          await api.post(`/research/challenges/${item.id}/type`, { text });
          setText("");
          setTick(value => value + 1);
        }}>
          <input value={text} onChange={e => setText(e.target.value)} aria-label="Текст для проверки" placeholder="Текст, если его просят ввести" className="min-w-0 flex-1 rounded-xl bg-[#2c2c2e] px-3 py-2 text-sm" />
          <button className="secondary-button !min-h-0 px-3 py-2 text-xs" type="submit">Ввести</button>
        </form>
      </> : <button className="secondary-button mt-3 text-xs" onClick={() => window.open(item.url, "_blank", "noopener")}>Открыть проверку</button>}
      <div className="mt-3 flex gap-2">
        <button className="primary-button !min-h-0 px-3 py-2 text-xs" onClick={async () => {
          const result = await api.post<{ ok: boolean }>(`/research/challenges/${item.id}/finish`);
          setNote(result.ok ? "" : "Страница всё ещё показывает проверку.");
        }}>Готово, читать страницу</button>
        <button className="secondary-button !min-h-0 px-3 py-2 text-xs" onClick={() => api.post(`/research/challenges/${item.id}/skip`)}>Пропустить</button>
      </div>
      {note && <p className="mt-2 text-xs text-neutral-400">{note}</p>}
    </section>)}
  </div>;
}
