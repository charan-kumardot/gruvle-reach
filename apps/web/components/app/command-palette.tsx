"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Command } from "cmdk";
import {
  LayoutDashboard, Users, Landmark, Sparkles, Send, ListChecks, Search as SearchIcon,
} from "lucide-react";

const ACTIONS = [
  { label: "Find customers", href: "/customers", icon: Users, hint: "Discover new target accounts" },
  { label: "Find investors", href: "/investors", icon: Landmark, hint: "See investor matches" },
  { label: "Find opportunities", href: "/opportunities", icon: Sparkles, hint: "Browse the unified opportunity feed" },
  { label: "Create outreach", href: "/outreach", icon: Send, hint: "Draft a new outreach message" },
  { label: "View today's actions", href: "/actions", icon: ListChecks, hint: "Open the Daily Founder Brief" },
  { label: "Overview", href: "/overview", icon: LayoutDashboard, hint: "Go to dashboard" },
];

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const router = useRouter();

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((v) => !v);
      }
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, []);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[60] flex items-start justify-center bg-black/50 backdrop-blur-sm pt-[15vh]" onClick={() => setOpen(false)}>
      <div
        className="w-full max-w-lg overflow-hidden rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--surface-raised)]/95 backdrop-blur-xl shadow-2xl animate-fade-in"
        onClick={(e) => e.stopPropagation()}
      >
        <Command label="Command Menu" className="flex flex-col">
          <div className="flex items-center gap-2 border-b border-[var(--border)] px-4 py-3">
            <SearchIcon className="h-4 w-4 text-[var(--muted-foreground)]" />
            <Command.Input
              autoFocus
              placeholder="Find customers, investors, opportunities…"
              className="flex-1 bg-transparent text-sm outline-none placeholder:text-[var(--muted-foreground)]"
            />
          </div>
          <Command.List className="max-h-80 overflow-y-auto p-2">
            <Command.Empty className="px-2 py-6 text-center text-sm text-[var(--muted-foreground)]">No results found.</Command.Empty>
            {ACTIONS.map((action) => (
              <Command.Item
                key={action.href}
                onSelect={() => {
                  setOpen(false);
                  router.push(action.href);
                }}
                className="flex cursor-pointer items-center gap-3 rounded-[var(--radius-sm)] px-3 py-2 text-sm data-[selected=true]:bg-[var(--border-subtle)]"
              >
                <action.icon className="h-4 w-4 text-[var(--muted-foreground)]" />
                <div className="flex flex-col">
                  <span>{action.label}</span>
                  <span className="text-xs text-[var(--muted-foreground)]">{action.hint}</span>
                </div>
              </Command.Item>
            ))}
          </Command.List>
        </Command>
      </div>
    </div>
  );
}
