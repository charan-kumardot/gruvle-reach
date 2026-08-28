"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ExternalLink, GitBranch, ShieldCheck } from "lucide-react";
import { toast } from "sonner";
import { api, ApiError } from "@/lib/api-client";
import { useAppStore } from "@/lib/store";
import type { Website, WebsiteChange } from "@/lib/types";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { EmptyState } from "@/components/app/empty-state";
import { RiskBadge } from "@/components/app/visibility/risk-badge";

const STATUS_VARIANT: Record<string, "success" | "warning" | "danger" | "muted" | "default"> = {
  drafted: "muted", validated: "default", blocked: "danger", approved: "warning",
  branch_created: "warning", pr_created: "success", merged: "success", rejected: "danger",
};

export function ChangesTab({ website }: { website: Website }) {
  const workspace = useAppStore((s) => s.workspace);
  const queryClient = useQueryClient();
  const [prepareTarget, setPrepareTarget] = useState<WebsiteChange | null>(null);
  const [prTitle, setPrTitle] = useState("");

  const { data: changes } = useQuery({
    queryKey: ["website-changes", website.id],
    queryFn: () => api.get<WebsiteChange[]>(`/workspaces/${workspace!.id}/websites/${website.id}/changes`),
    enabled: !!workspace,
  });

  const approve = useMutation({
    mutationFn: (change: WebsiteChange) => api.post<WebsiteChange>(`/workspaces/${workspace!.id}/websites/${website.id}/changes/${change.id}/approve`),
    onSuccess: () => {
      toast.success("Approved");
      queryClient.invalidateQueries({ queryKey: ["website-changes", website.id] });
    },
    onError: (err) => toast.error(err instanceof ApiError ? err.message : "Approval failed"),
  });

  const prepare = useMutation({
    mutationFn: () =>
      api.post<WebsiteChange>(`/workspaces/${workspace!.id}/websites/${website.id}/changes/${prepareTarget!.id}/prepare`, { pr_title: prTitle }),
    onSuccess: () => {
      toast.success("Branch and pull request created — review and merge on GitHub when ready");
      setPrepareTarget(null);
      setPrTitle("");
      queryClient.invalidateQueries({ queryKey: ["website-changes", website.id] });
    },
    onError: (err) => toast.error(err instanceof ApiError ? err.message : "Failed to create branch/PR — is GitHub connected?"),
  });

  if (!changes || changes.length === 0) {
    return <EmptyState icon={GitBranch} title="No changes yet" description="Generate a proposal from the Opportunities tab to see it here." />;
  }

  return (
    <div className="flex flex-col gap-3">
      {changes.map((change) => (
        <Card key={change.id}>
          <CardContent className="p-4">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant={STATUS_VARIANT[change.status] ?? "muted"}>{change.status.replace(/_/g, " ")}</Badge>
                  <RiskBadge level={change.risk_level} />
                </div>
                <p className="mt-1.5 text-sm">{change.reason}</p>
                <p className="mt-1 text-xs text-[var(--muted-foreground)]">
                  {change.files_changed.map((f) => f.path).join(", ")}
                </p>
                {Object.keys(change.semantic_diff).length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1.5 text-[11px]">
                    <Badge variant="outline">Product meaning: {String(change.semantic_diff.product_meaning ?? "n/a")}</Badge>
                    <Badge variant="outline">UI: {String(change.semantic_diff.ui_impact ?? "n/a")}</Badge>
                    <Badge variant="outline">Brand: {String(change.semantic_diff.brand_alignment_score ?? "n/a")}/100</Badge>
                  </div>
                )}
                {change.pr_url && (
                  <a href={change.pr_url} target="_blank" rel="noreferrer" className="mt-2 inline-flex items-center gap-1 text-xs text-[var(--accent)] hover:underline">
                    <ExternalLink className="h-3 w-3" /> View pull request #{change.pr_number}
                  </a>
                )}
              </div>
              <div className="flex shrink-0 flex-col items-end gap-1.5">
                {change.status === "validated" && (change.risk_level === "low" || change.risk_level === "medium") && (
                  <Button size="sm" variant="secondary" onClick={() => approve.mutate(change)} disabled={approve.isPending}>
                    <ShieldCheck className="mr-1.5 h-3.5 w-3.5" /> Approve
                  </Button>
                )}
                {change.status === "validated" && (change.risk_level === "high" || change.risk_level === "critical") && (
                  <p className="max-w-40 text-right text-[11px] text-[var(--muted-foreground)]">
                    {change.risk_level === "high" ? "HIGH risk — make this change manually" : "Blocked"}
                  </p>
                )}
                {change.status === "approved" && (
                  <Button size="sm" onClick={() => { setPrepareTarget(change); setPrTitle(change.reason.slice(0, 60)); }}>
                    <GitBranch className="mr-1.5 h-3.5 w-3.5" /> Create branch + PR
                  </Button>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      ))}

      <Dialog open={!!prepareTarget} onOpenChange={(v) => !v && setPrepareTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create branch + pull request</DialogTitle>
            <DialogDescription>
              Opens a real branch and PR on GitHub. Reach never merges it — you review and merge on GitHub, and your
              existing deployment pipeline takes it from there.
            </DialogDescription>
          </DialogHeader>
          <form className="flex flex-col gap-3" onSubmit={(e) => { e.preventDefault(); prepare.mutate(); }}>
            <Input required value={prTitle} onChange={(e) => setPrTitle(e.target.value)} placeholder="PR title" />
            <Button type="submit" disabled={prepare.isPending}>{prepare.isPending ? "Creating…" : "Create branch + PR"}</Button>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
