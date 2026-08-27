"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Check, Clock3, Zap } from "lucide-react";
import { api } from "@/lib/api-client";
import { useAppStore } from "@/lib/store";
import type { ActionItem } from "@/lib/types";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

const CATEGORY_LABEL: Record<string, string> = {
  customer: "Customer",
  investor: "Investor",
  marketing: "Marketing",
  content: "Content",
  competitor: "Competitor",
  launch: "Launch",
};

const IMPACT_VARIANT: Record<string, "success" | "warning" | "muted"> = {
  high: "success",
  medium: "warning",
  low: "muted",
};

export function ActionCard({ action, index }: { action: ActionItem; index: number }) {
  const workspace = useAppStore((s) => s.workspace);
  const queryClient = useQueryClient();

  const complete = useMutation({
    mutationFn: () => api.post(`/workspaces/${workspace!.id}/actions/${action.id}/complete`),
    onSuccess: () => {
      toast.success("Marked complete");
      queryClient.invalidateQueries({ queryKey: ["daily-brief"] });
    },
  });

  const approve = useMutation({
    mutationFn: () => api.post(`/workspaces/${workspace!.id}/actions/${action.id}/approve`),
    onSuccess: () => {
      toast.success("Approved");
      queryClient.invalidateQueries({ queryKey: ["daily-brief"] });
    },
  });

  return (
    <Card className="animate-fade-in">
      <CardContent className="p-4">
        <div className="flex items-start gap-3">
          <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[var(--border-subtle)] text-xs font-semibold text-[var(--muted-foreground)]">
            {String(index).padStart(2, "0")}
          </span>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <p className="text-sm font-medium">{action.title}</p>
              <Badge variant="outline">{CATEGORY_LABEL[action.category] ?? action.category}</Badge>
              <Badge variant={IMPACT_VARIANT[action.impact] ?? "muted"}>{action.impact} impact</Badge>
            </div>
            {action.why && <p className="mt-1.5 text-xs text-[var(--muted-foreground)]">{action.why}</p>}
            <div className="mt-2 flex items-center gap-3 text-[11px] text-[var(--muted-foreground)]">
              <span className="flex items-center gap-1"><Zap className="h-3 w-3" /> {action.effort} effort</span>
              {action.evidence_ids.length > 0 && (
                <span className="flex items-center gap-1"><Clock3 className="h-3 w-3" /> {action.evidence_ids.length} evidence source{action.evidence_ids.length !== 1 ? "s" : ""}</span>
              )}
            </div>
          </div>
          <div className="flex shrink-0 gap-1.5">
            {action.requires_approval && (
              <Button size="sm" variant="secondary" onClick={() => approve.mutate()} disabled={approve.isPending}>
                Approve
              </Button>
            )}
            <Button size="sm" variant="ghost" onClick={() => complete.mutate()} disabled={complete.isPending}>
              <Check className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
