"use client";

import Link from "next/link";
import { Radar } from "lucide-react";
import { Button } from "@/components/ui/button";

export function MarketingNav() {
  return (
    <header className="sticky top-0 z-40 border-b border-[var(--border)]/60 bg-[var(--background)]/70 backdrop-blur-md">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
        <Link href="/" className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-[var(--radius-sm)] bg-[var(--accent)] text-[var(--accent-foreground)]">
            <Radar className="h-4 w-4" />
          </div>
          <span className="text-sm font-semibold tracking-tight">Gruvle Reach</span>
        </Link>
        <nav className="hidden items-center gap-6 text-sm text-[var(--muted-foreground)] md:flex">
          <a href="#how-it-works" className="hover:text-[var(--foreground)]">How it works</a>
          <a href="#evidence" className="hover:text-[var(--foreground)]">Evidence</a>
          <a href="#integrations" className="hover:text-[var(--foreground)]">Integrations</a>
          <a href="#pricing" className="hover:text-[var(--foreground)]">Pricing</a>
          <a href="#faq" className="hover:text-[var(--foreground)]">FAQ</a>
        </nav>
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" asChild>
            <Link href="/login">Sign in</Link>
          </Button>
          <Button size="sm" asChild>
            <Link href="/register">Build my growth map</Link>
          </Button>
        </div>
      </div>
    </header>
  );
}
