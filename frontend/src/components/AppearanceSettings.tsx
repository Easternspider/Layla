"use client";

import { Type, Accessibility } from "lucide-react";
import { useAppearance } from "@/store/appearance";
import { AuroraBackdrop } from "@/components/AuroraBackdrop";

export function AppearanceSettings() {
  const { motion, setMotion } = useAppearance();
  return <div className="max-w-2xl">
    <h1>Внешний вид</h1>
    <p className="mb-7 text-sm text-neutral-400">Тёмная тема, ровные панели и ничего лишнего между вами и задачей.</p>
    <section className="mb-5">
      <div className="appearance-preview"><AuroraBackdrop /><span className="mb-4 inline-flex rounded-full bg-accent-500/10 px-3 py-1 text-xs text-accent-200">Ваше рабочее пространство</span><p className="appearance-preview-heading">От идеи — к результату.</p><p className="mt-2 max-w-sm text-sm leading-relaxed text-neutral-400">Чёрный фон, мягкий цветной свет за панелями и ровные серые поверхности. У каждого раздела — свой спокойный акцент.</p><div className="mt-5 flex gap-2" aria-label="Палитра">{["bg-ink-950", "bg-ink-800", "bg-accent-600", "bg-accent-300", "bg-domain-osint"].map(c => <span key={c} className={`h-8 flex-1 rounded-lg border border-neutral-300/20 ${c}`} />)}</div></div>
      <p className="mt-4 text-sm leading-relaxed text-neutral-400">Единое оформление чатов, проектов, инструментов и настроек во всех разделах.</p>
    </section>
    <section className="mb-5 flex items-start gap-3"><Type className="mt-1 h-5 w-5 shrink-0 text-accent-300" /><div><h2 className="font-semibold">Inter</h2><p className="mt-1 text-sm leading-relaxed text-neutral-400">Нейтральный шрифт с ровными буквами и поддержкой кириллицы. Для кода используется отдельный моноширинный шрифт.</p><p className="mt-5 text-xl">Привет, я Layla. Что создадим?</p></div></section>
    <section><label className="flex cursor-pointer items-start gap-3"><Accessibility className="mt-1 h-5 w-5 shrink-0 text-accent-300" /><span className="min-w-0 flex-1"><span className="block font-semibold">Плавные переходы</span><span className="mt-1 block text-sm leading-relaxed text-neutral-400">Плавное появление экранов и сообщений, мягкий свет за панелями и живые индикаторы задач. При отключении всё замирает. Системное уменьшение движения всегда учитывается.</span></span><input type="checkbox" checked={motion} onChange={e => setMotion(e.target.checked)} className="mt-1 h-5 w-5" /></label></section>
  </div>;
}
