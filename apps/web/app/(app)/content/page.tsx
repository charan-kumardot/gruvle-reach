"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { PenSquare, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { api, ApiError } from "@/lib/api-client";
import { useAppStore } from "@/lib/store";
import type { ContentItem, ContentStatus } from "@/lib/types";
import { PageHeader } from "@/components/app/page-header";
import { EmptyState } from "@/components/app/empty-state";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/input";

const CHANNELS = ["linkedin", "x", "instagram", "blog", "newsletter", "reddit"];

export default function ContentPage() {
  const { workspace, product } = useAppStore();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [idea, setIdea] = useState("");
  const [tab, setTab] = useState<ContentStatus>("draft");

  const { data: items } = useQuery({
    queryKey: ["content", workspace?.id, tab],
    queryFn: () => api.get<ContentItem[]>(`/workspaces/${workspace!.id}/content?status=${tab}`),
    enabled: !!workspace,
  });

  const generate = useMutation({
    mutationFn: () =>
      api.post<ContentItem>(`/workspaces/${workspace!.id}/content/generate`, {
        product_id: product?.id,
        idea,
        channels: CHANNELS,
      }),
    onSuccess: () => {
      toast.success("Content drafts generated");
      setOpen(false);
      setIdea("");
      queryClient.invalidateQueries({ queryKey: ["content"] });
    },
    onError: (err) => toast.error(err instanceof ApiError ? err.message : "Generation failed — check your AI_PROVIDER config"),
  });

  if (!product) {
    return <EmptyState icon={PenSquare} title="Select a product" description="Choose a product to generate content." />;
  }

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="Content"
        description="One idea, repurposed across every channel — grounded in your Brand Brain."
        action={
          <Button size="sm" onClick={() => setOpen(true)}>
            <Sparkles className="mr-1.5 h-4 w-4" /> New idea
          </Button>
        }
      />

      <Tabs value={tab} onValueChange={(v) => setTab(v as ContentStatus)} className="mb-4">
        <TabsList>
          <TabsTrigger value="idea">Ideas</TabsTrigger>
          <TabsTrigger value="draft">Drafts</TabsTrigger>
          <TabsTrigger value="approved">Approved</TabsTrigger>
          <TabsTrigger value="published">Published</TabsTrigger>
        </TabsList>
      </Tabs>

      {items && items.length > 0 ? (
        <div className="flex flex-col gap-4">
          {items.map((item) => (
            <Card key={item.id}>
              <CardContent className="p-4">
                <p className="text-sm font-medium">{item.idea}</p>
                <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
                  {item.variants.map((v) => (
                    <div key={v.id} className="rounded-[var(--radius-sm)] border border-[var(--border)] p-3">
                      <div className="mb-1.5 flex items-center justify-between">
                        <Badge variant="outline">{v.channel}</Badge>
                        <Badge>{v.status}</Badge>
                      </div>
                      <p className="whitespace-pre-wrap text-xs text-[var(--muted-foreground)]">{v.body}</p>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <EmptyState icon={PenSquare} title="Nothing here yet" description="Generate a new idea to see channel-specific drafts." action={<Button size="sm" onClick={() => setOpen(true)}>New idea</Button>} />
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>New content idea</DialogTitle>
            <DialogDescription>Generates LinkedIn, X, Instagram, blog, newsletter, and Reddit drafts from one idea.</DialogDescription>
          </DialogHeader>
          <form className="flex flex-col gap-3" onSubmit={(e) => { e.preventDefault(); generate.mutate(); }}>
            <Textarea required value={idea} onChange={(e) => setIdea(e.target.value)} placeholder="The story behind why we built this feature..." />
            <Button type="submit" disabled={generate.isPending}>{generate.isPending ? "Generating…" : "Generate drafts"}</Button>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
