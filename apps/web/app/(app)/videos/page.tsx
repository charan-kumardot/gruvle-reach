"use client";

import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Clapperboard, ImageUp, RotateCw } from "lucide-react";
import { toast } from "sonner";
import { api, ApiError } from "@/lib/api-client";
import { useAppStore } from "@/lib/store";
import type { Video, VideoBrandKit } from "@/lib/types";
import { PageHeader } from "@/components/app/page-header";
import { EmptyState } from "@/components/app/empty-state";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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

  const { data: brandKit } = useQuery({
    queryKey: ["video-brand-kit", workspace?.id, product?.id],
    queryFn: () => api.get<VideoBrandKit>(`/workspaces/${workspace!.id}/videos/brand-kit?product_id=${product!.id}`),
    enabled: !!workspace && !!product,
  });

  const fileInputRef = useRef<HTMLInputElement>(null);
  const uploadScreenshot = useMutation({
    mutationFn: (file: File) => api.upload<VideoBrandKit>(`/workspaces/${workspace!.id}/videos/brand-kit/screenshot?product_id=${product!.id}`, file),
    onSuccess: () => {
      toast.success("Screenshot saved — the product/solution scenes in new videos will use it");
      queryClient.invalidateQueries({ queryKey: ["video-brand-kit"] });
    },
    onError: (err) => toast.error(err instanceof ApiError ? err.message : "Upload failed"),
  });

  const generate = useMutation({
    mutationFn: () => api.post<Video>(`/workspaces/${workspace!.id}/videos/generate`, { idea, product_id: product?.id, aspect_ratio: "9:16" }),
    onSuccess: () => {
      toast.success("Rendering started — this card will update automatically when it's ready");
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

      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><ImageUp className="h-3.5 w-3.5" /> Product screenshot</CardTitle>
        </CardHeader>
        <CardContent className="pt-0">
          <p className="mb-3 text-xs text-[var(--muted-foreground)]">
            Upload a real screenshot of {product.name}. New videos will show it in a premium browser mockup for the
            product/solution scenes instead of an abstract background.
          </p>
          <div className="flex items-center gap-3">
            {brandKit?.product_screenshot_url && (
              <img
                src={brandKit.product_screenshot_url}
                alt="Product screenshot"
                className="h-16 w-28 rounded-[var(--radius-sm)] border border-[var(--border)] object-cover"
              />
            )}
            <input
              ref={fileInputRef}
              type="file"
              accept="image/png,image/jpeg,image/webp"
              className="hidden"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) uploadScreenshot.mutate(file);
                e.target.value = "";
              }}
            />
            <Button size="sm" variant="secondary" onClick={() => fileInputRef.current?.click()} disabled={uploadScreenshot.isPending}>
              {uploadScreenshot.isPending ? "Uploading…" : brandKit?.product_screenshot_url ? "Replace screenshot" : "Upload screenshot"}
            </Button>
          </div>
        </CardContent>
      </Card>

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
