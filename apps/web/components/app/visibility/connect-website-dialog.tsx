"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api, ApiError } from "@/lib/api-client";
import { useAppStore } from "@/lib/store";
import type { Website } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";

export function ConnectWebsiteDialog({ open, onOpenChange, onConnected }: { open: boolean; onOpenChange: (v: boolean) => void; onConnected: (w: Website) => void }) {
  const { workspace, product } = useAppStore();
  const queryClient = useQueryClient();
  const [form, setForm] = useState({ name: "", url: "", repository_owner: "", repository_name: "", default_branch: "main" });

  const create = useMutation({
    mutationFn: () => api.post<Website>(`/workspaces/${workspace!.id}/websites`, { ...form, product_id: product?.id }),
    onSuccess: (website) => {
      toast.success("Website connected");
      onOpenChange(false);
      queryClient.invalidateQueries({ queryKey: ["websites"] });
      onConnected(website);
    },
    onError: (err) => toast.error(err instanceof ApiError ? err.message : "Failed to connect website"),
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add website</DialogTitle>
          <DialogDescription>
            Connect a website and its GitHub repository. Reach will scan it, find opportunities, and prepare pull
            requests for you to review — it never pushes to your default branch directly.
          </DialogDescription>
        </DialogHeader>
        <form className="flex flex-col gap-3" onSubmit={(e) => { e.preventDefault(); create.mutate(); }}>
          <div className="flex flex-col gap-1.5">
            <Label>Name</Label>
            <Input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Gruvle Radar site" />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Website URL</Label>
            <Input required value={form.url} onChange={(e) => setForm({ ...form, url: e.target.value })} placeholder="https://gruvle.com" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label>Repo owner</Label>
              <Input value={form.repository_owner} onChange={(e) => setForm({ ...form, repository_owner: e.target.value })} placeholder="my-org" />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label>Repo name</Label>
              <Input value={form.repository_name} onChange={(e) => setForm({ ...form, repository_name: e.target.value })} placeholder="my-site" />
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Default branch</Label>
            <Input value={form.default_branch} onChange={(e) => setForm({ ...form, default_branch: e.target.value })} placeholder="main" />
          </div>
          <p className="text-xs text-[var(--muted-foreground)]">
            Connect GitHub in Settings → Integrations to enable branch/PR preparation. Scanning works without it.
          </p>
          <Button type="submit" disabled={create.isPending}>{create.isPending ? "Connecting…" : "Connect website"}</Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}
