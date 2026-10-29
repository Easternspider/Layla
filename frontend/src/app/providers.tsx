"use client";

import { MutationCache, QueryCache, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useEffect, useState, type ReactNode } from "react";
import { ApiError } from "@/lib/api";
import { useAppearance } from "@/store/appearance";
import { useAuth } from "@/store/auth";

function sessionDead(error: unknown) {
  if (!(error instanceof ApiError) || error.status !== 401) return;
  const hadUser = useAuth.getState().user != null;
  useAuth.setState({ user: null, loaded: true, error: null });
  if (hadUser && typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
    window.location.replace("/login");
  }
}

export function Providers({ children }: { children: ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        queryCache: new QueryCache({ onError: sessionDead }),
        mutationCache: new MutationCache({ onError: sessionDead }),
        defaultOptions: {
          queries: {
            retry: (failureCount, error) => {
              if (error instanceof ApiError && (error.status === 401 || error.status === 403 || error.status === 404)) {
                return false;
              }
              return failureCount < 3;
            },
          },
        },
      }),
  );
  const applyAppearance = useAppearance(s => s.apply);
  useEffect(() => { applyAppearance(); }, [applyAppearance]);
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
