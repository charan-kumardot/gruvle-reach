"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Megaphone, Plus, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { api, ApiError } from "@/lib/api-client";
import { useAppStore } from "@/lib/store";
import type { Campaign, CampaignMetric, ContentItem } from "@/lib/types";
import { PageHeader } from "@/components/app/page-header";
import { EmptyState } from "@/components/app/empty-state";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Input, Textarea } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const CAMPAIGN_CHANNELS = ["linkedin", "x", "instagram", "facebook", "reddit", "email"];

export default function CampaignsPage() {
  const { workspace, product } = useAppStore();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [form, setForm] = useState({ name: "", goal: "", audience_description: "" });
  const [channels, setChannels] = useState<string[]>(["linkedin", "x"]);

  const toggleChannel = (channel: string) => {
    setChannels((prev) => (prev.includes(channel) ? prev.filter((c) => c !== channel) : [...prev, channel]));
  };

  const { data: campaigns } = useQuery({
    queryKey: ["campaigns", workspace?.id],
    queryFn: () => api.get<Campaign[]>(`/workspaces/${workspace!.id}/campaigns`),
    enabled: !!workspace,
  });

  const create = useMutation({
    mutationFn: () => api.post<Campaign>(`/workspaces/${workspace!.id}/campaigns`, { ...form, product_id: product?.id, channels }),
    onSuccess: () => {
      toast.success("Campaign created");
      setOpen(false);
      setForm({ name: "", goal: "", audience_description: "" });
      setChannels(["linkedin", "x"]);
      queryClient.invalidateQueries({ queryKey: ["campaigns"] });
    },
    onError: (err) => toast.error(err instanceof ApiError ? err.message : "Failed to create campaign"),
  });

  if (!product) {
    return <EmptyState icon={Megaphone} title="Select a product" description="Choose a product to manage campaigns." />;
  }

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="Campaigns"
        description="Track reach, signups, and conversions across channels."
        action={
          <Button size="sm" onClick={() => setOpen(true)}>
            <Plus className="mr-1.5 h-4 w-4" /> New campaign
          </Button>
        }
      />

      {campaigns && campaigns.length > 0 ? (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {campaigns.map((c) => (
            <Card key={c.id} className="cursor-pointer" onClick={() => setSelectedId(c.id)}>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle>{c.name}</CardTitle>
                  <Badge variant="outline">{c.status}</Badge>
                </div>
                <CardDescription>{c.goal || "No goal set"}</CardDescription>
              </CardHeader>
              <CardContent className="pt-0 text-xs text-[var(--muted-foreground)]">{c.audience_description}</CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <EmptyState icon={Megaphone} title="No campaigns yet" description="Create a campaign to track launch performance across channels." action={<Button size="sm" onClick={() => setOpen(true)}>New campaign</Button>} />
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>New campaign</DialogTitle>
          </DialogHeader>
          <form className="flex flex-col gap-3" onSubmit={(e) => { e.preventDefault(); create.mutate(); }}>
            <div className="flex flex-col gap-1.5">
              <Label>Name</Label>
              <Input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Gruvle Radar Launch" />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label>Goal</Label>
              <Input value={form.goal} onChange={(e) => setForm({ ...form, goal: e.target.value })} placeholder="500 qualified signups" />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label>Audience</Label>
              <Textarea value={form.audience_description} onChange={(e) => setForm({ ...form, audience_description: e.target.value })} placeholder="B2B SaaS companies" />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label>Channels</Label>
              <div className="flex flex-wrap gap-1.5">
                {CAMPAIGN_CHANNELS.map((c) => (
                  <Button
                    key={c}
                    type="button"
                    size="sm"
                    variant={channels.includes(c) ? "default" : "secondary"}
                    onClick={() => toggleChannel(c)}
                  >
                    {c}
                  </Button>
                ))}
              </div>
            </div>
            <Button type="submit" disabled={create.isPending || channels.length === 0}>{create.isPending ? "Creating…" : "Create campaign"}</Button>
          </form>
        </DialogContent>
      </Dialog>

      <CampaignDetailDialog
        campaign={campaigns?.find((c) => c.id === selectedId) ?? null}
        onClose={() => setSelectedId(null)}
      />
    </div>
  );
}

function CampaignDetailDialog({ campaign, onClose }: { campaign: Campaign | null; onClose: () => void }) {
  const { workspace } = useAppStore();
  const queryClient = useQueryClient();

  const { data: content } = useQuery({
    queryKey: ["campaign-content", campaign?.id],
    queryFn: () => api.get<ContentItem[]>(`/workspaces/${workspace!.id}/campaigns/${campaign!.id}/content`),
    enabled: !!workspace && !!campaign,
  });

  const { data: metrics } = useQuery({
    queryKey: ["campaign-metrics", campaign?.id],
    queryFn: () => api.get<CampaignMetric[]>(`/workspaces/${workspace!.id}/campaigns/${campaign!.id}/metrics`),
    enabled: !!workspace && !!campaign,
  });

  const generateContent = useMutation({
    mutationFn: () => api.post<ContentItem[]>(`/workspaces/${workspace!.id}/campaigns/${campaign!.id}/generate-content`, { count: 5 }),
    onSuccess: (items) => {
      const withDrafts = items.filter((i) => i.variants.length > 0).length;
      if (withDrafts === items.length) {
        toast.success(`Generated ${items.length} campaign asset${items.length === 1 ? "" : "s"}`);
      } else if (withDrafts === 0) {
        toast.error(`${items.length} idea${items.length === 1 ? "" : "s"} created, but draft generation failed for all of them — your AI provider may be rate-limited. Retry below.`);
      } else {
        toast.warning(`${withDrafts} of ${items.length} ideas got drafts — the rest failed and can be retried below.`);
      }
      queryClient.invalidateQueries({ queryKey: ["campaign-content", campaign?.id] });
    },
    onError: (err) => toast.error(err instanceof ApiError ? err.message : "Content generation failed"),
  });

  const retryVariants = useMutation({
    mutationFn: (contentId: string) => api.post<ContentItem>(`/workspaces/${workspace!.id}/content/${contentId}/generate-variants`, { channels: ["linkedin", "x"] }),
    onSuccess: () => {
      toast.success("Draft generated");
      queryClient.invalidateQueries({ queryKey: ["campaign-content", campaign?.id] });
    },
    onError: (err) => toast.error(err instanceof ApiError ? err.message : "Still failed — try again shortly"),
  });

  const activate = useMutation({
    mutationFn: () => api.patch(`/workspaces/${workspace!.id}/campaigns/${campaign!.id}`, { status: "active" }),
    onSuccess: () => {
      toast.success("Campaign activated");
      queryClient.invalidateQueries({ queryKey: ["campaigns"] });
    },
    onError: (err) => toast.error(err instanceof ApiError ? err.message : "Requires the admin role"),
  });

  if (!campaign) return null;

  return (
    <Dialog open={!!campaign} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <div className="flex items-center gap-2">
            <DialogTitle>{campaign.name}</DialogTitle>
            <Badge variant="outline">{campaign.status}</Badge>
          </div>
          <DialogDescription>{campaign.goal || "No goal set"} — {campaign.audience_description || "no audience set"}</DialogDescription>
        </DialogHeader>

        <div className="flex flex-wrap gap-2">
          {campaign.status === "planned" && (
            <Button size="sm" variant="secondary" onClick={() => activate.mutate()} disabled={activate.isPending}>
              {activate.isPending ? "Activating…" : "Activate campaign"}
            </Button>
          )}
          <Button size="sm" onClick={() => generateContent.mutate()} disabled={generateContent.isPending}>
            <Sparkles className="mr-1.5 h-3.5 w-3.5" /> {generateContent.isPending ? "Generating…" : "Generate content for this campaign"}
          </Button>
        </div>

        {metrics && metrics.length > 0 && (
          <div className="grid grid-cols-3 gap-2 sm:grid-cols-6">
            {["reach", "visitors", "signups", "conversions", "responses", "meetings"].map((key) => {
              const total = metrics.reduce((sum, m) => sum + (m[key as keyof CampaignMetric] as number || 0), 0);
              return (
                <div key={key} className="rounded-[var(--radius-sm)] bg-[var(--border-subtle)] p-2 text-center">
                  <p className="text-sm font-semibold tabular-nums">{total}</p>
                  <p className="text-[10px] capitalize text-[var(--muted-foreground)]">{key}</p>
                </div>
              );
            })}
          </div>
        )}

        <div className="flex flex-col gap-2 max-h-80 overflow-y-auto">
          {content && content.length > 0 ? (
            content.map((item) => (
              <div key={item.id} className="rounded-[var(--radius-sm)] border border-[var(--border)] p-2.5">
                <div className="mb-1 flex items-center gap-1.5">
                  <Badge variant="outline">{item.content_type}</Badge>
                  {item.variants.length > 0 ? (
                    <span className="text-xs text-[var(--muted-foreground)]">{item.variants.length} variant{item.variants.length === 1 ? "" : "s"}</span>
                  ) : (
                    <Badge variant="danger">Draft generation failed</Badge>
                  )}
                </div>
                <p className="text-xs">{item.idea}</p>
                {item.variants.length === 0 && (
                  <Button
                    size="sm" variant="secondary" className="mt-2"
                    onClick={() => retryVariants.mutate(item.id)}
                    disabled={retryVariants.isPending}
                  >
                    {retryVariants.isPending ? "Retrying…" : "Retry draft"}
                  </Button>
                )}
              </div>
            ))
          ) : (
            <p className="text-xs text-[var(--muted-foreground)]">No content generated for this campaign yet.</p>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
