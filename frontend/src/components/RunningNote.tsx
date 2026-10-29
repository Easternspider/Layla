"use client";

import { useEffect, useState } from "react";

function stamp(value: string) {
  return new Date(/(Z|[+-]\d{2}:\d{2})$/i.test(value) ? value : `${value}Z`).getTime();
}

/** Сколько уже идёт долгий шаг. До минуты молчит, чтобы не мигать на обычных командах. */
export function RunningNote({ start, ceiling }: { start?: string | null; ceiling?: number }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!start) return;
    const id = window.setInterval(() => setNow(Date.now()), 15000);
    return () => window.clearInterval(id);
  }, [start]);
  if (!start) return null;
  const began = stamp(start);
  if (Number.isNaN(began)) return null;
  const elapsed = now - began;
  if (elapsed < 60_000) return null;
  const minutes = Math.floor(elapsed / 60_000);
  const cap = ceiling && ceiling > 0 ? ` из ${Math.max(1, Math.round(ceiling / 60))}` : "";
  return <span className="text-[11px] text-amber-200">идёт {minutes} мин{cap}</span>;
}
