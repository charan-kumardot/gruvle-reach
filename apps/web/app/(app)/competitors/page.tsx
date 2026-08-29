"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Swords, Plus, RefreshCw, Search } from "lucide-react";
import { toast } from "sonner";
import { api, ApiError } from "@/lib/api-client";
import { useAppStore } from "@/lib/store";
import { usePollAfterAction } from "@/lib/hooks";
import type { Competitor, CompetitorChange } from "@/lib/types";
import { PageHeader } from "@/components/app/page-header";
import { EmptyState } from "@/components/app/empty-state";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";

const IMPACT_VARIANT: Record<string, "success" | "warning" | "danger"> = { low: "success", medium: "warning", high: "danger" };

export default function CompetitorsPage() {
  const { workspace, product } = useAppStore();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ name: "", website: "" });

  const { data: competitors } = useQuery({
    queryKey: ["competitors", workspace?.id],
    queryFn: () => api.get<Competitor[]>(`/workspaces/${workspace!.id}/competitors`),
    enabled: !!workspace,
  });

  const create = useMutation({
    mutationFn: () => api.post<Competitor>(`/workspaces/${workspace!.id}/competitors`, { ...form, product_id: product?.id }),
    onSuccess: () => {
      toast.success("Competitor added");
      setOpen(false);
      setForm({ name: "", website: "" });
      queryClient.invalidateQueries({ queryKey: ["competitors"] });
    },
    onError: (err) => toast.error(err instanceof ApiError ? err.message : "Failed to add competitor"),
  });

  // Runs in the background (app/core/background.py) — no synchronous
  // result, so poll the list for a bit until new competitors show up.
  const { polling, start: startPolling } = usePollAfterAction(() => queryClient.invalidateQueries({ queryKey: ["competitors"] }));

  const discover = useMutation({
    mutationFn: () => api.post<{ status: string }>(`/workspaces/${workspace!.id}/competitors/discover?product_id=${product?.id}`),
    onSuccess: () => {
      toast.success("Discovery started — new competitors will appear below over the next minute or so");
      startPolling();
    },
    onError: (err) => toast.error(err instanceof ApiError ? err.message : "Competitor discovery failed"),
  });

  if (!product) {
    return <EmptyState icon={Swords} title="Select a product" description="Choose a product to track competitors." />;
  }

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="Competitors"
        description="Public page changes, tracked and summarized."
        action={
          <div className="flex gap-2">
            <Button size="sm" variant="secondary" onClick={() => setOpen(true)}><Plus className="mr-1.5 h-4 w-4" /> Add competitor</Button>
            <Button size="sm" onClick={() => discover.mutate()} disabled={discover.isPending}>
              <Search className="mr-1.5 h-4 w-4" /> {discover.isPending ? "Starting…" : "Discover competitors"}
            </Button>
          </div>
        }
      />

      {polling && (
        <p className="mb-3 text-xs text-[var(--muted-foreground)]">Discovery running in the background — checking for new competitors…</p>
      )}

      {competitors && competitors.length > 0 ? (
        <div className="flex flex-col gap-3">
          {competitors.map((c) => (
            <CompetitorRow key={c.id} competitor={c} />
          ))}
        </div>
      ) : (
        <EmptyState icon={Swords} title="No competitors tracked yet" description="Discover competitors automatically from your product's category, or add one you already know by name." action={<Button size="sm" onClick={() => discover.mutate()} disabled={discover.isPending}>{discover.isPending ? "Starting…" : "Discover competitors"}</Button>} />
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>Add competitor</DialogTitle></DialogHeader>
          <form className="flex flex-col gap-3" onSubmit={(e) => { e.preventDefault(); create.mutate(); }}>
            <div className="flex flex-col gap-1.5">
              <Label>Name</Label>
              <Input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Datadog" />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label>Website</Label>
              <Input required value={form.website} onChange={(e) => setForm({ ...form, website: e.target.value })} placeholder="https://www.datadoghq.com" />
            </div>
            <Button type="submit" disabled={create.isPending}>{create.isPending ? "Adding…" : "Add competitor"}</Button>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function CompetitorRow({ competitor }: { competitor: Competitor }) {
  const workspace = useAppStore((s) => s.workspace);
  const queryClient = useQueryClient();
  const [expanded, setExpanded] = useState(false);

  const { data: changes } = useQuery({
    queryKey: ["competitor-changes", competitor.id],
    queryFn: () => api.get<CompetitorChange[]>(`/workspaces/${workspace!.id}/competitors/${competitor.id}/changes`),
    enabled: expanded && !!workspace,
  });

  const scan = useMutation({
    mutationFn: () => api.post(`/workspaces/${workspace!.id}/competitors/${competitor.id}/scan`),
    onSuccess: (result) => {
      toast.success(result ? "Change detected" : "No changes since last scan");
      queryClient.invalidateQueries({ queryKey: ["competitor-changes", competitor.id] });
    },
    onError: (err) => toast.error(err instanceof ApiError ? err.message : "Scan failed"),
  });

  return (
    <Card>
      <CardContent className="p-4">
        <div className="flex items-center justify-between">
          <div className="cursor-pointer" onClick={() => setExpanded((v) => !v)}>
            <p className="text-sm font-medium">{competitor.name}</p>
            <p className="text-xs text-[var(--muted-foreground)]">{competitor.website}</p>
          </div>
          <Button size="sm" variant="secondary" onClick={() => scan.mutate()} disabled={scan.isPending}>
            <RefreshCw className={`mr-1.5 h-3.5 w-3.5 ${scan.isPending ? "animate-spin" : ""}`} /> Scan now
          </Button>
        </div>
        {expanded && (
          <div className="mt-3 border-t border-[var(--border)] pt-3">
            {changes && changes.length > 0 ? (
              <div className="flex flex-col gap-2">
                {changes.map((c) => (
                  <div key={c.id} className="rounded-[var(--radius-sm)] bg-[var(--border-subtle)] p-2.5">
                    <div className="flex items-center gap-2">
                      <Badge variant={IMPACT_VARIANT[c.potential_impact] ?? "muted"}>{c.potential_impact} impact</Badge>
                      <Badge variant="outline">{c.change_type}</Badge>
                    </div>
                    <p className="mt-1.5 text-xs">{c.description}</p>
                    <p className="mt-1 text-[11px] text-[var(--muted-foreground)]">{c.recommended_response}</p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-[var(--muted-foreground)]">No changes detected yet.</p>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
