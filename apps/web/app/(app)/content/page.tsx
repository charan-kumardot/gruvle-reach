"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Calendar, Clapperboard, PenSquare, Rocket, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { api, ApiError } from "@/lib/api-client";
import { useAppStore } from "@/lib/store";
import type { ContentItem, ContentVariant } from "@/lib/types";
import { PageHeader } from "@/components/app/page-header";
import { EmptyState } from "@/components/app/empty-state";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Input, Textarea } from "@/components/ui/input";

const CHANNELS = ["linkedin", "x", "instagram", "blog", "newsletter", "reddit"];

const STATUS_BADGE_VARIANT: Record<string, "default" | "muted" | "outline"> = {
  ready: "default",
  approved: "default",
  scheduled: "default",
  published: "default",
  approval_required: "outline",
  failed: "outline",
  rejected: "muted",
  draft: "muted",
  idea: "muted",
  archived: "muted",
};

export default function ContentPage() {
  const { workspace, product } = useAppStore();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [idea, setIdea] = useState("");
  const [libraryFilter, setLibraryFilter] = useState<string>("all");
  const [schedulingId, setSchedulingId] = useState<string | null>(null);
  const [scheduleValue, setScheduleValue] = useState("");

  const invalidateAll = () => {
    queryClient.invalidateQueries({ queryKey: ["content"] });
    queryClient.invalidateQueries({ queryKey: ["content-queue"] });
    queryClient.invalidateQueries({ queryKey: ["content-calendar"] });
  };

  const { data: allContent } = useQuery({
    queryKey: ["content", workspace?.id],
    queryFn: () => api.get<ContentItem[]>(`/workspaces/${workspace!.id}/content`),
    enabled: !!workspace,
  });

  const { data: queue } = useQuery({
    queryKey: ["content-queue", workspace?.id],
    queryFn: () => api.get<ContentVariant[]>(`/workspaces/${workspace!.id}/content/queue`),
    enabled: !!workspace,
  });

  const { data: calendarItems } = useQuery({
    queryKey: ["content-calendar", workspace?.id],
    queryFn: () => api.get<ContentVariant[]>(`/workspaces/${workspace!.id}/content/calendar`),
    enabled: !!workspace,
  });

  const contentById = useMemo(() => new Map((allContent ?? []).map((c) => [c.id, c])), [allContent]);

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
      invalidateAll();
    },
    onError: (err) => toast.error(err instanceof ApiError ? err.message : "Generation failed — check your AI_PROVIDER config"),
  });

  const planToday = useMutation({
    mutationFn: () => api.post<ContentItem[]>(`/workspaces/${workspace!.id}/content/plan-today`, { product_id: product?.id }),
    onSuccess: (items) => {
      toast.success(items.length > 0 ? `Planned ${items.length} idea${items.length === 1 ? "" : "s"} for today` : "No new ideas today — try again once there's more signal");
      invalidateAll();
    },
    onError: (err) => toast.error(err instanceof ApiError ? err.message : "Daily planning failed"),
  });

  const approve = useMutation({
    mutationFn: (variantId: string) => api.post(`/workspaces/${workspace!.id}/content/variants/${variantId}/approve`),
    onSuccess: () => { toast.success("Approved"); invalidateAll(); },
    onError: (err) => toast.error(err instanceof ApiError ? err.message : "Approve failed"),
  });

  const reject = useMutation({
    mutationFn: (variantId: string) => api.post(`/workspaces/${workspace!.id}/content/variants/${variantId}/reject`, { reason: "" }),
    onSuccess: () => { toast.success("Rejected"); invalidateAll(); },
    onError: (err) => toast.error(err instanceof ApiError ? err.message : "Reject failed"),
  });

  const schedule = useMutation({
    mutationFn: ({ variantId, scheduledAt }: { variantId: string; scheduledAt: string }) =>
      api.post(`/workspaces/${workspace!.id}/content/variants/${variantId}/schedule`, { scheduled_at: new Date(scheduledAt).toISOString() }),
    onSuccess: () => { toast.success("Scheduled"); setSchedulingId(null); invalidateAll(); },
    onError: (err) => toast.error(err instanceof ApiError ? err.message : "Schedule failed"),
  });

  const publishNow = useMutation({
    mutationFn: (variantId: string) => api.post<{ status: string; message?: string }>(`/workspaces/${workspace!.id}/content/variants/${variantId}/publish-now`),
    onSuccess: (result) => {
      if (result.status === "manual_action_required") toast(result.message || "Not connected — copy this draft and post it manually.");
      else if (result.status === "published") toast.success("Published");
      else toast.error(result.message || "Publish failed");
      invalidateAll();
    },
    onError: (err) => toast.error(err instanceof ApiError ? err.message : "Publish failed"),
  });

  const regenerate = useMutation({
    mutationFn: (variantId: string) => api.post(`/workspaces/${workspace!.id}/content/variants/${variantId}/regenerate`),
    onSuccess: () => { toast.success("Regenerated"); invalidateAll(); },
    onError: (err) => toast.error(err instanceof ApiError ? err.message : "Regenerate failed"),
  });

  const generateVideo = useMutation({
    mutationFn: (variantId: string) => api.post(`/workspaces/${workspace!.id}/videos/generate`, { content_variant_id: variantId, aspect_ratio: "9:16" }),
    onSuccess: () => { toast.success("Video generated — see it in the Video Library"); queryClient.invalidateQueries({ queryKey: ["videos"] }); invalidateAll(); },
    onError: (err) => toast.error(err instanceof ApiError ? err.message : "Video generation failed"),
  });

  if (!product) {
    return <EmptyState icon={PenSquare} title="Select a product" description="Choose a product to generate content." />;
  }

  const filteredContent = (allContent ?? []).filter((item) => {
    if (libraryFilter === "all") return true;
    return item.variants.some((v) => v.status === libraryFilter);
  });

  const groupedCalendar = (calendarItems ?? []).reduce<Record<string, ContentVariant[]>>((acc, v) => {
    const when = v.scheduled_at || v.published_at || "";
    const day = when ? when.slice(0, 10) : "unscheduled";
    (acc[day] ??= []).push(v);
    return acc;
  }, {});

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="Content"
        description="Reach researches the market and plans, generates, and queues your daily content — grounded in your Brand Brain."
        action={
          <div className="flex gap-2">
            <Button size="sm" variant="secondary" onClick={() => planToday.mutate()} disabled={planToday.isPending}>
              <Rocket className="mr-1.5 h-3.5 w-3.5" /> {planToday.isPending ? "Planning…" : "Plan Today"}
            </Button>
            <Button size="sm" onClick={() => setOpen(true)}>
              <Sparkles className="mr-1.5 h-4 w-4" /> New idea
            </Button>
          </div>
        }
      />

      <Tabs defaultValue="queue" className="mb-4">
        <TabsList>
          <TabsTrigger value="queue">Approval Queue{queue && queue.length > 0 ? ` (${queue.length})` : ""}</TabsTrigger>
          <TabsTrigger value="calendar">Calendar</TabsTrigger>
          <TabsTrigger value="library">Library</TabsTrigger>
        </TabsList>

        <TabsContent value="queue">
          {queue && queue.length > 0 ? (
            <div className="flex flex-col gap-3">
              {queue.map((v) => (
                <VariantCard
                  key={v.id}
                  variant={v}
                  idea={contentById.get(v.content_id)?.idea}
                  contentType={contentById.get(v.content_id)?.content_type}
                  onApprove={() => approve.mutate(v.id)}
                  onReject={() => reject.mutate(v.id)}
                  onRegenerate={() => regenerate.mutate(v.id)}
                  onGenerateVideo={() => generateVideo.mutate(v.id)}
                  busy={approve.isPending || reject.isPending || regenerate.isPending}
                />
              ))}
            </div>
          ) : (
            <EmptyState icon={Sparkles} title="Queue is empty" description="Run Plan Today or generate a new idea to fill the approval queue." />
          )}
        </TabsContent>

        <TabsContent value="calendar">
          {Object.keys(groupedCalendar).length > 0 ? (
            <div className="flex flex-col gap-5">
              {Object.entries(groupedCalendar).sort(([a], [b]) => a.localeCompare(b)).map(([day, variants]) => (
                <div key={day}>
                  <p className="mb-2 flex items-center gap-1.5 text-xs font-medium text-[var(--muted-foreground)]">
                    <Calendar className="h-3.5 w-3.5" /> {day === "unscheduled" ? "Unscheduled" : day}
                  </p>
                  <div className="flex flex-col gap-2">
                    {variants.map((v) => (
                      <Card key={v.id}>
                        <CardContent className="flex items-center justify-between gap-3 p-3">
                          <div className="min-w-0">
                            <div className="flex items-center gap-2">
                              <Badge variant="outline">{v.channel}</Badge>
                              <Badge variant={STATUS_BADGE_VARIANT[v.status] ?? "muted"}>{v.status}</Badge>
                            </div>
                            <p className="mt-1 truncate text-xs text-[var(--muted-foreground)]">{v.body}</p>
                          </div>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState icon={Calendar} title="Nothing scheduled" description="Approve and schedule content to see it here." />
          )}
        </TabsContent>

        <TabsContent value="library">
          <div className="mb-4 flex flex-wrap items-center gap-1.5">
            {["all", "ready", "approved", "scheduled", "published", "failed", "rejected"].map((s) => (
              <Button key={s} size="sm" variant={libraryFilter === s ? "default" : "secondary"} onClick={() => setLibraryFilter(s)}>
                {s}
              </Button>
            ))}
          </div>

          {filteredContent.length > 0 ? (
            <div className="flex flex-col gap-4">
              {filteredContent.map((item) => (
                <Card key={item.id}>
                  <CardContent className="p-4">
                    <div className="mb-2 flex flex-wrap items-center gap-2">
                      <Badge variant="outline">{item.content_type}</Badge>
                      <Badge variant="muted">{item.origin}</Badge>
                    </div>
                    <p className="text-sm font-medium">{item.idea}</p>
                    <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
                      {item.variants.map((v) => (
                        <VariantCard
                          key={v.id}
                          variant={v}
                          compact
                          onApprove={() => approve.mutate(v.id)}
                          onReject={() => reject.mutate(v.id)}
                          onRegenerate={() => regenerate.mutate(v.id)}
                          onGenerateVideo={() => generateVideo.mutate(v.id)}
                          onPublishNow={() => publishNow.mutate(v.id)}
                          onOpenSchedule={() => { setSchedulingId(v.id); setScheduleValue(""); }}
                          scheduling={schedulingId === v.id}
                          scheduleValue={scheduleValue}
                          onScheduleValueChange={setScheduleValue}
                          onConfirmSchedule={() => schedule.mutate({ variantId: v.id, scheduledAt: scheduleValue })}
                          busy={approve.isPending || reject.isPending || regenerate.isPending || publishNow.isPending || schedule.isPending}
                        />
                      ))}
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          ) : (
            <EmptyState icon={PenSquare} title="Nothing here yet" description="Generate a new idea to see channel-specific drafts." action={<Button size="sm" onClick={() => setOpen(true)}>New idea</Button>} />
          )}
        </TabsContent>
      </Tabs>

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

function VariantCard({
  variant, idea, contentType, compact, busy,
  onApprove, onReject, onRegenerate, onGenerateVideo, onPublishNow,
  onOpenSchedule, scheduling, scheduleValue, onScheduleValueChange, onConfirmSchedule,
}: {
  variant: ContentVariant;
  idea?: string;
  contentType?: string;
  compact?: boolean;
  busy?: boolean;
  onApprove: () => void;
  onReject: () => void;
  onRegenerate: () => void;
  onGenerateVideo: () => void;
  onPublishNow?: () => void;
  onOpenSchedule?: () => void;
  scheduling?: boolean;
  scheduleValue?: string;
  onScheduleValueChange?: (v: string) => void;
  onConfirmSchedule?: () => void;
}) {
  return (
    <div className={compact ? "rounded-[var(--radius-sm)] border border-[var(--border)] p-3" : "rounded-[var(--radius-sm)] border border-[var(--border)] p-3.5"}>
      <div className="mb-1.5 flex flex-wrap items-center gap-2">
        <Badge variant="outline">{variant.channel}</Badge>
        <Badge variant={STATUS_BADGE_VARIANT[variant.status] ?? "muted"}>{variant.status}</Badge>
        {contentType && <Badge variant="muted">{contentType}</Badge>}
      </div>
      {idea && !compact && <p className="mb-1.5 text-xs font-medium">{idea}</p>}
      <p className="whitespace-pre-wrap text-xs text-[var(--muted-foreground)]">{variant.body}</p>
      {variant.cta && <p className="mt-1.5 text-[11px] font-medium text-[var(--accent)]">{variant.cta}</p>}

      {variant.status === "failed" && variant.quality_flags?.blocking_reasons && (
        <div className="mt-2 rounded-[var(--radius-sm)] bg-[var(--danger)]/10 p-2">
          {variant.quality_flags.blocking_reasons.map((reason, i) => (
            <p key={i} className="text-[11px] text-[var(--danger)]">— {reason}</p>
          ))}
        </div>
      )}
      {variant.status === "rejected" && variant.rejected_reason && (
        <p className="mt-2 text-[11px] text-[var(--muted-foreground)]">Rejected: {variant.rejected_reason}</p>
      )}

      <div className="mt-2.5 flex flex-wrap gap-1.5">
        {(variant.status === "ready" || variant.status === "approval_required") && (
          <>
            <Button size="sm" variant="secondary" onClick={onApprove} disabled={busy}>Approve</Button>
            <Button size="sm" variant="ghost" onClick={onReject} disabled={busy}>Reject</Button>
          </>
        )}
        {variant.status === "approved" && onOpenSchedule && (
          <>
            <Button size="sm" variant="secondary" onClick={onOpenSchedule} disabled={busy}>Schedule</Button>
            {onPublishNow && <Button size="sm" onClick={onPublishNow} disabled={busy}>Publish now</Button>}
          </>
        )}
        {variant.status === "scheduled" && onPublishNow && (
          <Button size="sm" variant="secondary" onClick={onPublishNow} disabled={busy}>Publish now</Button>
        )}
        {variant.status === "failed" && (
          <Button size="sm" variant="secondary" onClick={onRegenerate} disabled={busy}>Regenerate</Button>
        )}
        {(variant.status === "ready" || variant.status === "approved") && !variant.video_id && (
          <Button size="sm" variant="ghost" onClick={onGenerateVideo} disabled={busy}>
            <Clapperboard className="mr-1 h-3.5 w-3.5" /> Generate video
          </Button>
        )}
      </div>

      {scheduling && (
        <div className="mt-2 flex items-center gap-2">
          <Input type="datetime-local" value={scheduleValue} onChange={(e) => onScheduleValueChange?.(e.target.value)} className="h-8 text-xs" />
          <Button size="sm" onClick={onConfirmSchedule} disabled={!scheduleValue}>Confirm</Button>
        </div>
      )}
    </div>
  );
}
