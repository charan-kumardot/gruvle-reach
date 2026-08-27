"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Megaphone, Plus } from "lucide-react";
import { toast } from "sonner";
import { api, ApiError } from "@/lib/api-client";
import { useAppStore } from "@/lib/store";
import type { Campaign } from "@/lib/types";
import { PageHeader } from "@/components/app/page-header";
import { EmptyState } from "@/components/app/empty-state";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input, Textarea } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function CampaignsPage() {
  const { workspace, product } = useAppStore();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ name: "", goal: "", audience_description: "" });

  const { data: campaigns } = useQuery({
    queryKey: ["campaigns", workspace?.id],
    queryFn: () => api.get<Campaign[]>(`/workspaces/${workspace!.id}/campaigns`),
    enabled: !!workspace,
  });

  const create = useMutation({
    mutationFn: () => api.post<Campaign>(`/workspaces/${workspace!.id}/campaigns`, { ...form, product_id: product?.id, channels: [] }),
    onSuccess: () => {
      toast.success("Campaign created");
      setOpen(false);
      setForm({ name: "", goal: "", audience_description: "" });
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
            <Card key={c.id}>
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
            <Button type="submit" disabled={create.isPending}>{create.isPending ? "Creating…" : "Create campaign"}</Button>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
