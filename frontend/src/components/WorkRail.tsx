"use client";

import { useEffect, type ReactNode } from "react";
import { Link2, Pencil, Pin, Plus, Search, Trash2 } from "lucide-react";

export type WorkRow = {
  id: string;
  title: string;
  subtitle?: string;
  working?: boolean;
  pinned?: boolean;
  alert?: boolean;
};

export function loadPins(key: string) {
  try { return JSON.parse(localStorage.getItem(key) || "[]") as string[]; } catch { return []; }
}

export function useListKeys(ids: string[], current: string | null, select: (id: string) => void, onNew?: () => void) {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const el = event.target as HTMLElement | null;
      if (el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.tagName === "SELECT" || el.isContentEditable)) return;
      if (event.metaKey || event.ctrlKey || event.altKey || document.querySelector("[role=dialog]")) return;
      if (event.key === "n" && onNew) { event.preventDefault(); onNew(); return; }
      if ((event.key !== "j" && event.key !== "k") || !ids.length) return;
      const index = Math.max(0, ids.indexOf(current || ""));
      const next = event.key === "j" ? Math.min(ids.length - 1, index + (current ? 1 : 0)) : Math.max(0, index - 1);
      select(ids[next]);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [ids, current, select, onNew]);
}

export function WorkRail({
  title, query, onQuery, rows, active, onOpen, onPin, onDelete, onRename, onCopy, onCreate, empty, children,
}: {
  title: string;
  query: string;
  onQuery: (value: string) => void;
  rows: WorkRow[];
  active: string | null;
  onOpen: (id: string) => void;
  onPin?: (id: string) => void;
  onDelete?: (id: string) => void;
  onRename?: (id: string) => void;
  onCopy?: (id: string) => void;
  onCreate?: () => void;
  empty?: string;
  children?: ReactNode;
}) {
  return (
    <aside className="flex w-64 shrink-0 flex-col border-r border-white/10 bg-black">
      <div className="flex items-center justify-between border-b border-white/10 px-3 py-2">
        <span className="text-[11px] font-semibold uppercase tracking-wide text-neutral-400">{title}</span>
        {onCreate && <button onClick={onCreate} className="grid h-6 w-6 place-items-center border border-white/10 text-neutral-400 hover:text-white" aria-label="Создать"><Plus className="h-3.5 w-3.5" /></button>}
      </div>
      {children}
      <label className="mx-2 mt-2 flex items-center gap-1 border border-white/10 px-2 py-1 text-neutral-500">
        <Search className="h-3 w-3 shrink-0" />
        <input value={query} onChange={e => onQuery(e.target.value)} aria-label={`Поиск: ${title}`} placeholder="Поиск" className="w-full bg-transparent text-xs text-neutral-200 outline-none" />
      </label>
      <div className="flex-1 overflow-y-auto py-1 text-xs">
        {!rows.length && <p className="px-3 py-4 text-neutral-600">{empty || "Список пуст."}</p>}
        {rows.map(row => (
          <div key={row.id} className={`group flex items-center gap-1 px-2 py-1.5 ${active === row.id ? "bg-white/5 text-white" : "text-neutral-400 hover:bg-white/[0.03]"}`} style={active === row.id ? { boxShadow: "inset 2px 0 0 #fff" } : undefined}>
            <button onClick={() => onOpen(row.id)} className="flex min-w-0 flex-1 items-center gap-2 text-left" aria-label={row.title}>
              <span className={`h-1.5 w-1.5 shrink-0 ${row.alert ? "bg-red-500" : row.working ? "animate-pulse bg-emerald-400" : "bg-neutral-600"}`} title={row.working ? "агент работает" : "простаивает"} />
              <span className="min-w-0 flex-1">
                <span className="block truncate">{row.title}</span>
                {row.subtitle && <span className="block truncate text-[10px] text-neutral-500">{row.subtitle}</span>}
              </span>
            </button>
            {onPin && <button onClick={() => onPin(row.id)} className={`shrink-0 ${row.pinned ? "text-amber-400" : "text-neutral-600 opacity-0 group-hover:opacity-100"}`} aria-label="Закрепить"><Pin className="h-3 w-3" /></button>}
            {onCopy && <button onClick={() => onCopy(row.id)} className="shrink-0 text-neutral-600 opacity-0 hover:text-white group-hover:opacity-100" aria-label="Скопировать ссылку"><Link2 className="h-3 w-3" /></button>}
            {onRename && <button onClick={() => onRename(row.id)} className="shrink-0 text-neutral-600 opacity-0 hover:text-white group-hover:opacity-100" aria-label="Переименовать"><Pencil className="h-3 w-3" /></button>}
            {onDelete && <button onClick={() => onDelete(row.id)} className="shrink-0 text-neutral-600 opacity-0 hover:text-red-300 group-hover:opacity-100" aria-label="Удалить"><Trash2 className="h-3 w-3" /></button>}
          </div>
        ))}
      </div>
      <p className="border-t border-white/10 px-3 py-1 text-[10px] text-neutral-600">j/k список, n новый, 1-4 домен</p>
    </aside>
  );
}
