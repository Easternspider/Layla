"use client";

import { useEffect, useRef } from "react";

const LIGHTS = [
  { x: 0.18, y: 0.22, r: 0.55, color: [10, 132, 255], speed: 0.12 },
  { x: 0.78, y: 0.18, r: 0.42, color: [94, 92, 230], speed: 0.09 },
  { x: 0.72, y: 0.82, r: 0.5, color: [48, 209, 188], speed: 0.11 },
  { x: 0.28, y: 0.78, r: 0.38, color: [255, 159, 90], speed: 0.08 },
];

/** Slow silk light behind the workspace. Clicks pass through. */
export function AuroraBackdrop() {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const canvas = ref.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;
    let raf = 0;
    const reduced = () => document.documentElement.dataset.motion === "reduced" || window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const draw = (time: number) => {
      const width = canvas.clientWidth;
      const height = canvas.clientHeight;
      const scale = 0.45;
      if (canvas.width !== Math.max(1, Math.floor(width * scale)) || canvas.height !== Math.max(1, Math.floor(height * scale))) {
        canvas.width = Math.max(1, Math.floor(width * scale));
        canvas.height = Math.max(1, Math.floor(height * scale));
      }
      ctx.setTransform(scale, 0, 0, scale, 0, 0);
      ctx.globalCompositeOperation = "source-over";
      ctx.fillStyle = "#000";
      ctx.fillRect(0, 0, width, height);
      ctx.globalCompositeOperation = "screen";
      for (let index = 0; index < LIGHTS.length; index += 1) {
        const light = LIGHTS[index];
        const drift = reduced() ? 0 : time;
        const x = (light.x + Math.sin(drift * light.speed + index) * 0.16) * width;
        const y = (light.y + Math.cos(drift * light.speed * 0.85 + index * 1.6) * 0.14) * height;
        const radius = Math.max(width, height) * (light.r + Math.sin(drift * 0.2 + index) * 0.04);
        const glow = ctx.createRadialGradient(x, y, 0, x, y, radius);
        const [red, green, blue] = light.color;
        glow.addColorStop(0, `rgba(${red}, ${green}, ${blue}, 0.55)`);
        glow.addColorStop(0.42, `rgba(${red}, ${green}, ${blue}, 0.18)`);
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
