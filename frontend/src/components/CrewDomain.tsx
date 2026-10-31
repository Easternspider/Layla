"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChatPanel } from "@/components/ChatPanel";
import { WorkRail, loadPins } from "@/components/WorkRail";
import { confirmAction } from "@/components/ConfirmDialog";
import { api, type Chat, type Job } from "@/lib/api";
import { useAuth } from "@/store/auth";

type Member = {
  id: string;
  role: string;
  task: string;
  status: string;
  report: string;
  error: string | null;
  detached: boolean;
};

const ROLE: Record<string, string> = { research: "Поиск", review: "Ревью", build: "Сборка" };
const STATUS: Record<string, string> = {
  queued: "в очереди", running: "работает", done: "готово", error: "ошибка",
  cancelled: "остановлен", interrupted: "прерван",
};

export function CrewDomain() {
  const owner = useAuth(s => s.user?.id);
  const qc = useQueryClient();
  const [query, setQuery] = useState("");
  const [pins, setPins] = useState<string[]>([]);
  const [chatId, setChatId] = useState<string | null>(null);
  useEffect(() => { setPins(loadPins("layla:crew:pinned")); }, []);
  useEffect(() => { try { localStorage.setItem("layla:crew:pinned", JSON.stringify(pins)); } catch { /* ignore */ } }, [pins]);
  useEffect(() => {
    if (!owner) return;
    try {
      const stored = localStorage.getItem(`layla:chat:${owner}:crew:`);
      if (stored && stored !== "new") setChatId(stored);
    } catch { /* ignore */ }
    const choose = (event: Event) => {
      const detail = (event as CustomEvent<{ domain?: string; id?: string | null }>).detail;
      if (detail?.domain === "crew") setChatId(detail.id || null);
    };
    window.addEventListener("layla:chat-selected", choose);
    return () => window.removeEventListener("layla:chat-selected", choose);
  }, [owner]);
  const chats = useQuery({
    queryKey: ["chats", owner, "crew", undefined],
    enabled: !!owner,
    queryFn: () => api.get<Chat[]>("/chats?domain=crew"),
  });
  const jobs = useQuery({
    queryKey: ["jobs", owner, "agent"],
    enabled: !!owner,
    queryFn: () => api.get<Job[]>("/jobs?domain=agent&limit=100"),
    refetchInterval: 2000,
  });
  const members = useQuery({
    queryKey: ["crew", owner, chatId],
    enabled: !!owner && !!chatId,
    queryFn: () => api.get<Member[]>(`/chats/${chatId}/crew`),
    refetchInterval: 2000,
  });
  const create = useMutation({
    mutationFn: () => api.post<Chat>("/chats", { domain: "crew", title: "Новый оркестр" }),
    onSuccess: chat => {
      qc.invalidateQueries({ queryKey: ["chats", owner, "crew", undefined] });
      window.dispatchEvent(new CustomEvent("layla:open-chat", { detail: chat }));
    },
  });
  const stop = useMutation({
    mutationFn: (id: string) => api.post(`/chats/${chatId}/crew/${id}/stop`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["crew", owner, chatId] }),
  });
  const rows = (chats.data || []).map(chat => ({
    id: chat.id,
    title: chat.title || "Оркестр",
    pinned: pins.includes(chat.id),
    working: (jobs.data || []).some(job => job.chat_id === chat.id && (job.status === "queued" || job.status === "running")),
  }));
  return <div className="flex h-full min-h-0 bg-black text-neutral-200">
    <WorkRail title="Оркестры" storageKey="layla:crew:list" query={query} onQuery={setQuery} active=""
      empty={chats.isPending ? "Загрузка…" : "Чатов пока нет."}
      rows={rows}
      onCreate={() => create.mutate()}
      onOpen={id => { const chat = chats.data?.find(item => item.id === id); if (chat) window.dispatchEvent(new CustomEvent("layla:open-chat", { detail: chat })); }}
      onPin={id => setPins(list => list.includes(id) ? list.filter(value => value !== id) : [...list, id])}
      onCopy={id => { const url = new URL(window.location.href); url.searchParams.set("chat", id); navigator.clipboard.writeText(url.toString()).catch(() => undefined); }}
      onRename={async (id, title) => { await api.patch(`/chats/${id}`, { title }); await qc.invalidateQueries({ queryKey: ["chats", owner, "crew", undefined] }); }}
      onDelete={async id => { if (!(await confirmAction("Удалить оркестр? Чат уйдёт в корзину."))) return; await api.del(`/chats/${id}`); await qc.invalidateQueries({ queryKey: ["chats", owner, "crew", undefined] }); }} />
    <div className="flex min-h-0 min-w-0 flex-1 flex-col">
      <ChatPanel domain="crew" />
    </div>
    <aside className="ios-panel m-2 hidden w-[300px] shrink-0 flex-col overflow-hidden rounded-2xl bg-[#1c1c1e] lg:flex">
      <div className="px-3 py-3">
        <p className="text-sm font-medium">Субагенты</p>
        <p className="pt-1 text-[11px] leading-4 text-neutral-500">Ведущий сам открывает сайты, смотрит экран и картинки, заполняет формы и заводит почту. Субагентов не больше трёх.</p>
      </div>
      <div className="min-h-0 flex-1 space-y-2 overflow-y-auto px-2 pb-3">
        {!chatId && <p className="px-2 text-xs text-neutral-500">Откройте чат, чтобы видеть субагентов.</p>}
        {chatId && members.isPending && <p className="px-2 text-xs text-neutral-500">Загрузка…</p>}
        {chatId && members.isSuccess && members.data.length === 0 && <p className="px-2 text-xs text-neutral-500">Пока никого. Попросите ведущего раздать задачу.</p>}
        {(members.data || []).map(member => <article key={member.id} className="rounded-xl bg-black/50 px-3 py-2">
          <div className="flex items-center justify-between gap-2">
            <p className="text-xs font-medium">{ROLE[member.role] || member.role}</p>
            <p className="text-[11px] text-neutral-400">{STATUS[member.status] || member.status}{member.detached ? " · фон" : ""}</p>
          </div>
          <p className="mt-1 line-clamp-3 text-[11px] leading-4 text-neutral-300">{member.task}</p>
          {member.report && <p className="mt-1 line-clamp-4 text-[11px] leading-4 text-neutral-500">{member.report}</p>}
          {member.error && <p className="mt-1 text-[11px] text-red-300">{member.error}</p>}
          {(member.status === "queued" || member.status === "running") && <button className="mt-2 text-[11px] text-[#0A84FF]" disabled={stop.isPending} onClick={() => stop.mutate(member.id)}>Остановить</button>}
        </article>)}
      </div>
    </aside>
  </div>;
}
