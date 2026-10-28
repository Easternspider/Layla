"use client";

import { useEffect, useState, type ReactNode } from "react";
import { Check, Link2, PanelLeft, Pencil, Pin, Plus, Search, Trash2 } from "lucide-react";

export type WorkRow = {
  id: string;
  title: string;
  subtitle?: string;
  working?: boolean;
  pinned?: boolean;
  done?: boolean;
  alert?: boolean;
  updatedAt?: string | null;
};

const FOLDERS = [
  ["pinned", "Закреплённые"],
  ["working", "В работе"],
  ["idle", "Простаивают"],
  ["done", "Готово"],
] as const;

export function loadPins(key: string) {
  try { return JSON.parse(localStorage.getItem(key) || "[]") as string[]; } catch { return []; }
}

export function ago(value?: string | null) {
  if (!value) return "";
  const time = new Date(/(Z|[+-]\d{2}:\d{2})$/i.test(value) ? value : `${value}Z`).getTime();
  if (Number.isNaN(time)) return "";
  const seconds = Math.max(0, (Date.now() - time) / 1000);
  if (seconds < 45) return "только что";
  if (seconds < 3600) return `${Math.floor(seconds / 60)} мин назад`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)} ч назад`;
  return `${Math.floor(seconds / 86400)} дн назад`;
}

function bucket(row: WorkRow) {
  if (row.pinned) return "pinned";
  if (row.working) return "working";
  if (row.done) return "done";
  return "idle";
}

export function folderIds(rows: WorkRow[]) {
  return FOLDERS.flatMap(([name]) => rows.filter(row => bucket(row) === name).map(row => row.id));
}

function typing(event: KeyboardEvent) {
  const el = event.target as HTMLElement | null;
  return !!el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.tagName === "SELECT" || el.isContentEditable);
}

export function useListKeys(ids: string[], current: string | null, select: (id: string) => void, onNew?: () => void) {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (typing(event) || event.metaKey || event.ctrlKey || event.altKey || document.querySelector("[role=dialog]")) return;
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
  title, query, onQuery, rows, active, onOpen, onPin, onDelete, onRename, onCopy, onCreate, empty, children, storageKey, railOpen, onCloseRail,
}: {
  title: string;
  query: string;
  onQuery: (value: string) => void;
  rows: WorkRow[];
  active: string | null;
  onOpen: (id: string) => void;
  onPin?: (id: string) => void;
  onDelete?: (id: string) => void;
  onRename?: (id: string, title: string) => void;
  onCopy?: (id: string) => void;
  onCreate?: () => void;
  empty?: string;
  children?: ReactNode;
  storageKey: string;
  railOpen?: boolean;
  onCloseRail?: () => void;
}) {
  const [open, setOpen] = useState(true);
  const [folders, setFolders] = useState<Record<string, boolean>>({ done: true });
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [copied, setCopied] = useState<string | null>(null);
  useEffect(() => {
    try {
      const stored = localStorage.getItem(storageKey);
      if (stored === "0") setOpen(false);
      else if (stored === null && window.matchMedia("(max-width: 900px)").matches) setOpen(false);
      const saved = localStorage.getItem(`${storageKey}:folders`);
      if (saved) setFolders(JSON.parse(saved));
    } catch { /* ignore */ }
  }, [storageKey]);
  useEffect(() => { try { localStorage.setItem(storageKey, open ? "1" : "0"); } catch { /* ignore */ } }, [open, storageKey]);
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape" || typing(event) || document.querySelector("[role=dialog]")) return;
      if (editing) { setEditing(null); return; }
      if (railOpen && onCloseRail) { onCloseRail(); return; }
      if (open) setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [editing, open, railOpen, onCloseRail]);
  function copy(id: string) {
    onCopy?.(id);
    setCopied(id);
    window.setTimeout(() => setCopied(current => current === id ? null : current), 1200);
  }
  function toggleFolder(name: string) {
    setFolders(current => {
      const next = { ...current, [name]: !current[name] };
      try { localStorage.setItem(`${storageKey}:folders`, JSON.stringify(next)); } catch { /* ignore */ }
      return next;
    });
  }
  if (!open) {
    return (
      <aside className="m-2 flex w-9 shrink-0 flex-col items-center rounded-2xl bg-[#1c1c1e] py-2">
        <button onClick={() => setOpen(true)} className="text-neutral-500 hover:text-white" aria-label="Показать список"><PanelLeft className="h-4 w-4" /></button>
      </aside>
    );
  }
  return (
    <aside className="m-2 flex w-64 shrink-0 flex-col rounded-2xl bg-[#1c1c1e]">
      <div className="flex items-center justify-between border-b border-white/10 px-3 py-2">
        <span className="text-[11px] font-semibold uppercase tracking-wide text-neutral-400">{title}</span>
        <span className="ml-auto flex items-center gap-1">
          {onCreate && <button onClick={onCreate} className="grid h-6 w-6 place-items-center border border-white/10 text-neutral-400 hover:text-white" aria-label="Создать"><Plus className="h-3.5 w-3.5" /></button>}
          <button onClick={() => setOpen(false)} className="grid h-6 w-6 place-items-center text-neutral-500 hover:text-white" aria-label="Свернуть список"><PanelLeft className="h-3.5 w-3.5" /></button>
        </span>
      </div>
      {children}
      <label className="mx-2 mt-2 flex items-center gap-1 border border-white/10 px-2 py-1 text-neutral-500">
        <Search className="h-3 w-3 shrink-0" />
        <input value={query} onChange={e => onQuery(e.target.value)} aria-label={`Поиск: ${title}`} placeholder="Поиск" className="w-full bg-transparent text-xs text-neutral-200 outline-none" />
      </label>
      <div className="flex-1 overflow-y-auto py-1 text-xs">
        {!rows.length && <p className="px-3 py-4 text-neutral-600">{empty || "Список пуст."}</p>}
        {FOLDERS.map(([name, label]) => {
          const group = rows.filter(row => bucket(row) === name);
          if (!group.length) return null;
          return (
            <div key={name}>
              <button onClick={() => toggleFolder(name)} className="flex w-full items-center gap-2 px-3 py-1 text-[10px] uppercase tracking-wide text-neutral-600 hover:text-neutral-300">
                <span className="flex-1 text-left">{label}</span><span>{group.length}</span>
              </button>
              {!folders[name] && group.map(row => {
                const meta = [row.subtitle, ago(row.updatedAt)].filter(Boolean).join(" · ");
                return (
                  <div key={row.id} className={`group mx-1 flex items-center gap-1 rounded-xl px-2 py-1.5 ${active === row.id ? "bg-[#0A84FF] text-white" : "text-neutral-300 hover:bg-white/[0.06]"}`}>
                    {editing === row.id ? (
                      <form className="flex min-w-0 flex-1 gap-1" onSubmit={event => { event.preventDefault(); if (draft.trim()) { onRename?.(row.id, draft.trim()); setEditing(null); } }}>
                        <input autoFocus value={draft} onChange={e => setDraft(e.target.value)} aria-label="Новое название" onKeyDown={e => { if (e.key === "Escape") { e.stopPropagation(); setEditing(null); } }} className="min-w-0 flex-1 border border-white/15 bg-black px-1 py-0.5 text-xs text-white" />
                      </form>
                    ) : (
                      <button onClick={() => onOpen(row.id)} className="flex min-w-0 flex-1 items-center gap-2 text-left" aria-label={row.title}>
                        <span className={`h-2 w-2 shrink-0 rounded-full ${row.alert ? "bg-[#FF453A]" : row.working ? "animate-pulse bg-[#30D158]" : active === row.id ? "bg-white" : "bg-neutral-400"}`} title={row.working ? "агент работает" : "простаивает"} />
                        <span className="min-w-0 flex-1">
                          <span className="block truncate text-[13px] leading-5">{row.title}</span>
                          {meta && <span className={`block truncate text-xs leading-4 ${active === row.id ? "text-white/90" : "text-neutral-300"}`}>{meta}</span>}
                        </span>
                      </button>
                    )}
                    {onPin && editing !== row.id && <button onClick={() => onPin(row.id)} className={`shrink-0 ${row.pinned ? "text-amber-400" : "text-neutral-600 opacity-0 group-hover:opacity-100"}`} aria-label="Закрепить"><Pin className="h-3 w-3" /></button>}
                    {onCopy && editing !== row.id && <button onClick={() => copy(row.id)} className="shrink-0 text-neutral-600 opacity-0 hover:text-white group-hover:opacity-100" aria-label={copied === row.id ? "Скопировано" : "Скопировать ссылку"}>{copied === row.id ? <Check className="h-3 w-3 text-emerald-300" /> : <Link2 className="h-3 w-3" />}</button>}
                    {onRename && editing !== row.id && <button onClick={() => { setEditing(row.id); setDraft(row.title); }} className="shrink-0 text-neutral-600 opacity-0 hover:text-white group-hover:opacity-100" aria-label="Переименовать"><Pencil className="h-3 w-3" /></button>}
                    {onDelete && editing !== row.id && <button onClick={() => onDelete(row.id)} className="shrink-0 text-neutral-600 opacity-0 hover:text-red-300 group-hover:opacity-100" aria-label="Удалить"><Trash2 className="h-3 w-3" /></button>}
                  </div>
                );
              })}
            </div>
          );
        })}
      </div>
      <p className="border-t border-white/10 px-3 py-1 text-[10px] text-neutral-600">j/k список, n новый, Esc свернуть</p>
    </aside>
  );
}
