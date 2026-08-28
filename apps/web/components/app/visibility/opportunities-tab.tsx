"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Sparkles, Wand2 } from "lucide-react";
import { toast } from "sonner";
import { api, ApiError } from "@/lib/api-client";
import { useAppStore } from "@/lib/store";
import type { Website, WebsiteChange, WebsiteOpportunity } from "@/lib/types";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { EmptyState } from "@/components/app/empty-state";

const IMPACT_VARIANT: Record<string, "success" | "warning" | "danger"> = { low: "success", medium: "warning", high: "danger" };

export function OpportunitiesTab({ website }: { website: Website }) {
  const workspace = useAppStore((s) => s.workspace);
  const queryClient = useQueryClient();
  const [target, setTarget] = useState<WebsiteOpportunity | null>(null);
  const [targetPath, setTargetPath] = useState("");

  const { data: opportunities } = useQuery({
    queryKey: ["website-opportunities", website.id],
    queryFn: () => api.get<WebsiteOpportunity[]>(`/workspaces/${workspace!.id}/websites/${website.id}/opportunities`),
    enabled: !!workspace,
  });

  const generate = useMutation({
    mutationFn: () =>
      api.post<WebsiteChange>(
        `/workspaces/${workspace!.id}/websites/${website.id}/opportunities/${target!.id}/generate-proposal`,
        { target_path: targetPath }
      ),
    onSuccess: (change) => {
      toast.success(change.status === "validated" ? "Proposal validated — review it in Website Changes" : "Proposal blocked — see reason in Website Changes");
      setTarget(null);
      setTargetPath("");
      queryClient.invalidateQueries({ queryKey: ["website-changes", website.id] });
      queryClient.invalidateQueries({ queryKey: ["website-opportunities", website.id] });
    },
    onError: (err) => toast.error(err instanceof ApiError ? err.message : "Failed to generate proposal"),
  });

  if (!opportunities || opportunities.length === 0) {
    return <EmptyState icon={Sparkles} title="No opportunities yet" description="Run a scan from the Overview tab — high/medium impact issues become opportunities here." />;
  }

  return (
    <div className="flex flex-col gap-3">
      {opportunities.map((o) => (
        <Card key={o.id}>
          <CardContent className="p-4">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <p className="text-sm font-medium">{o.title}</p>
                  <Badge variant={IMPACT_VARIANT[o.impact] ?? "muted"}>{o.impact} impact</Badge>
                  <Badge variant="outline">{o.status}</Badge>
                </div>
                <p className="mt-1.5 text-xs text-[var(--muted-foreground)]">{o.description}</p>
              </div>
              {o.status === "open" && (
                <Button size="sm" onClick={() => setTarget(o)}>
                  <Wand2 className="mr-1.5 h-3.5 w-3.5" /> Generate Proposal
                </Button>
              )}
            </div>
          </CardContent>
        </Card>
      ))}

      <Dialog open={!!target} onOpenChange={(v) => !v && setTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Generate proposal</DialogTitle>
            <DialogDescription>
              Gruvle Reach will draft a minimal, targeted fix and validate it against your Product Truth and risk
              rules before anything can become a pull request. Specify the source file to edit (or leave blank to
              try common locations for your detected framework).
            </DialogDescription>
          </DialogHeader>
          <form className="flex flex-col gap-3" onSubmit={(e) => { e.preventDefault(); generate.mutate(); }}>
            <div className="flex flex-col gap-1.5">
              <Label>Target file path (optional)</Label>
              <Input value={targetPath} onChange={(e) => setTargetPath(e.target.value)} placeholder="app/layout.tsx" />
            </div>
            <Button type="submit" disabled={generate.isPending}>{generate.isPending ? "Generating…" : "Generate proposal"}</Button>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
