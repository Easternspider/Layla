"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { api, type Chat, type Design, type Engagement, type OsintCase, type Project } from "@/lib/api";

type Hit = { id: string; label: string; hint: string; href: string; detail?: Record<string, string> };

export function CommandPalette({ open, close }: { open: boolean; close: () => void }) {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [cursor, setCursor] = useState(0);
  const enabled = open;
  const engagements = useQuery({ queryKey: ["engagements"], enabled, queryFn: () => api.get<Engagement[]>("/engagements") });
  const cases = useQuery({ queryKey: ["osint", "palette"], enabled, queryFn: () => api.get<OsintCase[]>("/osint/cases?limit=50&offset=0") });
  const projects = useQuery({ queryKey: ["projects"], enabled, queryFn: () => api.get<Project[]>("/projects") });
  const designs = useQuery({ queryKey: ["designs"], enabled, queryFn: () => api.get<Design[]>("/designs") });
  const chats = useQuery({ queryKey: ["chats", "palette"], enabled, queryFn: () => api.get<Chat[]>("/chats?limit=80") });
  const hits = useMemo(() => {
    const rows: Hit[] = [
      { id: "code", label: "Код", hint: "домен", href: "/code" },
      { id: "pentest", label: "Пентест", hint: "домен", href: "/pentest" },
      { id: "osint", label: "OSINT", hint: "домен", href: "/osint" },
      { id: "design", label: "Дизайн", hint: "домен", href: "/design" },
    ];
    for (const item of engagements.data || []) rows.push({ id: item.id, label: item.target, hint: "пентест", href: `/pentest?engagement=${item.id}`, detail: { engagement_id: item.id } });
    for (const item of cases.data || []) rows.push({ id: item.id, label: item.subject, hint: "osint", href: `/osint?case=${item.id}` });
    for (const item of projects.data || []) rows.push({ id: item.id, label: item.name, hint: "проект", href: `/code?project=${item.id}`, detail: { project_id: item.id, domain: "code" } });
    for (const item of designs.data || []) {
      const title = String((item.brief as Record<string, string>)?.title || (item.brief as Record<string, string>)?.artifact_type || "Макет");
      rows.push({ id: item.id, label: title, hint: "дизайн", href: `/design?design=${item.id}`, detail: { design_id: item.id } });
    }
    for (const item of chats.data || []) rows.push({ id: item.id, label: item.title || "Чат", hint: item.domain, href: `/${item.domain}?chat=${item.id}${item.project_id ? `&project=${item.project_id}` : ""}`, detail: { id: item.id, domain: item.domain, project_id: item.project_id || "" } });
    const needle = query.trim().toLowerCase();
    return needle ? rows.filter(row => `${row.label} ${row.hint}`.toLowerCase().includes(needle)) : rows;
  }, [query, engagements.data, cases.data, projects.data, designs.data, chats.data]);
  useEffect(() => { setCursor(0); }, [query, open]);
  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") { event.preventDefault(); close(); }
      if (event.key === "ArrowDown") { event.preventDefault(); setCursor(value => Math.min(hits.length - 1, value + 1)); }
      if (event.key === "ArrowUp") { event.preventDefault(); setCursor(value => Math.max(0, value - 1)); }
      if (event.key === "Enter" && hits[cursor]) { event.preventDefault(); go(hits[cursor]); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, hits, cursor, close]);
  function go(hit: Hit) {
    close();
    router.push(hit.href);
    if (hit.detail?.engagement_id) window.dispatchEvent(new CustomEvent("layla:open-workspace", { detail: { domain: "pentest", engagement_id: hit.detail.engagement_id } }));
    if (hit.detail?.design_id) window.dispatchEvent(new CustomEvent("layla:open-workspace", { detail: { domain: "design", design_id: hit.detail.design_id } }));
    if (hit.detail?.id) window.dispatchEvent(new CustomEvent("layla:open-chat", { detail: { id: hit.detail.id, domain: hit.detail.domain, project_id: hit.detail.project_id || null } }));
  }
  if (!open) return null;
  return (
    <div role="dialog" aria-modal="true" aria-label="Поиск по Layla" className="fixed inset-0 z-[80] grid place-items-start bg-black/60 p-4 pt-[12vh]" onClick={close}>
      <div onClick={e => e.stopPropagation()} className="w-full max-w-xl border border-white/15 bg-black shadow-floating">
        <input autoFocus value={query} onChange={e => setQuery(e.target.value)} placeholder="Домен, чат, кейс, проект" aria-label="Команда" className="w-full border-b border-white/10 bg-transparent px-4 py-3 text-sm outline-none" />
        <div className="max-h-80 overflow-y-auto py-1">
          {!hits.length && <p className="px-4 py-6 text-sm text-neutral-500">Ничего не найдено.</p>}
          {hits.slice(0, 40).map((hit, index) => (
            <button key={`${hit.hint}:${hit.id}`} onMouseEnter={() => setCursor(index)} onClick={() => go(hit)} className={`flex w-full items-center gap-3 px-4 py-2 text-left text-sm ${index === cursor ? "bg-white/10 text-white" : "text-neutral-300"}`}>
              <span className="w-16 shrink-0 text-[10px] uppercase tracking-wide text-neutral-500">{hit.hint}</span>
              <span className="truncate">{hit.label}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
