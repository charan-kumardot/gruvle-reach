"use client";

import { useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { api } from "@/lib/api-client";
import { useAppStore } from "@/lib/store";
import type { SEOIssue, Website } from "@/lib/types";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/app/empty-state";

const IMPACT_VARIANT: Record<string, "success" | "warning" | "danger"> = { low: "success", medium: "warning", high: "danger" };

export function SEOTab({ website }: { website: Website }) {
  const workspace = useAppStore((s) => s.workspace);

  const { data: issues } = useQuery({
    queryKey: ["seo-issues", website.id],
    queryFn: () => api.get<SEOIssue[]>(`/workspaces/${workspace!.id}/websites/${website.id}/seo-issues`),
    enabled: !!workspace,
  });

  if (!issues || issues.length === 0) {
    return <EmptyState icon={Search} title="No SEO issues found yet" description="Run a scan from the Overview tab to detect issues." />;
  }

  return (
    <div className="flex flex-col gap-2">
      {issues.map((issue) => (
        <Card key={issue.id}>
          <CardContent className="p-4">
            <div className="flex items-center gap-2">
              <Badge variant={IMPACT_VARIANT[issue.impact] ?? "muted"}>{issue.impact} impact</Badge>
              <span className="text-sm font-medium">{issue.issue_type.replace(/_/g, " ")}</span>
            </div>
            <p className="mt-1.5 text-xs text-[var(--muted-foreground)]">{issue.evidence}</p>
            {issue.recommendation && <p className="mt-1.5 text-xs text-[var(--accent)]">{issue.recommendation}</p>}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
