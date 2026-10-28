import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["var(--font-onest)", "Onest", "system-ui", "sans-serif"],
        mono: ['"SFMono-Regular"', "Consolas", '"Liberation Mono"', "monospace"],
      },
      colors: {
        ink: {
          950: "#0c101b",
          900: "#111624",
          800: "#1a2031",
          700: "#2a3349",
          600: "#3c4863",
        },
        neutral: {
          50: "#f8faff", 100: "#edf2fc", 200: "#e2e8f5", 300: "#c7d1e5",
          400: "#acb8d0", 500: "#96a4be", 600: "#8492ae", 700: "#4d5b76",
          800: "#283248", 900: "#151d2d", 950: "#0c101b",
        },
        accent: {
          50: "#f5f6f7", 100: "#e8eaed", 200: "#d4d7dc", 300: "#b8bcc4",
          400: "#9aa0a8", 500: "#7c828a", 600: "#5f656d", 700: "#484e55",
          800: "#343a40", 900: "#24282d", 950: "#16181b",
        },
        domain: { code: "#c8ccd2", pentest: "#d4d7dc", osint: "#b8bcc4", design: "#c8ccd2" },
      },
      borderRadius: {
        DEFAULT: "8px", sm: "6px", md: "8px", lg: "10px",
        xl: "12px", "2xl": "14px", "3xl": "16px",
      },
      boxShadow: {
        panel: "0 24px 80px -28px rgb(0 0 0 / 0.65), inset 0 1px 0 rgb(255 255 255 / 0.04)",
        floating: "0 16px 48px -18px rgb(0 0 0 / 0.65), inset 0 1px 0 rgb(255 255 255 / 0.06)",
      },
    },
  },
  plugins: [],
};
export default config;
