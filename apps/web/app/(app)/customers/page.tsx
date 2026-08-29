"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Users, Search, Zap, Globe } from "lucide-react";
import { toast } from "sonner";
import { api, ApiError } from "@/lib/api-client";
import { useAppStore } from "@/lib/store";
import { usePollAfterAction } from "@/lib/hooks";
import type { Company, CompanyTrigger } from "@/lib/types";
import { PageHeader } from "@/components/app/page-header";
import { EmptyState } from "@/components/app/empty-state";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { ScoreBadge } from "@/components/app/score-badge";
import { EvidenceBadge } from "@/components/app/evidence-badge";

export default function CustomersPage() {
  const { workspace, product } = useAppStore();
  const queryClient = useQueryClient();
  const [discoverOpen, setDiscoverOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [minScore, setMinScore] = useState(0);

  const { data: companies, isLoading } = useQuery({
    queryKey: ["companies", workspace?.id, product?.id, minScore],
    queryFn: () => api.get<Company[]>(`/workspaces/${workspace!.id}/companies?product_id=${product!.id}&min_score=${minScore}`),
    enabled: !!workspace && !!product,
  });

  const { polling, start: startPolling } = usePollAfterAction(() => queryClient.invalidateQueries({ queryKey: ["companies"] }));

  // Zero-input discovery: derives a broad set of queries from the product's
  // own ICPs (industries x company-size tiers, no geography bias) — this is
  // the primary action. Safe to click repeatedly; discovery dedupes by URL.
  // Runs in the background (app/core/background.py) — no synchronous result,
  // so poll the companies list for a bit until it shows up.
  const discoverAuto = useMutation({
    mutationFn: () => api.post<{ status: string }>(`/workspaces/${workspace!.id}/companies/discover-auto?product_id=${product!.id}`),
    onSuccess: () => {
      toast.success("Discovery started — new companies will appear below over the next minute or so");
      startPolling();
    },
    onError: (err) =>
      toast.error(err instanceof ApiError ? err.message : "Discovery failed — check your SEARCH_PROVIDER config"),
  });

  const discover = useMutation({
    mutationFn: () =>
      api.post<{ status: string }>(`/workspaces/${workspace!.id}/companies/discover?product_id=${product!.id}`, {
        queries: [query],
        max_results_per_query: 15,
      }),
    onSuccess: () => {
      toast.success("Search started — matching companies will appear below over the next minute or so");
      setDiscoverOpen(false);
      setQuery("");
      startPolling();
    },
    onError: (err) =>
      toast.error(err instanceof ApiError ? err.message : "Discovery failed — check your SEARCH_PROVIDER config"),
  });

  if (!product) {
    return <EmptyState icon={Users} title="Select a product" description="Choose a product from the top bar to see customer research." />;
  }

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="Customers"
        description="Target accounts researched and scored against your ICP."
        action={
          <div className="flex gap-2">
            <Button size="sm" variant="secondary" onClick={() => setDiscoverOpen(true)}>
              Custom search
            </Button>
            <Button size="sm" onClick={() => discoverAuto.mutate()} disabled={discoverAuto.isPending}>
              <Search className="mr-1.5 h-4 w-4" /> {discoverAuto.isPending ? "Starting…" : "Discover companies"}
            </Button>
          </div>
        }
      />

      {polling && (
        <p className="mb-3 text-xs text-[var(--muted-foreground)]">Discovery running in the background — checking for new results…</p>
      )}

      <div className="mb-4 flex items-center gap-2">
        {[0, 60, 75, 90].map((s) => (
          <Button key={s} size="sm" variant={minScore === s ? "default" : "secondary"} onClick={() => setMinScore(s)}>
            {s === 0 ? "All" : `${s}+`}
          </Button>
        ))}
      </div>

      {isLoading ? (
        <p className="text-sm text-[var(--muted-foreground)]">Loading…</p>
      ) : companies && companies.length > 0 ? (
        <div className="flex flex-col gap-3">
          {companies.map((c) => (
            <CompanyRow key={c.id} company={c} />
          ))}
        </div>
      ) : (
        <EmptyState
          icon={Users}
          title="No target accounts yet"
          description="Run discovery to find real candidate companies with evidence — no query needed, it derives search terms from your product's own ICPs."
          action={<Button size="sm" onClick={() => discoverAuto.mutate()} disabled={discoverAuto.isPending}>{discoverAuto.isPending ? "Starting…" : "Discover companies"}</Button>}
        />
      )}

      <Dialog open={discoverOpen} onOpenChange={setDiscoverOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Custom search</DialogTitle>
            <DialogDescription>
              Searches the web via your configured search provider, fetches each result safely, and asks AI to extract
              only what the page actually says — every company comes with a source URL and confidence level. Use this
              for a specific phrase in addition to the automatic ICP-derived discovery above.
            </DialogDescription>
          </DialogHeader>
          <form
            className="flex flex-col gap-3"
            onSubmit={(e) => {
              e.preventDefault();
              discover.mutate();
            }}
          >
            <Input
              required
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="e.g. B2B SaaS companies raising Series A using Kubernetes"
            />
            <Button type="submit" disabled={discover.isPending}>
              {discover.isPending ? "Researching…" : "Run discovery"}
            </Button>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function CompanyRow({ company }: { company: Company }) {
  const workspace = useAppStore((s) => s.workspace);
  const [expanded, setExpanded] = useState(false);

  const { data: triggers } = useQuery({
    queryKey: ["triggers", company.id],
    queryFn: () => api.get<CompanyTrigger[]>(`/workspaces/${workspace!.id}/companies/${company.id}/triggers`),
    enabled: expanded && !!workspace,
  });

  return (
    <Card>
      <CardContent className="p-4">
        <div className="flex cursor-pointer items-start justify-between gap-3" onClick={() => setExpanded((v) => !v)}>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <p className="text-sm font-medium">{company.name}</p>
              {company.industry && <Badge variant="outline">{company.industry}</Badge>}
              <EvidenceBadge status={company.confidence} />
            </div>
            {company.potential_pain && <p className="mt-1.5 text-xs text-[var(--muted-foreground)]">{company.potential_pain}</p>}
            <div className="mt-2 flex flex-wrap items-center gap-3 text-[11px] text-[var(--muted-foreground)]">
              {company.website && (
                <a href={company.website} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()} className="flex items-center gap-1 hover:text-[var(--accent)]">
                  <Globe className="h-3 w-3" /> Source
                </a>
              )}
              {company.employee_estimate && <span>{company.employee_estimate} employees</span>}
              {company.funding_stage && <span>{company.funding_stage}</span>}
            </div>
          </div>
          <ScoreBadge score={company.manual_score_override ?? company.icp_fit_score} />
        </div>

        {expanded && (
          <div className="mt-4 border-t border-[var(--border)] pt-3">
            <p className="mb-2 text-xs font-medium text-[var(--muted-foreground)]">Triggers</p>
            {triggers && triggers.length > 0 ? (
              <div className="flex flex-col gap-2">
                {triggers.map((t) => (
                  <div key={t.id} className="rounded-[var(--radius-sm)] bg-[var(--border-subtle)] p-2.5">
                    <div className="flex items-center gap-2">
                      <Zap className="h-3.5 w-3.5 text-[var(--warning)]" />
                      <span className="text-xs font-medium">{t.description}</span>
                    </div>
                    <p className="mt-1 text-[11px] text-[var(--muted-foreground)]">{t.why_it_matters}</p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-[var(--muted-foreground)]">No triggers detected for this company.</p>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
