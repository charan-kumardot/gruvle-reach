"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAppStore, useHasHydrated } from "@/lib/store";
import { useBootstrap } from "@/lib/hooks";
import { Sidebar } from "@/components/app/sidebar";
import { Topbar } from "@/components/app/topbar";
import { CommandPalette } from "@/components/app/command-palette";
import { Radar } from "lucide-react";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const token = useAppStore((s) => s.token);
  const hydrated = useHasHydrated();
  const { products, ready } = useBootstrap();

  useEffect(() => {
    if (hydrated && !token) router.replace("/login");
  }, [hydrated, token, router]);

  if (!hydrated || !token) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Radar className="h-6 w-6 animate-pulse text-[var(--muted-foreground)]" />
      </div>
    );
  }

  if (!ready) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="flex flex-col items-center gap-3 text-[var(--muted-foreground)]">
          <Radar className="h-6 w-6 animate-pulse" />
          <span className="text-sm">Loading your workspace…</span>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar products={products} />
        <main className="flex-1 overflow-y-auto p-6">{children}</main>
      </div>
      <CommandPalette />
    </div>
  );
}
