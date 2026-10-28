import { ConfirmHost } from "@/components/ConfirmDialog";
import type { Metadata } from "next";
import { Onest } from "next/font/google";
import "../styles/globals.css";
import { Providers } from "./providers";

const onest = Onest({
  subsets: ["latin", "cyrillic"],
  display: "swap",
  variable: "--font-onest",
});

export const metadata: Metadata = {
  title: "Layla",
  description: "Мультидоменная ИИ-рабочая станция — Код · Пентест · OSINT · Дизайн",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru" className={onest.variable} suppressHydrationWarning>
      <body className={onest.className}>
        <Providers>{children}<ConfirmHost /></Providers>
      </body>
    </html>
  );
}