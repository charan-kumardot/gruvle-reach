"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ListChecks, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { api, ApiError } from "@/lib/api-client";
import { useAppStore } from "@/lib/store";
import type { ActionItem, ActionStatus } from "@/lib/types";
import { PageHeader } from "@/components/app/page-header";
import { EmptyState } from "@/components/app/empty-state";
import { ActionCard } from "@/components/app/action-card";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";

export default function ActionsPage() {
  const { workspace, product } = useAppStore();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<ActionStatus>("today");

  const { data: actions, isLoading } = useQuery({
    queryKey: ["actions", workspace?.id, tab],
    queryFn: () => api.get<ActionItem[]>(`/workspaces/${workspace!.id}/actions?status=${tab}`),
    enabled: !!workspace,
  });

  const refresh = useMutation({
    mutationFn: () => api.post(`/workspaces/${workspace!.id}/actions/refresh?product_id=${product!.id}`),
    onSuccess: () => {
      toast.success("Actions refreshed from latest research");
      queryClient.invalidateQueries({ queryKey: ["actions"] });
    },
    onError: (err) => toast.error(err instanceof ApiError ? err.message : "Refresh failed"),
  });

  if (!product) {
    return <EmptyState icon={ListChecks} title="Select a product" description="Choose a product to see its action center." />;
  }

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="Actions"
        description="Every recommendation, with why, evidence, impact, and effort."
        action={
          <Button size="sm" variant="secondary" onClick={() => refresh.mutate()} disabled={refresh.isPending}>
            <RefreshCw className={`mr-1.5 h-3.5 w-3.5 ${refresh.isPending ? "animate-spin" : ""}`} /> Refresh
          </Button>
        }
      />

      <Tabs value={tab} onValueChange={(v) => setTab(v as ActionStatus)} className="mb-4">
        <TabsList>
          <TabsTrigger value="today">Today</TabsTrigger>
          <TabsTrigger value="upcoming">Upcoming</TabsTrigger>
          <TabsTrigger value="waiting">Waiting</TabsTrigger>
          <TabsTrigger value="completed">Completed</TabsTrigger>
        </TabsList>
      </Tabs>

      {isLoading ? (
        <p className="text-sm text-[var(--muted-foreground)]">Loading…</p>
      ) : actions && actions.length > 0 ? (
        <div className="flex flex-col gap-3">
          {actions.map((a, idx) => (
            <ActionCard key={a.id} action={a} index={idx + 1} />
          ))}
        </div>
      ) : (
        <EmptyState icon={ListChecks} title="Nothing here" description="Refresh to pull in the latest recommendations from research, investor matching, and competitor watch." action={<Button size="sm" onClick={() => refresh.mutate()}>Refresh</Button>} />
      )}
    </div>
  );
}
