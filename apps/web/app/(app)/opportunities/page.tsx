"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Sparkles } from "lucide-react";
import { toast } from "sonner";
import { api, ApiError } from "@/lib/api-client";
import { useAppStore } from "@/lib/store";
import type { Opportunity, OpportunityType } from "@/lib/types";
import { PageHeader } from "@/components/app/page-header";
import { EmptyState } from "@/components/app/empty-state";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

const TYPES: { value: OpportunityType | "all"; label: string }[] = [
  { value: "all", label: "All" },
  { value: "customer", label: "Customer" },
  { value: "investor", label: "Investor" },
  { value: "marketing", label: "Marketing" },
  { value: "launch", label: "Launch" },
  { value: "community", label: "Community" },
  { value: "content", label: "Content" },
  { value: "partnership", label: "Partnership" },
  { value: "media", label: "Media" },
  { value: "event", label: "Event" },
  { value: "seo", label: "SEO" },
  { value: "geo", label: "GEO" },
  { value: "ai_visibility", label: "AI Visibility" },
  { value: "competitor", label: "Competitor" },
  { value: "social", label: "Social" },
  { value: "grant", label: "Grant" },
  { value: "accelerator", label: "Accelerator" },
  { value: "podcast", label: "Podcast" },
  { value: "newsletter", label: "Newsletter" },
  { value: "other", label: "Other" },
];

export default function OpportunitiesPage() {
  const { workspace, product } = useAppStore();
  const queryClient = useQueryClient();
  const [filter, setFilter] = useState<OpportunityType | "all">("all");

  const { data: opportunities } = useQuery({
    queryKey: ["opportunities", workspace?.id, filter],
    queryFn: () =>
      api.get<Opportunity[]>(
        `/workspaces/${workspace!.id}/opportunities${filter !== "all" ? `?type=${filter}` : ""}`
      ),
    enabled: !!workspace,
  });

  const discoverMarketing = useMutation({
    mutationFn: () =>
      api.post<Opportunity[]>(
        `/workspaces/${workspace!.id}/opportunities/discover-marketing?product_id=${product!.id}`
      ),
    onSuccess: (found) => {
      toast.success(found.length > 0 ? `Discovered ${found.length} new opportunities` : "No new opportunities found this run");
      queryClient.invalidateQueries({ queryKey: ["opportunities"] });
    },
    onError: (err) => toast.error(err instanceof ApiError ? err.message : "Marketing discovery failed"),
  });

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="Opportunities"
        description="Every growth opportunity in one unified, scored feed."
        action={
          product && (
            <Button size="sm" onClick={() => discoverMarketing.mutate()} disabled={discoverMarketing.isPending}>
              {discoverMarketing.isPending ? "Discovering…" : "Discover Marketing Opportunities"}
            </Button>
          )
        }
      />

      <div className="mb-4 flex flex-wrap items-center gap-1.5">
        {TYPES.map((t) => (
          <Button key={t.value} size="sm" variant={filter === t.value ? "default" : "secondary"} onClick={() => setFilter(t.value)}>
            {t.label}
          </Button>
        ))}
      </div>

      {opportunities && opportunities.length > 0 ? (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          {opportunities.map((o) => (
            <Card key={o.id}>
              <CardContent className="p-4">
                <div className="flex items-center gap-2">
                  <Badge>{o.type}</Badge>
                  <Badge variant="outline">{o.status}</Badge>
                </div>
                <p className="mt-2 text-sm font-medium">{o.title}</p>
                <p className="mt-1 text-xs text-[var(--muted-foreground)]">{o.description}</p>
                {o.deadline && <p className="mt-2 text-[11px] text-[var(--warning)]">Deadline: {o.deadline}</p>}
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <EmptyState icon={Sparkles} title="No opportunities yet" description="Opportunities surface here from research, competitor watch, brand monitoring, and launch discovery." />
      )}
    </div>
  );
}
