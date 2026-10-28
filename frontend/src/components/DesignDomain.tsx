"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import {
  ChevronDown, Code2, Columns2, Eye, History, Loader2, Monitor, MousePointerClick, Palette,
  PanelRight, Smartphone, Sparkles, Tablet,
} from "lucide-react";
import { ChatPanel } from "@/components/ChatPanel";
import { PickBar, PickFrame } from "@/components/PickBar";
import { pickMessage, type PickedElement } from "@/lib/pick";
import { DesignBriefForm } from "@/components/DesignBriefForm";
import { CodeStream, DesignLive, isActive } from "@/components/DesignLive";
import { loadPins, folderIds, useListKeys, WorkRail } from "@/components/WorkRail";
import { api, type Chat, type Design, type FileContent, type FileNode, type Job, type ModelInfo, type Project } from "@/lib/api";
import { DEFAULT_BRIEF, briefPayload, loadBrief, saveBrief, type Brief } from "@/lib/design-brief";
import { useAuth } from "@/store/auth";
import { confirmAction } from "@/components/ConfirmDialog";

const BREAKPOINTS = { desktop: "100%", tablet: "768px", mobile: "390px" } as const;

/** Что показываем в превью: файлы открытого чата или сохранённую версию брифа. */
type Source = { kind: "chat" } | { kind: "design"; id: string };

export function DesignDomain() {
  const qc = useQueryClient();
  const router = useRouter();
  const [brief, setBrief] = useState<Brief>(DEFAULT_BRIEF);
  const briefLoaded = useRef(false);
  const [stack, setStack] = useState("html");
  const [model, setModel] = useState("");
  const [briefOpen, setBriefOpen] = useState(false);
  const [source, setSource] = useState<Source>({ kind: "chat" });
  const [chatProject, setChatProject] = useState<string | null>(null);
  const [view, setView] = useState<"preview" | "code" | "split">("preview");
  const [bp, setBp] = useState<keyof typeof BREAKPOINTS>("desktop");
  const [pane, setPane] = useState<"chat" | "result">("chat");
  const [busy, setBusy] = useState(false);
  const [chatOpen, setChatOpen] = useState(true);
  const [listQuery, setListQuery] = useState("");
  const [pins, setPins] = useState<string[]>([]);
  useEffect(() => { setPins(loadPins("layla:design:pinned")); }, []);
  useEffect(() => { try { localStorage.setItem("layla:design:pinned", JSON.stringify(pins)); } catch { /* ignore */ } }, [pins]);
  const [error, setError] = useState<string | null>(null);
  // Генерация по брифу, которую показываем вживую; watching=false — пользователь смотрит другое.
  const [liveJobId, setLiveJobId] = useState<string | null>(null);
  const [watching, setWatching] = useState(false);
  // Правка по клику: режим выбора и выбранный в превью элемент.
  const [picking, setPicking] = useState(false);
  const [pickedEl, setPickedEl] = useState<PickedElement | null>(null);
  const [pickBusy, setPickBusy] = useState(false);

  const { data: models = [] } = useQuery({ queryKey: ["models"], queryFn: () => api.get<ModelInfo[]>("/models") });
  const { data: designs = [], isSuccess: designsLoaded } = useQuery({ queryKey: ["designs"], queryFn: () => api.get<Design[]>("/designs") });
  // Тот же ключ, что у истории в ChatPanel, — общий кеш, без лишнего запроса.
  const owner = useAuth(s => s.user?.id);
  const { data: chats = [], isSuccess: chatsLoaded } = useQuery({
    queryKey: ["chats", owner, "design", undefined],
    queryFn: () => api.get<Chat[]>("/chats?domain=design"),
  });

  // Файлы чата: их пишет агент, поэтому превью показывает актуальный результат.
  const tree = useQuery({
    queryKey: ["design-files", chatProject],
    enabled: !!chatProject,
    queryFn: () => api.get<FileNode[]>(`/projects/${chatProject}/files`),
  });
  const page = useMemo(() => {
    const list = (tree.data || []).filter(f => !f.is_dir);
    return list.find(f => f.name === "index.html") || list.find(f => f.name.endsWith(".html")) || null;
  }, [tree.data]);
  const live = useQuery({
    queryKey: ["design-file", chatProject, page?.path],
    enabled: !!chatProject && !!page,
    queryFn: () => api.get<FileContent>(`/projects/${chatProject}/file?path=${encodeURIComponent(page!.path)}`),
  });

  const liveJob = useQuery({
    queryKey: ["design-job", liveJobId],
    enabled: !!liveJobId,
    queryFn: () => api.get<Job>(`/jobs/${liveJobId}`),
    refetchInterval: q => (!q.state.data || isActive(q.state.data) ? 700 : false),
    refetchIntervalInBackground: true,
  });
  // Генерация, начатая раньше (до перезагрузки страницы или в другом разделе), — продолжаем показывать.
  const running = useQuery({
    queryKey: ["design-running-jobs"],
    queryFn: () => api.get<Job[]>("/jobs?active=true&limit=50"),
    // Только при открытии раздела и всегда свежий список: старый кеш вернул бы давно законченную задачу.
    staleTime: Infinity,
    gcTime: 0,
    refetchOnWindowFocus: false,
  });

  const generate = useMutation({
    mutationFn: () => api.post<Job>("/designs/generate", { stack, brief: briefPayload(brief), model: model || undefined }),
    onSuccess: job => {
      setLiveJobId(job.id);
      setWatching(true);
      setView("split");
      setPane("result");
      qc.invalidateQueries({ queryKey: ["jobs"] });
      setBriefOpen(false);
      setError(null);
    },
    onError: e => setError(e instanceof Error ? e.message : "Ошибка генерации"),
  });
  const resume = useMutation({
    mutationFn: (id: string) => api.post<Job>(`/designs/generate/${id}/resume`),
    onSuccess: next => { setLiveJobId(next.id); setWatching(true); setError(null); qc.invalidateQueries({ queryKey: ["jobs"] }); },
    onError: e => setError(e instanceof Error ? e.message : "Не удалось продолжить генерацию"),
  });
  const stop = useMutation({
    mutationFn: (id: string) => api.post<Job>(`/jobs/${id}/cancel`),
    onSettled: () => liveJob.refetch(),
    onError: e => setError(e instanceof Error ? e.message : "Не удалось остановить"),
  });

  useEffect(() => {
    if (briefLoaded.current) { saveBrief(brief); return; }
    briefLoaded.current = true;
    setBrief(loadBrief());
  }, [brief]);
  useEffect(() => {
    const job = running.data?.find(j => j.kind === "design.generate");
    if (job) { setLiveJobId(id => id ?? job.id); setWatching(true); }
  }, [running.data]);
  // Генерация закончилась: готовую версию сразу показываем в превью.
  const finished = liveJob.data?.status === "done" ? liveJob.data.result.design_id : undefined;
  useEffect(() => {
    if (typeof finished !== "string") return;
    let cancelled = false;
    qc.invalidateQueries({ queryKey: ["designs"] }).then(() => {
      if (cancelled) return;
      setSource({ kind: "design", id: finished });
      setLiveJobId(null);
      setWatching(false);
    });
    qc.invalidateQueries({ queryKey: ["providers"] });  // модель могла подстроить свои настройки
    return () => { cancelled = true; };
  }, [finished, qc]);

  // Бриф раскрывается сам только на совсем пустом разделе. Раньше он открывался,
  // когда не было версий, и прятал чат — вместе с кнопками удаления и очистки истории.
  useEffect(() => {
    if (designsLoaded && chatsLoaded && !designs.length && !chats.length) setBriefOpen(true);
  }, [designsLoaded, chatsLoaded, designs.length, chats.length]);
  useEffect(() => {
    const linked = new URLSearchParams(window.location.search).get("design");
    if (linked && designs.some(d => d.id === linked)) setSource({ kind: "design", id: linked });
  }, [designs]);
  useEffect(() => {
    const mine = (e: Event) => (e as CustomEvent<{ domain?: string }>).detail?.domain === "design";
    // Клик по готовой генерации в «В работе» открывает именно эту версию.
    const result = (e: Event) => {
      if (!mine(e)) return;
      const detail = (e as CustomEvent<{ design_id?: unknown; job_id?: unknown }>).detail;
      if (typeof detail.design_id === "string") {
        setSource({ kind: "design", id: detail.design_id });
        setWatching(false);
      } else if (typeof detail.job_id === "string") {
        // Идущая или сорвавшаяся генерация — показываем её ход и черновик.
        setLiveJobId(detail.job_id);
        setWatching(true);
      }
      setPane("result");
    };
    const chat = (e: Event) => { if (mine(e)) { setPane("chat"); setChatOpen(true); } };
    window.addEventListener("layla:open-workspace", result);
    window.addEventListener("layla:open-chat", chat);
    return () => { window.removeEventListener("layla:open-workspace", result); window.removeEventListener("layla:open-chat", chat); };
  }, []);

  // Агент дописал файл — перечитываем превью, чтобы оно не отставало от чата.
  const refresh = useCallback(() => {
    qc.invalidateQueries({ queryKey: ["design-files", chatProject] });
    qc.invalidateQueries({ queryKey: ["design-file", chatProject] });
  }, [qc, chatProject]);
  const bindProject = useCallback((id: string | null) => setChatProject(id), []);

  const showLive = !!liveJobId && watching;
  const picked = source.kind === "design" ? designs.find(d => d.id === source.id) || null : null;
  // Пока чат не создал страницу, показывать нечего — тогда видна последняя версия брифа.
  const version = picked || (page ? null : designs[0] || null);
  const html = version ? version.files?.[0]?.content ?? "" : live.data?.content ?? "";

  const versionLabel = (d: Design) => {
    const brief = d.brief as Record<string, string>;
    if (brief?.title) return brief.title;
    const i = designs.findIndex(x => x.id === d.id);
    return `Версия ${designs.length - i} · ${String(brief?.artifact_type || "Design")} · ${d.stack}`;
  };
  function choose(next: Source) {
    setSource(next);
    setWatching(false);
  }
  async function clearVersions() {
    if (!designs.length || !(await confirmAction(`Удалить все версии (${designs.length})? Проекты, созданные из них в «Коде», останутся.`))) return;
    setBusy(true);
    try {
      await api.del("/designs");
      setSource({ kind: "chat" });
      await qc.invalidateQueries({ queryKey: ["designs"] });
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось удалить версии");
    } finally { setBusy(false); }
  }

  async function removeVersion(id: string) {
    if (!(await confirmAction("Удалить эту версию макета? Проект, созданный из неё, останется."))) return;
    setBusy(true);
    try {
      await api.del(`/designs/${id}`);
      if (source.kind === "design" && source.id === id) setSource({ kind: "chat" });
      await qc.invalidateQueries({ queryKey: ["designs"] });
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось удалить версию");
    } finally { setBusy(false); }
  }

  function stopPicking() { setPicking(false); setPickedEl(null); }
  /** Задача по выбранному элементу — в дизайн-чат. Версию по брифу сначала копируем в новый чат. */
  async function sendPick(request: string) {
    if (!pickedEl) return;
    setPickBusy(true);
    try {
      const text = pickMessage(pickedEl, request, version ? "index.html" : page?.path);
      if (version) {
        const chat = await api.post<Chat>(`/designs/${version.id}/chat`);
        await qc.invalidateQueries({ queryKey: ["chats"] });
        window.dispatchEvent(new CustomEvent("layla:open-chat", { detail: chat }));
        window.dispatchEvent(new CustomEvent("layla:chat-send", { detail: { domain: "design", text, chat_id: chat.id } }));
        setSource({ kind: "chat" });
      } else {
        window.dispatchEvent(new CustomEvent("layla:chat-send", { detail: { domain: "design", text } }));
      }
      stopPicking();
      setError(null);
      // На телефоне превью и чат — разные экраны: показываем чат, где агент уже работает.
      if (window.matchMedia?.("(max-width: 760px)").matches) setPane("chat");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось отправить правку");
    } finally { setPickBusy(false); }
  }

  /** Передать увиденное в домен «Код»: там файловое дерево, редактор и агент. */
  async function openInCode() {
    setBusy(true);
    try {
      let projectId = chatProject;
      if (version) {
        const project = await api.post<Project>(`/designs/${version.id}/project`);
        projectId = project.id;
        await Promise.all([
          qc.invalidateQueries({ queryKey: ["designs"] }),
          qc.invalidateQueries({ queryKey: ["projects"] }),
        ]);
      }
      if (!projectId) { setError("Сначала сгенерируйте макет или начните чат."); return; }
      // Папка чата становится проектом «Кода»: появляется в списке и не удаляется вместе с чатом.
      if (!version) await api.post<Project>(`/projects/${projectId}/promote`);
      // Сбрасываем кеш списка проектов: «Код» загрузит его заново уже с этим проектом.
      qc.removeQueries({ queryKey: ["projects"] });
      router.push(`/code?project=${projectId}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось передать макет в Код");
    } finally { setBusy(false); }
  }

  const visibleDesigns = designs.filter(d => versionLabel(d).toLowerCase().includes(listQuery.trim().toLowerCase()));
  const orderedDesigns = [...visibleDesigns].sort((a, b) => Number(pins.includes(b.id)) - Number(pins.includes(a.id)));
  const activeId = source.kind === "design" ? source.id : "chat-files";
  const designRows = [
    { id: "chat-files", title: "Файлы чата", subtitle: page?.name || "пока пусто", pinned: pins.includes("chat-files"), updatedAt: live.data ? undefined : null },
    ...orderedDesigns.map(d => ({
      id: d.id, title: versionLabel(d), subtitle: d.stack, pinned: pins.includes(d.id), done: !!d.project_id, updatedAt: d.updated_at,
      working: !!(liveJob.data && isActive(liveJob.data) && String(liveJob.data.result?.design_id || orderedDesigns[0]?.id || "") === d.id),
    })),
  ];
  useListKeys(folderIds(designRows), activeId, id => {
    if (id === "chat-files") { choose({ kind: "chat" }); setChatOpen(true); }
    else choose({ kind: "design", id });
  }, () => { setChatOpen(true); window.dispatchEvent(new CustomEvent("layla:new-chat", { detail: { domain: "design" } })); });

  return (
    <div className="flex h-full min-h-0 bg-black text-neutral-200">
      <WorkRail title="Версии" storageKey="layla:design:list" railOpen={chatOpen} onCloseRail={() => setChatOpen(false)} query={listQuery} onQuery={setListQuery} active={activeId}
        onOpen={id => { if (id === "chat-files") { choose({ kind: "chat" }); setChatOpen(true); } else choose({ kind: "design", id }); }}
        onCreate={() => setBriefOpen(v => !v)}
        rows={designRows}
        onPin={id => setPins(list => list.includes(id) ? list.filter(value => value !== id) : [...list, id])}
        onCopy={id => { const url = new URL(window.location.href); if (id !== "chat-files") url.searchParams.set("design", id); navigator.clipboard.writeText(url.toString()).catch(() => undefined); }}
        onRename={async (id, title) => {
          if (id === "chat-files") return;
          await api.patch(`/designs/${id}`, { title });
          await qc.invalidateQueries({ queryKey: ["designs"] });
        }}
        onDelete={id => { if (id !== "chat-files") void removeVersion(id); }}>
        <div className="border-b border-white/10">
          <button onClick={() => setBriefOpen(v => !v)} aria-expanded={briefOpen} className="flex w-full items-center gap-2 px-3 py-2 text-xs text-neutral-300">
            <Sparkles className="h-3.5 w-3.5" /><span className="flex-1 text-left">Бриф</span>
            <ChevronDown className={`h-3.5 w-3.5 ${briefOpen ? "rotate-180" : ""}`} />
          </button>
          {briefOpen && <div className="max-h-72 overflow-y-auto px-2 pb-2"><DesignBriefForm brief={brief} onChange={setBrief} stack={stack} onStack={setStack} model={model} onModel={setModel} models={models} pending={generate.isPending} onGenerate={() => generate.mutate()} /></div>}
          {error && <p role="alert" className="px-3 pb-2 text-xs text-red-300">{error}</p>}
        </div>
      </WorkRail>

      <div className="flex min-h-0 min-w-0 flex-1 flex-col">
          <div className="flex flex-wrap items-center gap-2 border-b border-white/10 px-3 py-2">
            <button className="secondary-button text-xs" onClick={openInCode} disabled={busy || (!version && !chatProject)}><Code2 className="h-4 w-4" />В Код</button>
            <button onClick={() => setChatOpen(v => !v)} className="ml-auto text-neutral-500 hover:text-white" aria-label="Чат"><PanelRight className="h-4 w-4" /></button>
          </div>
          <div className="flex flex-wrap items-center gap-2 border-b border-ink-700/60 px-4 py-3">
            <div className="flex gap-1">
              <ToolbarBtn active={view === "preview"} onClick={() => setView("preview")}><Eye className="h-3.5 w-3.5" /> Превью</ToolbarBtn>
              <ToolbarBtn active={view === "code"} onClick={() => setView("code")}><Code2 className="h-3.5 w-3.5" /> Код</ToolbarBtn>
              <ToolbarBtn active={view === "split"} label="Код и превью рядом" onClick={() => setView("split")}><Columns2 className="h-3.5 w-3.5" /><span className="hidden sm:inline">Вместе</span></ToolbarBtn>
            </div>
            {liveJob.data && !showLive && (
              <button onClick={() => setWatching(true)} className="flex items-center gap-1.5 rounded-lg bg-accent-500/15 px-2.5 py-1.5 text-xs text-accent-100 hover:bg-accent-500/25">
                {isActive(liveJob.data) && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                {isActive(liveJob.data) ? `Генерация · ${Math.round(liveJob.data.progress * 100)}%` : "Последняя генерация"}
              </button>
            )}
            <span className="flex min-w-0 items-center gap-1.5 px-2 py-1 text-xs text-neutral-400">
              <History className="h-3.5 w-3.5 shrink-0" />
              <span className="max-w-[14rem] truncate">{showLive ? "Генерация по брифу" : version ? versionLabel(version) : page ? `Файлы чата · ${page.name}` : "Файлы чата"}</span>
            </span>
            {designs.length > 1 && <button onClick={clearVersions} disabled={busy} className="px-2 py-1 text-xs text-red-300 hover:bg-red-500/10">Удалить все</button>}
            {view !== "code" && html && !showLive && (
              <button onClick={() => (picking || pickedEl ? stopPicking() : setPicking(true))} aria-pressed={picking || !!pickedEl}
                title="Нажмите на элемент в превью и опишите, что в нём изменить"
                className={`flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs ${picking || pickedEl ? "bg-accent-500/25 text-accent-100" : "bg-ink-900 text-neutral-300 hover:bg-ink-800"}`}>
                <MousePointerClick className="h-3.5 w-3.5" />Правка по клику
              </button>
            )}
            {view !== "code" && (
              <div className="ml-auto hidden gap-1 sm:flex">
                <ToolbarBtn label="Компьютер" active={bp === "desktop"} onClick={() => setBp("desktop")}><Monitor className="h-3.5 w-3.5" /></ToolbarBtn>
                <ToolbarBtn label="Планшет" active={bp === "tablet"} onClick={() => setBp("tablet")}><Tablet className="h-3.5 w-3.5" /></ToolbarBtn>
                <ToolbarBtn label="Телефон" active={bp === "mobile"} onClick={() => setBp("mobile")}><Smartphone className="h-3.5 w-3.5" /></ToolbarBtn>
              </div>
            )}
          </div>

          {showLive && liveJob.data ? (
            <div className="min-h-0 flex-1 overflow-hidden bg-ink-950/40">
              <DesignLive job={liveJob.data} view={view} width={BREAKPOINTS[bp]} stopping={stop.isPending}
                onStop={() => stop.mutate(liveJob.data!.id)}
                onResume={() => resume.mutate(liveJob.data!.id)} resuming={resume.isPending}
                onClose={() => { setLiveJobId(null); setWatching(false); }} />
            </div>
          ) : (
          <div className={`min-h-0 flex-1 bg-ink-950/40 ${view === "split" && html ? "overflow-hidden" : "overflow-auto p-4"}`}>
            {!html ? (
              <div className="grid h-full place-items-center p-4 text-center">
                <div className="max-w-sm">
                  <span className="empty-orb"><Palette className="h-6 w-6" /></span>
                  <h2 className="text-xl font-semibold">Каким будет ваш следующий проект?</h2>
                  <p className="mt-3 text-sm leading-7 text-neutral-400">
                    Заполните бриф для первого макета или просто опишите задачу в чате. Здесь появится живое превью,
                    а кнопка «Открыть в Коде» перенесёт результат в домен Код — дорабатывать его до сайта.
                  </p>
                </div>
              </div>
            ) : view === "preview" ? (
              <div className="mx-auto h-full bg-white" style={{ width: BREAKPOINTS[bp], maxWidth: "100%" }}>
                {/* Изолированный sandbox: скрипты выполняются, доступа к родителю нет. */}
                <PickFrame html={html} picking={picking} onPicked={el => { setPickedEl(el); setPicking(false); }} onCancel={stopPicking} />
              </div>
            ) : view === "code" ? (
              <pre className="whitespace-pre-wrap text-xs leading-relaxed text-neutral-300"><code>{html}</code></pre>
            ) : (
              <div className="grid h-full min-h-0 grid-rows-2 lg:grid-cols-2 lg:grid-rows-1">
                <div className="min-h-0 border-b border-ink-700/60 lg:border-b-0 lg:border-r"><CodeStream code={html} live={false} /></div>
                <div className="min-h-0 p-3">
                  <div className="mx-auto h-full bg-white" style={{ width: BREAKPOINTS[bp], maxWidth: "100%" }}>
                    <PickFrame html={html} picking={picking} onPicked={el => { setPickedEl(el); setPicking(false); }} onCancel={stopPicking} />
                  </div>
                </div>
              </div>
            )}
          </div>
          )}
          {!showLive && <PickBar picking={picking} element={pickedEl} onSend={sendPick} onCancel={stopPicking} busy={pickBusy} />}
      </div>
      {chatOpen && <aside className="ios-panel hidden w-[22rem] shrink-0 flex-col lg:flex">
        <ChatPanel domain="design" onProject={bindProject} onFileChange={refresh} />
      </aside>}
    </div>
  );
}

function ToolbarBtn({ active, onClick, children, label }: {
  active: boolean; label?: string; onClick: () => void; children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      aria-label={label}
      aria-pressed={active}
      className={`flex items-center gap-1 rounded px-2 py-1 text-xs ${active ? "bg-ink-700 text-white" : "text-neutral-400 hover:bg-ink-800"}`}
    >
      {children}
    </button>
  );
}
