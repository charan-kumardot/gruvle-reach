"use client";

import { useQuery } from "@tanstack/react-query";
import { Sparkles, TrendingUp, Users, Landmark, Radio } from "lucide-react";
import { api } from "@/lib/api-client";
import { useAppStore } from "@/lib/store";
import type { ActionItem, BrandMention, Company, DashboardAnalytics, InvestorMatch, Investor } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/app/empty-state";
import { ActionCard } from "@/components/app/action-card";
import { Badge } from "@/components/ui/badge";
import { ScoreBadge } from "@/components/app/score-badge";

export default function OverviewPage() {
  const { workspace, product } = useAppStore();
  const wsId = workspace?.id;
  const productId = product?.id;

  const { data: brief } = useQuery({
    queryKey: ["daily-brief", wsId, productId],
    queryFn: () => api.get<ActionItem[]>(`/workspaces/${wsId}/actions/daily-brief?product_id=${productId}`),
    enabled: !!wsId && !!productId,
  });

  const { data: analytics } = useQuery({
    queryKey: ["analytics", wsId],
    queryFn: () => api.get<DashboardAnalytics>(`/workspaces/${wsId}/analytics/dashboard`),
    enabled: !!wsId,
  });

  const { data: companies } = useQuery({
    queryKey: ["companies-top", wsId, productId],
    queryFn: () => api.get<Company[]>(`/workspaces/${wsId}/companies?product_id=${productId}&min_score=60`),
    enabled: !!wsId && !!productId,
  });

  const { data: matches } = useQuery({
    queryKey: ["investor-matches-top", wsId, productId],
    queryFn: () => api.get<InvestorMatch[]>(`/workspaces/${wsId}/products/${productId}/investor-matches`),
    enabled: !!wsId && !!productId,
  });

  const { data: investors } = useQuery({
    queryKey: ["investors-directory"],
    queryFn: () => api.get<Investor[]>("/investors"),
  });

  const { data: brandMentions } = useQuery({
    queryKey: ["brand-mentions", wsId],
    queryFn: () => api.get<BrandMention[]>(`/workspaces/${wsId}/brand/mentions`),
    enabled: !!wsId,
  });

  if (!product) {
    return (
      <EmptyState
        icon={Sparkles}
        title="Create your first product to get started"
        description="Gruvle Reach researches your market once you tell it what you're building."
      />
    );
  }

  const investorById = new Map((investors ?? []).map((i) => [i.id, i]));
  const kpis = [
    { label: "Qualified prospects", value: analytics?.qualified_prospects, icon: Users },
    { label: "Open opportunities", value: analytics?.open_opportunities, icon: Sparkles },
    { label: "Investor conversations", value: analytics?.investor_conversations, icon: Landmark },
    { label: "Actions today", value: analytics?.actions_today, icon: TrendingUp },
  ];

  return (
    <div className="animate-fade-in">
      <div className="mb-8">
        <h1 className="text-xl font-semibold tracking-tight">Good morning.</h1>
        <p className="mt-1 text-sm text-[var(--muted-foreground)]">Here&apos;s what deserves your attention on {product.name}.</p>
      </div>

      <div className="mb-8 grid grid-cols-2 gap-3 lg:grid-cols-4">
        {kpis.map((kpi) => (
          <Card key={kpi.label}>
            <CardContent className="flex items-center justify-between p-4">
              <div>
                <p className="text-xs text-[var(--muted-foreground)]">{kpi.label}</p>
                <p className="mt-1 text-2xl font-semibold tabular-nums">{kpi.value ?? "–"}</p>
              </div>
              <kpi.icon className="h-4 w-4 text-[var(--muted-foreground)]" />
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold">7 actions most likely to move your product forward today</h2>
          </div>
          {brief && brief.length > 0 ? (
            <div className="flex flex-col gap-3">
              {brief.slice(0, 7).map((action, idx) => (
                <ActionCard key={action.id} action={action} index={idx + 1} />
              ))}
            </div>
          ) : (
            <EmptyState
              icon={Sparkles}
              title="No actions yet"
              description="Run research from the Customers or Investors pages to generate your first recommendations."
            />
          )}
        </div>

        <div className="flex flex-col gap-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2"><Users className="h-3.5 w-3.5" /> Top customer prospects</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-2 pt-0">
              {companies && companies.length > 0 ? (
                companies.slice(0, 4).map((c) => (
                  <div key={c.id} className="flex items-center justify-between gap-2 rounded-[var(--radius-sm)] px-2 py-1.5 hover:bg-[var(--border-subtle)]">
                    <span className="truncate text-sm">{c.name}</span>
                    <ScoreBadge score={c.icp_fit_score} showLabel={false} />
                  </div>
                ))
              ) : (
                <p className="text-xs text-[var(--muted-foreground)]">No companies discovered yet.</p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2"><Landmark className="h-3.5 w-3.5" /> Investor matches</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-2 pt-0">
              {matches && matches.length > 0 ? (
                matches.slice(0, 4).map((m) => (
                  <div key={m.id} className="flex items-center justify-between gap-2 rounded-[var(--radius-sm)] px-2 py-1.5 hover:bg-[var(--border-subtle)]">
                    <span className="truncate text-sm">{investorById.get(m.investor_id)?.fund_name ?? "Investor"}</span>
                    <ScoreBadge score={m.fit_score} showLabel={false} />
                  </div>
                ))
              ) : (
                <p className="text-xs text-[var(--muted-foreground)]">No investor matches yet.</p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2"><Radio className="h-3.5 w-3.5" /> Brand mentions</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-2 pt-0">
              {brandMentions && brandMentions.length > 0 ? (
                brandMentions.slice(0, 3).map((m) => (
                  <div key={m.id} className="rounded-[var(--radius-sm)] px-2 py-1.5">
                    <div className="flex items-center gap-2">
                      <Badge variant="outline">{m.category}</Badge>
                      <span className="truncate text-xs text-[var(--muted-foreground)]">{m.keyword}</span>
                    </div>
                  </div>
                ))
              ) : (
                <p className="text-xs text-[var(--muted-foreground)]">No mentions detected yet.</p>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
