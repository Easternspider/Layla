"use client";

import { useEffect, useRef } from "react";

type Light = { x: number; y: number; r: number; speed: number; phase: number; mote?: boolean };

const LIGHTS: Light[] = [
  { x: 0.18, y: 0.22, r: 0.52, speed: 0.12, phase: 0.2 },
  { x: 0.78, y: 0.16, r: 0.4, speed: 0.09, phase: 1.4 },
  { x: 0.7, y: 0.82, r: 0.48, speed: 0.11, phase: 2.2 },
  { x: 0.26, y: 0.74, r: 0.34, speed: 0.08, phase: 0.8 },
  { x: 0.12, y: 0.48, r: 0.07, speed: 0.42, phase: 0.4, mote: true },
  { x: 0.58, y: 0.18, r: 0.05, speed: 0.55, phase: 1.1, mote: true },
  { x: 0.86, y: 0.46, r: 0.06, speed: 0.36, phase: 2.6, mote: true },
  { x: 0.4, y: 0.88, r: 0.05, speed: 0.48, phase: 1.8, mote: true },
  { x: 0.33, y: 0.36, r: 0.04, speed: 0.62, phase: 3.1, mote: true },
];

const PALETTES: Record<string, [number, number, number][]> = {
  code: [[10, 132, 255], [94, 92, 230], [48, 209, 188], [120, 170, 255]],
  pentest: [[255, 69, 58], [255, 159, 10], [191, 90, 242], [255, 55, 95]],
  osint: [[48, 209, 88], [100, 210, 255], [48, 209, 188], [10, 132, 255]],
  design: [[191, 90, 242], [255, 55, 95], [90, 200, 250], [255, 159, 10]],
  agent: [[255, 159, 10], [10, 132, 255], [48, 209, 88], [94, 92, 230]],
  settings: [[10, 132, 255], [142, 142, 147], [48, 209, 188], [94, 92, 230]],
  login: [[10, 132, 255], [191, 90, 242], [48, 209, 188], [255, 159, 10]],
};

/** Slow silk light behind the workspace. Clicks pass through. Color follows the open section. */
export function AuroraBackdrop() {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const canvas = ref.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;
    let raf = 0;
    const reduced = () => document.documentElement.dataset.motion === "reduced" || window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const paletteFor = () => {
      const host = canvas.closest("[data-domain]") as HTMLElement | null;
      const key = host?.dataset.domain || (canvas.closest(".login-shell") ? "login" : "code");
      return PALETTES[key] || PALETTES.code;
    };
    const draw = (time: number) => {
      const width = canvas.clientWidth;
      const height = canvas.clientHeight;
      const scale = 0.45;
      if (canvas.width !== Math.max(1, Math.floor(width * scale)) || canvas.height !== Math.max(1, Math.floor(height * scale))) {
        canvas.width = Math.max(1, Math.floor(width * scale));
        canvas.height = Math.max(1, Math.floor(height * scale));
      }
      const palette = paletteFor();
      ctx.setTransform(scale, 0, 0, scale, 0, 0);
      ctx.globalCompositeOperation = "source-over";
      ctx.fillStyle = "#000";
      ctx.fillRect(0, 0, width, height);
      ctx.globalCompositeOperation = "screen";
      for (let index = 0; index < LIGHTS.length; index += 1) {
        const light = LIGHTS[index];
        const drift = reduced() ? 0 : time;
        const travel = light.mote ? 0.22 : 0.16;
        const x = (light.x + Math.sin(drift * light.speed + light.phase) * travel) * width;
        const y = (light.y + Math.cos(drift * light.speed * 0.85 + light.phase) * (light.mote ? 0.18 : 0.12)) * height;
        const radius = Math.max(width, height) * (light.r + Math.sin(drift * (light.mote ? 0.8 : 0.2) + light.phase) * (light.mote ? 0.015 : 0.04));
        const [red, green, blue] = palette[index % palette.length];
        const glow = ctx.createRadialGradient(x, y, 0, x, y, radius);
        const core = light.mote ? 0.28 + Math.max(0, Math.sin(drift * 1.6 + light.phase)) * 0.55 : 0.5;
        glow.addColorStop(0, `rgba(${red}, ${green}, ${blue}, ${core})`);
        glow.addColorStop(light.mote ? 0.35 : 0.42, `rgba(${red}, ${green}, ${blue}, ${light.mote ? 0.05 : 0.16})`);
        glow.addColorStop(1, `rgba(${red}, ${green}, ${blue}, 0)`);
        ctx.fillStyle = glow;
        ctx.beginPath();
        ctx.arc(x, y, radius, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.globalCompositeOperation = "source-over";
      if (!reduced()) raf = requestAnimationFrame(now => draw(now / 1000));
    };
    draw(reduced() ? 1.2 : performance.now() / 1000);
    const onResize = () => { if (reduced()) draw(1.2); };
    window.addEventListener("resize", onResize);
    return () => { cancelAnimationFrame(raf); window.removeEventListener("resize", onResize); };
  }, []);
  return <canvas ref={ref} className="aurora-backdrop" aria-hidden="true" />;
}
