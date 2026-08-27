"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Landmark } from "lucide-react";
import { toast } from "sonner";
import { api, ApiError } from "@/lib/api-client";
import { useAppStore } from "@/lib/store";
import type { Investor, InvestorMatch } from "@/lib/types";
import { PageHeader } from "@/components/app/page-header";
import { EmptyState } from "@/components/app/empty-state";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScoreBadge } from "@/components/app/score-badge";

export default function InvestorsPage() {
  const { workspace, product } = useAppStore();
  const queryClient = useQueryClient();

  const { data: investors } = useQuery({
    queryKey: ["investors-directory"],
    queryFn: () => api.get<Investor[]>("/investors"),
  });

  const { data: matches } = useQuery({
    queryKey: ["investor-matches", workspace?.id, product?.id],
    queryFn: () => api.get<InvestorMatch[]>(`/workspaces/${workspace!.id}/products/${product!.id}/investor-matches`),
    enabled: !!workspace && !!product,
  });

  const computeMatches = useMutation({
    mutationFn: () =>
      api.post<InvestorMatch[]>(`/workspaces/${workspace!.id}/products/${product!.id}/investor-matches`, {
        stage: product?.stage ?? "",
      }),
    onSuccess: () => {
      toast.success("Investor matches computed");
      queryClient.invalidateQueries({ queryKey: ["investor-matches"] });
    },
    onError: (err) => toast.error(err instanceof ApiError ? err.message : "Matching failed"),
  });

  if (!product) {
    return <EmptyState icon={Landmark} title="Select a product" description="Choose a product to see investor matches." />;
  }

  const investorById = new Map((investors ?? []).map((i) => [i.id, i]));
  const sortedMatches = [...(matches ?? [])].sort((a, b) => b.fit_score - a.fit_score);

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="Investors"
        description={`${investors?.length ?? 0} investors in the directory — scored against ${product.name}.`}
        action={
          <Button size="sm" onClick={() => computeMatches.mutate()} disabled={computeMatches.isPending}>
            {computeMatches.isPending ? "Matching…" : "Compute matches"}
          </Button>
        }
      />

      {sortedMatches.length > 0 ? (
        <div className="flex flex-col gap-3">
          {sortedMatches.map((m) => {
            const investor = investorById.get(m.investor_id);
            if (!investor) return null;
            return (
              <Card key={m.id}>
                <CardContent className="p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="text-sm font-medium">{investor.fund_name || investor.investor_name}</p>
                        {investor.is_demo && <Badge variant="muted">DEMO</Badge>}
                        {investor.stage.slice(0, 2).map((s) => (
                          <Badge key={s} variant="outline">{s}</Badge>
                        ))}
                      </div>
                      <p className="mt-1.5 text-xs text-[var(--muted-foreground)]">{investor.thesis}</p>
                      {m.reasons.length > 0 && (
                        <ul className="mt-2 flex flex-col gap-1">
                          {m.reasons.map((r, i) => (
                            <li key={i} className="text-[11px] text-[var(--muted-foreground)]">— {r.reason}</li>
                          ))}
                        </ul>
                      )}
                    </div>
                    <ScoreBadge score={m.fit_score} />
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      ) : (
        <EmptyState
          icon={Landmark}
          title="No investor matches yet"
          description="Compute matches to score every investor in the directory against this product's stage, sector, and geography."
          action={<Button size="sm" onClick={() => computeMatches.mutate()}>Compute matches</Button>}
        />
      )}
    </div>
  );
}
