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
          950: "#000000",
          900: "#1c1c1e",
          800: "#2c2c2e",
          700: "#3a3a3c",
          600: "#48484a",
        },
        neutral: {
          50: "#ffffff", 100: "#f2f2f7", 200: "#f2f2f7", 300: "#ebebf5",
          400: "#aeaeb2", 500: "#8e8e93", 600: "#636366", 700: "#48484a",
          800: "#3a3a3c", 900: "#1c1c1e", 950: "#000000",
        },
        accent: {
          50: "#e8f2ff", 100: "#cce4ff", 200: "#99c9ff", 300: "#66aeff",
          400: "#3d9bff", 500: "#0A84FF", 600: "#0A84FF", 700: "#0066cc",
          800: "#004999", 900: "#003366", 950: "#001a33",
        },
        domain: { code: "#0A84FF", pentest: "#0A84FF", osint: "#30D158", design: "#FF9F0A" },
      },
      borderRadius: {
        DEFAULT: "12px", sm: "8px", md: "10px", lg: "12px",
        xl: "14px", "2xl": "18px", "3xl": "22px",
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
