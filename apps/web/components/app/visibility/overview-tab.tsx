"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, RefreshCw, Search } from "lucide-react";
import { toast } from "sonner";
import { api, ApiError } from "@/lib/api-client";
import { useAppStore } from "@/lib/store";
import type { Website, WebsiteScan } from "@/lib/types";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { EmptyState } from "@/components/app/empty-state";

const SCORE_LABELS: Record<string, string> = {
  overall: "Overall Visibility",
  seo: "SEO",
  geo: "GEO / AI Visibility",
  technical: "Technical Health",
  content: "Content Coverage",
  brand_clarity: "Brand Clarity",
};

export function OverviewTab({ website }: { website: Website }) {
  const workspace = useAppStore((s) => s.workspace);
  const queryClient = useQueryClient();
  const [editOpen, setEditOpen] = useState(false);
  const [editForm, setEditForm] = useState({ name: website.name, url: website.url });

  const { data: scan, isLoading } = useQuery({
    queryKey: ["website-scan-latest", website.id],
    queryFn: () => api.get<WebsiteScan | null>(`/workspaces/${workspace!.id}/websites/${website.id}/scans/latest`),
    enabled: !!workspace,
  });

  const runScan = useMutation({
    mutationFn: () => api.post<WebsiteScan>(`/workspaces/${workspace!.id}/websites/${website.id}/scan`),
    onSuccess: (result) => {
      if (result.status === "failed") {
        toast.error("Scan failed — the URL couldn't be fetched. Check it's correct and reachable.");
      } else {
        toast.success("Scan complete");
      }
      queryClient.invalidateQueries({ queryKey: ["website-scan-latest", website.id] });
      queryClient.invalidateQueries({ queryKey: ["seo-issues", website.id] });
      queryClient.invalidateQueries({ queryKey: ["website-opportunities", website.id] });
    },
    onError: (err) => toast.error(err instanceof ApiError ? err.message : "Scan failed"),
  });

  const saveEdit = useMutation({
    mutationFn: () => api.patch<Website>(`/workspaces/${workspace!.id}/websites/${website.id}`, editForm),
    onSuccess: () => {
      toast.success("Website updated");
      setEditOpen(false);
      queryClient.invalidateQueries({ queryKey: ["websites"] });
    },
    onError: (err) => toast.error(err instanceof ApiError ? err.message : "Failed to update"),
  });

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-1.5">
            <p className="text-sm font-medium">{website.name}</p>
            <button onClick={() => { setEditForm({ name: website.name, url: website.url }); setEditOpen(true); }} className="text-[var(--muted-foreground)] hover:text-[var(--accent)]">
              <Pencil className="h-3 w-3" />
            </button>
          </div>
          <p className="text-xs text-[var(--muted-foreground)]">{website.url}</p>
        </div>
        <Button size="sm" onClick={() => runScan.mutate()} disabled={runScan.isPending}>
          <RefreshCw className={`mr-1.5 h-3.5 w-3.5 ${runScan.isPending ? "animate-spin" : ""}`} /> {runScan.isPending ? "Scanning…" : "Run scan"}
        </Button>
      </div>

      {isLoading ? (
        <p className="text-sm text-[var(--muted-foreground)]">Loading…</p>
      ) : scan && scan.status === "failed" ? (
        <EmptyState
          icon={Search}
          title="Last scan failed"
          description="The URL couldn't be fetched — double-check it's correct (a typo'd scheme like httpt:// instead of https:// will fail silently otherwise) and reachable, then edit it above and re-scan."
          action={<Button size="sm" onClick={() => runScan.mutate()} disabled={runScan.isPending}>Try again</Button>}
        />
      ) : scan && scan.status === "completed" ? (
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-3">
          {Object.entries(SCORE_LABELS).map(([key, label]) => (
            <Card key={key}>
              <CardContent className="p-4">
                <p className="text-xs text-[var(--muted-foreground)]">{label}</p>
                <p className="mt-1 text-2xl font-semibold tabular-nums">{scan.summary_scores[key] ?? "–"}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <EmptyState
          icon={Search}
          title="No scan yet"
          description="Run a scan to analyze SEO, technical health, and content coverage — every finding is tagged VERIFIED, ESTIMATED, or UNKNOWN."
          action={<Button size="sm" onClick={() => runScan.mutate()}>Run scan</Button>}
        />
      )}

      {scan && scan.status === "completed" && (
        <Card>
          <CardContent className="p-4">
            <p className="mb-2 text-xs font-medium text-[var(--muted-foreground)]">Quick facts (from the last scan)</p>
            <div className="flex flex-wrap gap-2">
              <Badge variant="outline">Title: {String(scan.raw_result.title?.value ?? "missing")}</Badge>
              <Badge variant="outline">{scan.raw_result.https?.value ? "HTTPS" : "No HTTPS"}</Badge>
              <Badge variant="outline">{scan.raw_result.sitemap_present?.value ? "Has sitemap" : "No sitemap"}</Badge>
              <Badge variant="outline">{scan.raw_result.structured_data_present?.value ? "Has structured data" : "No structured data"}</Badge>
            </div>
          </CardContent>
        </Card>
      )}

      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>Edit website</DialogTitle></DialogHeader>
          <form className="flex flex-col gap-3" onSubmit={(e) => { e.preventDefault(); saveEdit.mutate(); }}>
            <div className="flex flex-col gap-1.5">
              <Label>Name</Label>
              <Input required value={editForm.name} onChange={(e) => setEditForm({ ...editForm, name: e.target.value })} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label>URL</Label>
              <Input required value={editForm.url} onChange={(e) => setEditForm({ ...editForm, url: e.target.value })} placeholder="https://example.com" />
            </div>
            <Button type="submit" disabled={saveEdit.isPending}>{saveEdit.isPending ? "Saving…" : "Save"}</Button>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
