"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Radio, Search } from "lucide-react";
import { toast } from "sonner";
import { api, ApiError } from "@/lib/api-client";
import { useAppStore } from "@/lib/store";
import type { BrandMention } from "@/lib/types";
import { PageHeader } from "@/components/app/page-header";
import { EmptyState } from "@/components/app/empty-state";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";

const CATEGORY_VARIANT: Record<string, "success" | "danger" | "warning" | "default" | "muted"> = {
  positive: "success",
  negative: "danger",
  question: "warning",
  purchase_intent: "success",
  competitor_comparison: "default",
  feedback: "muted",
  neutral: "muted",
};

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
    return <EmptyState icon={Radio} title="Select a product" description="Choose a product to monitor brand mentions." />;
  }

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="Brand"
        description="Public mentions of your product, categorized — never posted automatically."
        action={<Button size="sm" onClick={() => setOpen(true)}><Search className="mr-1.5 h-4 w-4" /> Scan mentions</Button>}
      />

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
