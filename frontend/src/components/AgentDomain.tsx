"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChatPanel } from "@/components/ChatPanel";
import { WorkRail, loadPins } from "@/components/WorkRail";
import { confirmAction } from "@/components/ConfirmDialog";
import { api, type Chat, type Job, type PentestServer } from "@/lib/api";
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

export function AgentDomain() {
  const owner = useAuth(s => s.user?.id);
  const qc = useQueryClient();
  const [query, setQuery] = useState("");
  const [pins, setPins] = useState<string[]>([]);
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState({ host: "", port: 22, user: "root", auth: "key" as "key" | "password", private_key: "", password: "" });
  const [chatId, setChatId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { setPins(loadPins("layla:agent:pinned")); }, []);
  useEffect(() => { try { localStorage.setItem("layla:agent:pinned", JSON.stringify(pins)); } catch { /* ignore */ } }, [pins]);
  useEffect(() => {
    if (!owner) return;
    try {
      const stored = localStorage.getItem(`layla:chat:${owner}:agent:`);
      if (stored && stored !== "new") setChatId(stored);
    } catch { /* ignore */ }
    const choose = (event: Event) => {
      const detail = (event as CustomEvent<{ domain?: string; id?: string | null }>).detail;
      if (detail?.domain === "agent") setChatId(detail.id || null);
    };
    window.addEventListener("layla:chat-selected", choose);
    return () => window.removeEventListener("layla:chat-selected", choose);
  }, [owner]);
  const chats = useQuery({
    queryKey: ["chats", owner, "agent", undefined],
    enabled: !!owner,
    queryFn: () => api.get<Chat[]>("/chats?domain=agent"),
  });
  const jobs = useQuery({
    queryKey: ["jobs", owner],
    enabled: !!owner,
    queryFn: () => api.get<Job[]>("/jobs?limit=100"),
    refetchInterval: 2000,
  });
  const servers = useQuery({ queryKey: ["servers"], queryFn: () => api.get<PentestServer[]>("/servers") });
  const members = useQuery({
    queryKey: ["crew", owner, chatId],
    enabled: !!owner && !!chatId,
    queryFn: () => api.get<Member[]>(`/chats/${chatId}/crew`),
    refetchInterval: 2000,
  });
  const stopMember = useMutation({
    mutationFn: (id: string) => api.post(`/chats/${chatId}/crew/${id}/stop`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["crew", owner, chatId] }),
  });
  const chosen = chats.data?.find(chat => chat.id === chatId)?.server_ids || [];
  const setServers = useMutation({
    mutationFn: (server_ids: string[]) => api.put(`/chats/${chatId}/servers`, { server_ids }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["chats", owner, "agent", undefined] });
      if (chatId) qc.invalidateQueries({ queryKey: ["chat", owner, chatId] });
    },
    onError: err => setError(err instanceof Error ? err.message : "Выбор серверов не сохранился"),
  });
  const create = useMutation({
    mutationFn: () => api.post<Chat>("/chats", { domain: "agent", title: "Новая задача" }),
    onSuccess: chat => {
      qc.invalidateQueries({ queryKey: ["chats", owner, "agent", undefined] });
      window.dispatchEvent(new CustomEvent("layla:open-chat", { detail: chat }));
    },
  });
  const addServer = useMutation({
    mutationFn: () => api.post("/servers", {
      host: form.host.trim(), port: form.port, user: form.user.trim() || "root", auth: form.auth,
      private_key: form.auth === "key" ? form.private_key : undefined,
      password: form.auth === "password" ? form.password : undefined,
    }),
    onSuccess: () => {
      setForm({ host: "", port: 22, user: "root", auth: "key", private_key: "", password: "" });
      setAdding(false);
      setError(null);
      qc.invalidateQueries({ queryKey: ["servers"] });
    },
    onError: err => setError(err instanceof Error ? err.message : "Сервер не сохранился"),
  });
  const rows = (chats.data || []).map(chat => ({
    id: chat.id,
    title: chat.title || "Задача",
    pinned: pins.includes(chat.id),
    working: (jobs.data || []).some(job => job.chat_id === chat.id && (job.status === "queued" || job.status === "running")),
  }));
  return <div className="flex h-full min-h-0 bg-black text-neutral-200">
    <WorkRail title="Задачи" storageKey="layla:agent:list" query={query} onQuery={setQuery} active=""
      empty={chats.isPending ? "Загрузка…" : "Задач пока нет."}
      rows={rows}
      onCreate={() => create.mutate()}
      onOpen={id => { const chat = chats.data?.find(item => item.id === id); if (chat) window.dispatchEvent(new CustomEvent("layla:open-chat", { detail: chat })); }}
      onPin={id => setPins(list => list.includes(id) ? list.filter(value => value !== id) : [...list, id])}
      onCopy={id => { const url = new URL(window.location.href); url.searchParams.set("chat", id); navigator.clipboard.writeText(url.toString()).catch(() => undefined); }}
      onRename={async (id, title) => { await api.patch(`/chats/${id}`, { title }); await qc.invalidateQueries({ queryKey: ["chats", owner, "agent", undefined] }); }}
      onDelete={async id => { if (!(await confirmAction("Удалить задачу? Чат уйдёт в корзину."))) return; await api.del(`/chats/${id}`); await qc.invalidateQueries({ queryKey: ["chats", owner, "agent", undefined] }); }} />
    <div className="flex min-h-0 min-w-0 flex-1 flex-col">
      <ChatPanel domain="agent" />
    </div>
    <aside className="ios-panel m-2 hidden w-[280px] shrink-0 flex-col overflow-hidden rounded-2xl bg-[#1c1c1e] lg:flex">
      <div className="flex items-center justify-between px-3 py-3">
        <p className="text-sm font-medium">Серверы</p>
        <button className="text-xs text-[#0A84FF]" onClick={() => setAdding(value => !value)}>{adding ? "Закрыть" : "Добавить"}</button>
      </div>
      {adding && <form className="space-y-2 border-t border-white/10 px-3 py-3" onSubmit={event => { event.preventDefault(); addServer.mutate(); }}>
        <input aria-label="Адрес сервера" value={form.host} onChange={event => setForm({ ...form, host: event.target.value })} placeholder="Хост" className="w-full rounded-lg bg-black px-2 py-1.5 text-xs" />
        <div className="flex gap-2">
          <input aria-label="Пользователь SSH" value={form.user} onChange={event => setForm({ ...form, user: event.target.value })} placeholder="Пользователь" className="w-full rounded-lg bg-black px-2 py-1.5 text-xs" />
          <input aria-label="Порт SSH" type="number" value={form.port} onChange={event => setForm({ ...form, port: Number(event.target.value) })} className="w-20 rounded-lg bg-black px-2 py-1.5 text-xs" />
        </div>
        <select aria-label="Способ входа" value={form.auth} onChange={event => setForm({ ...form, auth: event.target.value as "key" | "password", private_key: "", password: "" })} className="w-full rounded-lg bg-black px-2 py-1.5 text-xs">
          <option value="key">Вход по ключу</option>
          <option value="password">Вход по паролю</option>
        </select>
        {form.auth === "password" ? (
          <input aria-label="Пароль SSH" type="password" autoComplete="new-password" value={form.password} onChange={event => setForm({ ...form, password: event.target.value })} placeholder="Пароль SSH" className="w-full rounded-lg bg-black px-2 py-1.5 text-xs" />
        ) : (
          <textarea aria-label="Приватный ключ" value={form.private_key} onChange={event => setForm({ ...form, private_key: event.target.value })} placeholder="Приватный ключ" rows={4} className="w-full rounded-lg bg-black px-2 py-1.5 text-xs" />
        )}
        <button disabled={!form.host.trim() || (form.auth === "password" ? !form.password.trim() : !form.private_key.trim()) || addServer.isPending} className="w-full rounded-lg bg-[#0A84FF] py-1.5 text-xs text-white disabled:opacity-40">Сохранить</button>
        {error && <p className="text-xs text-red-300">{error}</p>}
      </form>}
      <div className="min-h-0 flex-1 space-y-1 overflow-y-auto px-2 pb-3">
        <p className="px-2 pb-1 text-[11px] leading-4 text-neutral-500">{chatId ? (chosen.length ? "Задача работает только с отмеченными серверами." : "Ничего не отмечено: агент видит все серверы. Отметьте один или несколько, чтобы ограничить задачу.") : "Откройте задачу, чтобы выбрать серверы."}</p>
        {error && !adding && <p className="px-2 text-xs text-red-300">{error}</p>}
        {(servers.data || []).map(server => <label key={server.id} className="flex items-start gap-2 rounded-xl px-2 py-2 hover:bg-white/[0.04]">
          <input aria-label={`Сервер ${server.host}`} type="checkbox" className="mt-1" disabled={!chatId || setServers.isPending} checked={chosen.includes(server.id)} onChange={() => {
            const next = chosen.includes(server.id) ? chosen.filter(id => id !== server.id) : [...chosen, server.id];
            setServers.mutate(next);
          }} />
          <span className="min-w-0">
            <p className="truncate text-sm">{server.user}@{server.host}</p>
            <p className="text-[11px] text-neutral-500">{server.port} · {server.auth === "password" ? "пароль" : "ключ"} · {server.status}</p>
          </span>
        </label>)}
        {!servers.data?.length && <p className="px-2 text-xs text-neutral-500">Добавьте сервер, и агент сможет проверить его и поставить пакеты.</p>}
        <p className="px-2 pt-3 text-sm font-medium">Субагенты</p>
        <p className="px-2 text-[11px] leading-4 text-neutral-500">Не больше трёх. Ведущий сам открывает сайты, смотрит картинки и решает капчу.</p>
        {!chatId && <p className="px-2 text-xs text-neutral-500">Откройте задачу, чтобы видеть субагентов.</p>}
        {chatId && members.isSuccess && members.data.length === 0 && <p className="px-2 text-xs text-neutral-500">Пока никого.</p>}
        {(members.data || []).map(member => <article key={member.id} className="rounded-xl bg-black/50 px-3 py-2">
          <div className="flex items-center justify-between gap-2">
            <p className="text-xs font-medium">{ROLE[member.role] || member.role}</p>
            <p className="text-[11px] text-neutral-400">{STATUS[member.status] || member.status}{member.detached ? " · фон" : ""}</p>
          </div>
          <p className="mt-1 line-clamp-3 text-[11px] leading-4 text-neutral-300">{member.task}</p>
          {member.report && <p className="mt-1 line-clamp-4 text-[11px] leading-4 text-neutral-500">{member.report}</p>}
          {member.error && <p className="mt-1 text-[11px] text-red-300">{member.error}</p>}
          {(member.status === "queued" || member.status === "running") && <button className="mt-2 text-[11px] text-[#0A84FF]" disabled={stopMember.isPending} onClick={() => stopMember.mutate(member.id)}>Остановить</button>}
        </article>)}
      </div>
    </aside>
  </div>;
}
