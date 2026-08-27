"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { useAppStore } from "@/lib/store";
import type { DashboardAnalytics } from "@/lib/types";
import { PageHeader } from "@/components/app/page-header";
import { Card, CardContent } from "@/components/ui/card";

const LABELS: Record<keyof DashboardAnalytics, string> = {
  qualified_prospects: "Qualified prospects",
  outreach_sent: "Outreach sent",
  outreach_replied: "Replies",
  meetings: "Meetings booked",
  customers_won: "Customers won",
  investor_conversations: "Investor conversations",
  open_opportunities: "Open opportunities",
  actions_today: "Actions today",
};

export default function AnalyticsPage() {
  const workspace = useAppStore((s) => s.workspace);

  const { data } = useQuery({
    queryKey: ["analytics", workspace?.id],
    queryFn: () => api.get<DashboardAnalytics>(`/workspaces/${workspace!.id}/analytics/dashboard`),
    enabled: !!workspace,
  });

  return (
    <div className="animate-fade-in">
      <PageHeader title="Analytics" description="Pipeline, outreach, and conversion metrics across your workspace." />
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {data &&
          (Object.keys(LABELS) as (keyof DashboardAnalytics)[]).map((key) => (
            <Card key={key}>
              <CardContent className="p-4">
                <p className="text-xs text-[var(--muted-foreground)]">{LABELS[key]}</p>
                <p className="mt-1 text-2xl font-semibold tabular-nums">{data[key]}</p>
              </CardContent>
            </Card>
          ))}
      </div>
    </div>
  );
}
