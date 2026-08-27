"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Sparkles } from "lucide-react";
import { api } from "@/lib/api-client";
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
];

export default function OpportunitiesPage() {
  const { workspace } = useAppStore();
  const [filter, setFilter] = useState<OpportunityType | "all">("all");

  const { data: opportunities } = useQuery({
    queryKey: ["opportunities", workspace?.id, filter],
    queryFn: () =>
      api.get<Opportunity[]>(
        `/workspaces/${workspace!.id}/opportunities${filter !== "all" ? `?type=${filter}` : ""}`
      ),
    enabled: !!workspace,
  });

  return (
    <div className="animate-fade-in">
      <PageHeader title="Opportunities" description="Every growth opportunity in one unified, scored feed." />

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
