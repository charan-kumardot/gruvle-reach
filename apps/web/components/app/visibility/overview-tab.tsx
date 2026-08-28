"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RefreshCw, Search } from "lucide-react";
import { toast } from "sonner";
import { api, ApiError } from "@/lib/api-client";
import { useAppStore } from "@/lib/store";
import type { Website, WebsiteScan } from "@/lib/types";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
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

  const { data: scan, isLoading } = useQuery({
    queryKey: ["website-scan-latest", website.id],
    queryFn: () => api.get<WebsiteScan | null>(`/workspaces/${workspace!.id}/websites/${website.id}/scans/latest`),
    enabled: !!workspace,
  });

  const runScan = useMutation({
    mutationFn: () => api.post<WebsiteScan>(`/workspaces/${workspace!.id}/websites/${website.id}/scan`),
    onSuccess: () => {
      toast.success("Scan complete");
      queryClient.invalidateQueries({ queryKey: ["website-scan-latest", website.id] });
      queryClient.invalidateQueries({ queryKey: ["seo-issues", website.id] });
      queryClient.invalidateQueries({ queryKey: ["website-opportunities", website.id] });
    },
    onError: (err) => toast.error(err instanceof ApiError ? err.message : "Scan failed"),
  });

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium">{website.name}</p>
          <p className="text-xs text-[var(--muted-foreground)]">{website.url}</p>
        </div>
        <Button size="sm" onClick={() => runScan.mutate()} disabled={runScan.isPending}>
          <RefreshCw className={`mr-1.5 h-3.5 w-3.5 ${runScan.isPending ? "animate-spin" : ""}`} /> {runScan.isPending ? "Scanning…" : "Run scan"}
        </Button>
      </div>

      {isLoading ? (
        <p className="text-sm text-[var(--muted-foreground)]">Loading…</p>
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
    </div>
  );
}
