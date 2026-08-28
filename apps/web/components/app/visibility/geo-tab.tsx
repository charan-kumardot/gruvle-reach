"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Eye, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { api, ApiError } from "@/lib/api-client";
import { useAppStore } from "@/lib/store";
import type { VisibilityQuestion, Website } from "@/lib/types";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/app/empty-state";

export function GEOTab({ website }: { website: Website }) {
  const workspace = useAppStore((s) => s.workspace);
  const queryClient = useQueryClient();

  const { data: questions } = useQuery({
    queryKey: ["visibility-questions", website.id],
    queryFn: () => api.get<VisibilityQuestion[]>(`/workspaces/${workspace!.id}/websites/${website.id}/visibility-questions`),
    enabled: !!workspace,
  });

  const runGeoScan = useMutation({
    mutationFn: () => api.post<VisibilityQuestion[]>(`/workspaces/${workspace!.id}/websites/${website.id}/geo-scan`),
    onSuccess: () => {
      toast.success("GEO scan complete");
      queryClient.invalidateQueries({ queryKey: ["visibility-questions", website.id] });
    },
    onError: (err) => toast.error(err instanceof ApiError ? err.message : "Run a scan first, then try again"),
  });

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <p className="text-xs text-[var(--muted-foreground)] max-w-md">
          Self-assessment against your own site content — not a live query against any external AI platform&apos;s ranking.
        </p>
        <Button size="sm" onClick={() => runGeoScan.mutate()} disabled={runGeoScan.isPending}>
          <RefreshCw className={`mr-1.5 h-3.5 w-3.5 ${runGeoScan.isPending ? "animate-spin" : ""}`} /> Run GEO scan
        </Button>
      </div>

      {questions && questions.length > 0 ? (
        <div className="flex flex-col gap-2">
          {questions.map((q) => (
            <Card key={q.id}>
              <CardContent className="p-4">
                <div className="flex items-center gap-2">
                  <Badge variant={q.coverage_status === "mentioned" ? "success" : "danger"}>
                    {q.coverage_status === "mentioned" ? "Mentioned" : "Not detected"}
                  </Badge>
                  <Badge variant="outline">{q.category.replace(/_/g, " ")}</Badge>
                </div>
                <p className="mt-1.5 text-sm">{q.question}</p>
                {q.evidence_snippet && <p className="mt-1 text-xs text-[var(--muted-foreground)]">&quot;{q.evidence_snippet}&quot;</p>}
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <EmptyState icon={Eye} title="No GEO check yet" description="Generates customer-style questions and checks whether your site's own content answers them." action={<Button size="sm" onClick={() => runGeoScan.mutate()}>Run GEO scan</Button>} />
      )}
    </div>
  );
}
