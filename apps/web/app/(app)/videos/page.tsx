"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Clapperboard, RotateCw } from "lucide-react";
import { toast } from "sonner";
import { api, ApiError } from "@/lib/api-client";
import { useAppStore } from "@/lib/store";
import type { Video } from "@/lib/types";
import { PageHeader } from "@/components/app/page-header";
import { EmptyState } from "@/components/app/empty-state";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/input";

const STATUS_VARIANT: Record<string, "default" | "muted" | "outline"> = {
  ready: "default",
  rendering: "outline",
  script_ready: "outline",
  failed: "muted",
};

export default function VideosPage() {
  const { workspace, product } = useAppStore();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [idea, setIdea] = useState("");

  const { data: videos } = useQuery({
    queryKey: ["videos", workspace?.id],
    queryFn: () => api.get<Video[]>(`/workspaces/${workspace!.id}/videos`),
    enabled: !!workspace,
    refetchInterval: (query) => (query.state.data?.some((v) => v.status === "rendering") ? 4000 : false),
  });

  const generate = useMutation({
    mutationFn: () => api.post<Video>(`/workspaces/${workspace!.id}/videos/generate`, { idea, product_id: product?.id, aspect_ratio: "9:16" }),
    onSuccess: (video) => {
      toast[video.status === "ready" ? "success" : "error"](
        video.status === "ready" ? "Video rendered" : "Render failed — see the video card for details"
      );
      setOpen(false);
      setIdea("");
      queryClient.invalidateQueries({ queryKey: ["videos"] });
    },
    onError: (err) => toast.error(err instanceof ApiError ? err.message : "Video generation failed — check your AI_PROVIDER config"),
  });

  if (!product) {
    return <EmptyState icon={Clapperboard} title="Select a product" description="Choose a product to generate short-form videos." />;
  }

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="Video Library"
        description="Free-first template videos — script, scenes, and captions generated from a core idea."
        action={
          <Button size="sm" onClick={() => setOpen(true)}>
            <Clapperboard className="mr-1.5 h-4 w-4" /> New video
          </Button>
        }
      />

      {videos && videos.length > 0 ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {videos.map((v) => (
            <Card key={v.id}>
              <CardContent className="p-3">
                {v.status === "ready" && v.storage_url ? (
                  <video src={v.storage_url} controls className="mb-2 w-full rounded-[var(--radius-sm)] bg-black" style={{ aspectRatio: v.aspect_ratio.replace(":", "/") }} />
                ) : (
                  <div
                    className="mb-2 flex w-full items-center justify-center rounded-[var(--radius-sm)] bg-[var(--border-subtle)] text-[var(--muted-foreground)]"
                    style={{ aspectRatio: v.aspect_ratio.replace(":", "/") }}
                  >
                    {v.status === "rendering" ? <RotateCw className="h-5 w-5 animate-spin" /> : <Clapperboard className="h-5 w-5" />}
                  </div>
                )}
                <div className="flex items-center gap-2">
                  <Badge variant={STATUS_VARIANT[v.status] ?? "muted"}>{v.status}</Badge>
                  <Badge variant="outline">{v.aspect_ratio}</Badge>
                  {v.has_voiceover && <Badge variant="outline">voiceover</Badge>}
                </div>
                <p className="mt-1.5 truncate text-xs font-medium">{v.script.hook || "Untitled"}</p>
                {v.status === "failed" && <p className="mt-1 text-[11px] text-[var(--danger)]">{v.render_log.slice(0, 200)}</p>}
                {v.duration_seconds > 0 && <p className="mt-1 text-[11px] text-[var(--muted-foreground)]">{Math.round(v.duration_seconds)}s</p>}
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <EmptyState
          icon={Clapperboard}
          title="No videos yet"
          description="Generate one from an idea, or approve content in the Content page and use 'Generate video' on a variant."
          action={<Button size="sm" onClick={() => setOpen(true)}>New video</Button>}
        />
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>New video</DialogTitle>
            <DialogDescription>Writes a short hook/problem/insight/solution/product/CTA script and renders it with your brand colors.</DialogDescription>
          </DialogHeader>
          <form className="flex flex-col gap-3" onSubmit={(e) => { e.preventDefault(); generate.mutate(); }}>
            <Textarea required value={idea} onChange={(e) => setIdea(e.target.value)} placeholder="What should this video be about?" />
            <Button type="submit" disabled={generate.isPending}>{generate.isPending ? "Rendering…" : "Generate video"}</Button>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
