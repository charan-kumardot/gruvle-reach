"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Radio, Search, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { api, ApiError } from "@/lib/api-client";
import { useAppStore } from "@/lib/store";
import type { BrandBrain, BrandMention } from "@/lib/types";
import { PageHeader } from "@/components/app/page-header";
import { EmptyState } from "@/components/app/empty-state";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input, Textarea } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";

const CATEGORY_VARIANT: Record<string, "success" | "danger" | "warning" | "default" | "muted"> = {
  positive: "success",
  negative: "danger",
  question: "warning",
  purchase_intent: "success",
  competitor_comparison: "default",
  feedback: "muted",
  neutral: "muted",
};

const listToText = (v: string[]) => v.join("\n");
const textToList = (v: string) => v.split("\n").map((s) => s.trim()).filter(Boolean);

export default function BrandPage() {
  const { workspace, product } = useAppStore();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [keywords, setKeywords] = useState("Gruvle Radar");

  const { data: mentions } = useQuery({
    queryKey: ["brand-mentions", workspace?.id],
    queryFn: () => api.get<BrandMention[]>(`/workspaces/${workspace!.id}/brand/mentions`),
    enabled: !!workspace,
  });

  const scan = useMutation({
    mutationFn: () =>
      api.post<BrandMention[]>(`/workspaces/${workspace!.id}/brand/scan`, {
        product_id: product?.id,
        keywords: keywords.split(",").map((k) => k.trim()).filter(Boolean),
      }),
    onSuccess: (found) => {
      toast.success(`Found ${found.length} mention${found.length === 1 ? "" : "s"}`);
      setOpen(false);
      queryClient.invalidateQueries({ queryKey: ["brand-mentions"] });
    },
    onError: (err) => toast.error(err instanceof ApiError ? err.message : "Scan failed"),
  });

  if (!product) {
    return <EmptyState icon={Radio} title="Select a product" description="Choose a product to manage its brand kit and monitor mentions." />;
  }

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="Brand"
        description="Your brand kit grounds every AI-generated post and blocks unsupported claims — plus public mentions, never posted automatically."
      />

      <Tabs defaultValue="kit">
        <TabsList>
          <TabsTrigger value="kit">Brand Kit</TabsTrigger>
          <TabsTrigger value="mentions">Mentions</TabsTrigger>
        </TabsList>

        <TabsContent value="kit">
          <BrandKitTab productId={product.id} />
        </TabsContent>

        <TabsContent value="mentions">
          <div className="mb-4">
            <Button size="sm" onClick={() => setOpen(true)}><Search className="mr-1.5 h-4 w-4" /> Scan mentions</Button>
          </div>
          {mentions && mentions.length > 0 ? (
            <div className="flex flex-col gap-3">
              {mentions.map((m) => (
                <Card key={m.id}>
                  <CardContent className="p-4">
                    <div className="flex items-center gap-2">
                      <Badge variant={CATEGORY_VARIANT[m.category] ?? "muted"}>{m.category.replace("_", " ")}</Badge>
                      <span className="text-xs text-[var(--muted-foreground)]">&quot;{m.keyword}&quot;</span>
                    </div>
                    <p className="mt-2 text-sm">{m.excerpt}</p>
                    <p className="mt-1.5 text-xs text-[var(--accent)]">{m.recommended_action}</p>
                  </CardContent>
                </Card>
              ))}
            </div>
          ) : (
            <EmptyState icon={Radio} title="No mentions yet" description="Scan for public mentions of your product name across the web." action={<Button size="sm" onClick={() => setOpen(true)}>Scan mentions</Button>} />
          )}
        </TabsContent>
      </Tabs>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Scan for brand mentions</DialogTitle>
            <DialogDescription>Comma-separated keywords to search for.</DialogDescription>
          </DialogHeader>
          <form className="flex flex-col gap-3" onSubmit={(e) => { e.preventDefault(); scan.mutate(); }}>
            <Input value={keywords} onChange={(e) => setKeywords(e.target.value)} placeholder="Gruvle Radar, Gruvle" />
            <Button type="submit" disabled={scan.isPending}>{scan.isPending ? "Scanning…" : "Scan"}</Button>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function BrandKitTab({ productId }: { productId: string }) {
  const workspace = useAppStore((s) => s.workspace);
  const queryClient = useQueryClient();

  const { data: brand, isLoading } = useQuery({
    queryKey: ["brand-brain", workspace?.id, productId],
    queryFn: () => api.get<BrandBrain | null>(`/workspaces/${workspace!.id}/brand-brain?product_id=${productId}`),
    enabled: !!workspace,
  });

  const [form, setForm] = useState({
    voice: "", tone: "", positioning: "", founder_story: "",
    key_messages: "", words_to_use: "", words_to_avoid: "", claims: "",
  });

  useEffect(() => {
    if (brand) {
      setForm({
        voice: brand.voice, tone: brand.tone, positioning: brand.positioning, founder_story: brand.founder_story,
        key_messages: listToText(brand.key_messages), words_to_use: listToText(brand.words_to_use),
        words_to_avoid: listToText(brand.words_to_avoid), claims: listToText(brand.claims),
      });
    }
  }, [brand]);

  const generate = useMutation({
    mutationFn: () => api.post(`/workspaces/${workspace!.id}/products/${productId}/brand-setup/generate`),
    onSuccess: () => {
      toast.success("Drafted your brand kit — review and edit below, then save.");
      queryClient.invalidateQueries({ queryKey: ["brand-brain", workspace?.id, productId] });
      queryClient.invalidateQueries({ queryKey: ["product-truth", productId] });
    },
    onError: (err) => toast.error(err instanceof ApiError ? err.message : "Generation failed — check your AI_PROVIDER config"),
  });

  const save = useMutation({
    mutationFn: () =>
      api.put(`/workspaces/${workspace!.id}/brand-brain?product_id=${productId}`, {
        voice: form.voice, tone: form.tone, positioning: form.positioning, founder_story: form.founder_story,
        key_messages: textToList(form.key_messages), words_to_use: textToList(form.words_to_use),
        words_to_avoid: textToList(form.words_to_avoid), claims: textToList(form.claims),
        proof_points: brand?.proof_points ?? [], product_facts: brand?.product_facts ?? [],
      }),
    onSuccess: () => {
      toast.success("Brand kit saved");
      queryClient.invalidateQueries({ queryKey: ["brand-brain", workspace?.id, productId] });
    },
    onError: (err) => toast.error(err instanceof ApiError ? err.message : "Failed to save"),
  });

  const isEmpty = !isLoading && !brand;

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardHeader>
          <div className="flex items-start justify-between gap-3">
            <div>
              <CardTitle>Brand Kit</CardTitle>
              <CardDescription>
                Grounds every generated post — voice, key messages, and which claims are actually supported.
                Every quality-gate check (duplicate detection, forbidden words, unsupported claims) uses this.
              </CardDescription>
            </div>
            <Button size="sm" variant="secondary" onClick={() => generate.mutate()} disabled={generate.isPending}>
              <Sparkles className="mr-1.5 h-3.5 w-3.5" /> {generate.isPending ? "Drafting…" : brand ? "Regenerate with AI" : "Generate with AI"}
            </Button>
          </div>
        </CardHeader>
        <CardContent className="flex flex-col gap-3 pt-0">
          {isEmpty && (
            <p className="rounded-[var(--radius-sm)] bg-[var(--warning)]/10 p-2.5 text-xs text-[var(--warning)]">
              No brand kit set up yet — content generated so far had no brand grounding at all. Generate one from your
              product description, or fill it in by hand below.
            </p>
          )}
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5">
              <Label>Voice</Label>
              <Input value={form.voice} onChange={(e) => setForm({ ...form, voice: e.target.value })} placeholder="direct, technical, no hype" />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label>Tone</Label>
              <Input value={form.tone} onChange={(e) => setForm({ ...form, tone: e.target.value })} placeholder="confident but not salesy" />
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Positioning</Label>
            <Textarea value={form.positioning} onChange={(e) => setForm({ ...form, positioning: e.target.value })} placeholder="One or two sentences on how you want to be seen in the market." />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Key messages (one per line)</Label>
            <Textarea value={form.key_messages} onChange={(e) => setForm({ ...form, key_messages: e.target.value })} />
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5">
              <Label>Words to use (one per line)</Label>
              <Textarea value={form.words_to_use} onChange={(e) => setForm({ ...form, words_to_use: e.target.value })} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label>Words to avoid (one per line)</Label>
              <Textarea value={form.words_to_avoid} onChange={(e) => setForm({ ...form, words_to_avoid: e.target.value })} />
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Approved claims (one per line)</Label>
            <Textarea value={form.claims} onChange={(e) => setForm({ ...form, claims: e.target.value })} placeholder="Only what you can actually back up — the quality gate blocks anything not listed here." />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Founder story (optional)</Label>
            <Textarea value={form.founder_story} onChange={(e) => setForm({ ...form, founder_story: e.target.value })} placeholder="AI can't write this for you — why you're building this." />
          </div>
          <Button size="sm" className="self-start" onClick={() => save.mutate()} disabled={save.isPending}>
            {save.isPending ? "Saving…" : "Save Brand Kit"}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
