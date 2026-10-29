"use client";
import { useEffect, useRef, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, Loader2 } from "lucide-react";
import { api, type Job } from "@/lib/api";
import { useAuth } from "@/store/auth";

const labels: Record<string, string> = { code: "Код", design: "Дизайн", pentest: "Пентест", osint: "OSINT", agent: "Агент" };
const states = { queued: "В очереди", running: "Работает", done: "Готово", error: "Ошибка", cancelled: "Остановлено" };
export function ActivityPanel() {
  const owner = useAuth(s => s.user?.id);
  const router = useRouter();
  const pathname = usePathname();
  const qc = useQueryClient();
  const menu = useRef<HTMLDetailsElement>(null);
  const previous = useRef(new Map<string, string>());
  const [notice, setNotice] = useState<Job | null>(null);
  const { data = [], isError } = useQuery({ queryKey: ["jobs", owner], enabled: !!owner, queryFn: () => api.get<Job[]>("/jobs?limit=100"), refetchInterval: 1500, refetchIntervalInBackground: true });
  const running = data.filter(j => j.status === "running" || j.status === "queued");
  useEffect(() => {
    if (!notice) return;
    const timer = window.setTimeout(() => setNotice(null), 6000);
    return () => window.clearTimeout(timer);
  }, [notice]);
  useEffect(() => {
    for (const job of data) {
      const prev = previous.current.get(job.id);
      if (prev && prev !== job.status) {
        const chat = job.chat_id || job.result.chat_id;
        if (chat) qc.invalidateQueries({ queryKey: ["chat", owner, chat] });
        if (job.status === "done") { qc.invalidateQueries({ queryKey: ["designs"] }); qc.invalidateQueries({ queryKey: ["findings"] }); }
        if ((prev === "running" || prev === "queued") && (job.status === "done" || job.status === "error")) {
          if (document.hidden) notify(job);
          else if (!pathname.startsWith(`/${job.domain}`)) setNotice(job);
        }
      }
      previous.current.set(job.id, job.status);
    }
    const live = data.some(job => job.status === "running" || job.status === "queued");
    try {
      if (live && document.hidden && typeof Notification !== "undefined" && Notification.permission === "default" && !sessionStorage.getItem("layla:notify-asked")) {
        sessionStorage.setItem("layla:notify-asked", "1");
        void Notification.requestPermission().catch(() => undefined);
      }
    } catch { /* Приватный режим может запретить sessionStorage. */ }
  }, [data, owner, qc, pathname]);
  function notify(job: Job) {
    if (typeof Notification === "undefined" || Notification.permission !== "granted") return;
    const note = new Notification(job.status === "error" ? "Layla: ошибка" : "Layla: готово", {
      body: `${labels[job.domain] || job.domain} · ${job.title}`,
    });
    note.onclick = () => { window.focus(); open(job); note.close(); };
  }
  function open(job: Job) {
    const chat = job.chat_id || job.result.chat_id;
    const project = job.result.project_id;
    if (menu.current) menu.current.open = false;
    const query = new URLSearchParams();
    if (typeof chat === "string") {
      query.set("chat", chat);
      try {
        localStorage.setItem(`layla:chat:${owner}:${job.domain}:`, chat);
        if (typeof project === "string") {
          localStorage.setItem(`layla:chat:${owner}:${job.domain}:${project}`, chat);
          if (job.domain === "code") localStorage.setItem(`layla:project:${owner}`, project);
        }
      } catch { /* Storage can be unavailable. */ }
    } else {
      query.set("view", "workspace");
      if (typeof job.result.engagement_id === "string") query.set("engagement", job.result.engagement_id);
      if (typeof job.result.run_id === "string") query.set("run", job.result.run_id);
      if (typeof job.result.design_id === "string") query.set("design", job.result.design_id);
    }
    if (typeof project === "string") query.set("project", project);
    router.push(`/${job.domain}?${query}`);
    if (!chat) window.dispatchEvent(new CustomEvent("layla:open-workspace", { detail: { domain: job.domain, design_id: job.result.design_id, job_id: job.id, engagement_id: job.result.engagement_id, run_id: job.result.run_id } }));
    if (chat) window.dispatchEvent(new CustomEvent("layla:open-chat", { detail: { id: chat, project_id: project, domain: job.domain } }));
  }
  const lead = running[0];
  const leadLabel = lead ? `${labels[lead.domain] || lead.domain} · ${lead.title}` : (isError ? "Нет связи" : "Простой");
  return <>
    <details ref={menu} className="relative max-w-[16rem]">
    <summary aria-label="Прогресс задач" data-live={running.length ? "true" : undefined} className="flex cursor-pointer list-none items-center gap-2 rounded-full bg-[#1c1c1e] px-3 py-2 text-xs [&::-webkit-details-marker]:hidden">{running.length ? <Loader2 className="h-4 w-4 shrink-0 animate-spin text-[#30D158]" /> : <Activity className="h-4 w-4 shrink-0 text-neutral-400" />}<span className="hidden truncate sm:inline">{leadLabel}</span><span aria-live="polite">{running.length}</span></summary>
    <div className="fixed left-3 right-3 top-20 z-50 max-h-[70dvh] overflow-y-auto rounded-[20px] bg-[#1c1c1e] p-2 shadow-floating sm:absolute sm:left-auto sm:right-0 sm:top-full sm:mt-3 sm:w-96">
      <p className="p-2 text-sm font-semibold">Задачи во всех разделах</p>
      {isError && <p role="alert" className="p-2 text-xs text-red-300">Не удалось обновить прогресс. Повторяем подключение…</p>}
      {!data.length && <p className="p-3 text-sm text-neutral-400">Отправьте сообщение в любом чате — его прогресс появится здесь.</p>}
      {[...running, ...data.filter(j => !running.includes(j))].map(job => <button key={job.id} onClick={() => open(job)} className="mb-1 block w-full rounded-xl bg-[#2c2c2e] p-3 text-left hover:bg-[#3a3a3c]"><span className="flex justify-between gap-2 text-xs text-neutral-400"><span>{labels[job.domain] || job.domain}</span><span>{states[job.status]}</span></span><span className="mt-2 block truncate text-sm">{job.title}</span><span className="mt-1 block break-words text-xs text-neutral-400">{job.error || job.steps.at(-1)?.text || "Ожидает начала"}</span>{typeof job.result.verdict === "string" && <span className="mt-2 block whitespace-pre-wrap text-sm">{job.result.verdict}</span>}{job.updated_at && <span className="mt-2 block text-[11px] text-neutral-500">Обновлено {new Date(/[Z+]/.test(job.updated_at) ? job.updated_at : job.updated_at + "Z").toLocaleTimeString()}</span>}</button>)}
    </div>
    </details>
    {notice && <button onClick={() => { const job = notice; setNotice(null); open(job); }} className="toast-in fixed bottom-4 right-4 z-[70] max-w-sm rounded-2xl bg-[#1c1c1e] px-4 py-3 text-left text-xs shadow-floating">
      <span className="block text-neutral-500">{labels[notice.domain] || notice.domain} · {notice.status === "error" ? "ошибка" : "готово"}</span>
      <span className="mt-1 block truncate text-sm text-white">{notice.title}</span>
    </button>}
  </>;
}