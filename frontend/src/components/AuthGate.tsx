"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/store/auth";

// Клиентский гейт: запрашивает /me при монтировании и перенаправляет на /login,
// если пользователь не аутентифицирован. Ошибка сети не оставляет экран в вечной
// загрузке и не маскируется под «нет сессии».
export function AuthGate({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { user, loaded, loading, error, fetchMe } = useAuth();

  useEffect(() => {
    if (!loaded) fetchMe();
  }, [loaded, fetchMe]);

  useEffect(() => {
    if (loaded && !loading && !user && !error) router.replace("/login");
  }, [loaded, loading, user, error, router]);

  if (!loaded || (loading && !user)) {
    return (
      <div className="grid h-screen place-items-center text-sm text-neutral-500">
        Загрузка Layla…
      </div>
    );
  }
  if (error && !user) {
    return (
      <div className="grid h-screen place-items-center px-6 text-center text-sm text-neutral-400">
        <div className="max-w-sm space-y-3">
          <p>Не удалось связаться с Layla.</p>
          <p className="text-neutral-500">{error}</p>
          <button type="button" className="primary-button" onClick={() => void fetchMe()}>
            Повторить
          </button>
        </div>
      </div>
    );
  }
  if (!user) return null;
  return <>{children}</>;
}
