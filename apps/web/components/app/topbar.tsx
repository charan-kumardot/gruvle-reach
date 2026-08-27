"use client";

import { useRouter } from "next/navigation";
import { Command, ChevronDown, LogOut } from "lucide-react";
import { useAppStore } from "@/lib/store";
import type { Product } from "@/lib/types";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuLabel,
} from "@/components/ui/dropdown-menu";

export function Topbar({ products }: { products: Product[] }) {
  const router = useRouter();
  const { userEmail, product, workspace, setProduct, logout } = useAppStore();

  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-[var(--border)] bg-[var(--surface)]/60 backdrop-blur-sm px-5">
      <div className="flex items-center gap-3">
        {products.length > 0 && (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="secondary" size="sm" className="gap-1.5">
                {product?.name ?? "Select product"}
                <ChevronDown className="h-3.5 w-3.5 opacity-60" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start">
              <DropdownMenuLabel>{workspace?.name}</DropdownMenuLabel>
              <DropdownMenuSeparator />
              {products.map((p) => (
                <DropdownMenuItem key={p.id} onSelect={() => setProduct(p)}>
                  {p.name}
                  {p.is_demo && <span className="ml-1.5 text-[10px] text-[var(--muted-foreground)]">DEMO</span>}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        )}
      </div>

      <div className="flex items-center gap-2">
        <Button variant="outline" size="sm" className="gap-1.5 text-[var(--muted-foreground)]" onClick={() => document.dispatchEvent(new KeyboardEvent("keydown", { key: "k", metaKey: true }))}>
          <Command className="h-3.5 w-3.5" /> <span className="hidden sm:inline">Search</span>
          <kbd className="hidden sm:inline rounded border border-[var(--border)] bg-[var(--border-subtle)] px-1 text-[10px]">⌘K</kbd>
        </Button>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button className="rounded-full outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]">
              <Avatar>
                <AvatarFallback>{userEmail?.[0]?.toUpperCase() ?? "?"}</AvatarFallback>
              </Avatar>
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuLabel className="max-w-48 truncate">{userEmail}</DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              onSelect={() => {
                logout();
                router.push("/login");
              }}
              className="text-[var(--danger)]"
            >
              <LogOut className="mr-2 h-4 w-4" /> Sign out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
