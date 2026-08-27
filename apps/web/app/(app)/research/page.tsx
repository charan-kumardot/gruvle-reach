"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Search, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { api, ApiError } from "@/lib/api-client";
import { useAppStore } from "@/lib/store";
import type { EvidenceStatus } from "@/lib/types";
import { PageHeader } from "@/components/app/page-header";
import { EmptyState } from "@/components/app/empty-state";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { EvidenceBadge } from "@/components/app/evidence-badge";

interface ResearchSource {
  id: string;
  url: string;
  name: string;
  source_type: string;
  is_active: boolean;
}

interface EvidenceRow {
  id: string;
  claim: string;
  evidence_snippet: string;
  source_url: string;
  confidence: number;
  status: EvidenceStatus;
  related_entity_type: string;
}

export default function ResearchPage() {
  const { workspace } = useAppStore();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [url, setUrl] = useState("");

  const { data: sources } = useQuery({
    queryKey: ["research-sources", workspace?.id],
    queryFn: () => api.get<ResearchSource[]>(`/workspaces/${workspace!.id}/research/sources`),
    enabled: !!workspace,
  });

  const { data: evidence } = useQuery({
    queryKey: ["evidence", workspace?.id],
    queryFn: () => api.get<EvidenceRow[]>(`/workspaces/${workspace!.id}/research/evidence`),
    enabled: !!workspace,
  });

  const addSource = useMutation({
    mutationFn: () => api.post(`/workspaces/${workspace!.id}/research/sources`, { url, name: url, source_type: "user_submitted" }),
    onSuccess: () => {
      toast.success("Source added");
      setOpen(false);
      setUrl("");
      queryClient.invalidateQueries({ queryKey: ["research-sources"] });
    },
    onError: (err) => toast.error(err instanceof ApiError ? err.message : "Failed to add source (requires admin role)"),
  });

  const removeSource = useMutation({
    mutationFn: (id: string) => api.delete(`/workspaces/${workspace!.id}/research/sources/${id}`),
    onSuccess: () => {
      toast.success("Source removed");
      queryClient.invalidateQueries({ queryKey: ["research-sources"] });
    },
  });

  return (
    <div className="animate-fade-in">
      <PageHeader title="Research" description="Sources and the evidence ledger behind every claim in the system." />

      <Tabs defaultValue="evidence">
        <TabsList>
          <TabsTrigger value="evidence">Evidence</TabsTrigger>
          <TabsTrigger value="sources">Sources</TabsTrigger>
        </TabsList>

        <TabsContent value="evidence">
          {evidence && evidence.length > 0 ? (
            <div className="flex flex-col gap-2">
              {evidence.map((e) => (
                <Card key={e.id}>
                  <CardContent className="p-3.5">
                    <div className="flex items-start justify-between gap-2">
                      <p className="text-sm">{e.claim}</p>
                      <EvidenceBadge status={e.status} />
                    </div>
                    {e.evidence_snippet && <p className="mt-1.5 text-xs text-[var(--muted-foreground)]">&quot;{e.evidence_snippet}&quot;</p>}
                    <div className="mt-2 flex items-center gap-2 text-[11px] text-[var(--muted-foreground)]">
                      <a href={e.source_url} target="_blank" rel="noreferrer" className="truncate hover:text-[var(--accent)]">{e.source_url}</a>
                      <Badge variant="outline">{Math.round(e.confidence * 100)}% confidence</Badge>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          ) : (
            <EmptyState icon={Search} title="No evidence yet" description="Evidence accumulates automatically as research runs across companies, investors, and competitors." />
          )}
        </TabsContent>

        <TabsContent value="sources">
          <div className="mb-3">
            <Button size="sm" onClick={() => setOpen(true)}><Plus className="mr-1.5 h-4 w-4" /> Add source</Button>
          </div>
          {sources && sources.length > 0 ? (
            <div className="flex flex-col gap-2">
              {sources.map((s) => (
                <Card key={s.id}>
                  <CardContent className="flex items-center justify-between p-3.5">
                    <div className="min-w-0">
                      <p className="truncate text-sm">{s.url}</p>
                      <Badge variant="outline" className="mt-1">{s.source_type}</Badge>
                    </div>
                    <Button size="icon" variant="ghost" onClick={() => removeSource.mutate(s.id)}>
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </CardContent>
                </Card>
              ))}
            </div>
          ) : (
            <EmptyState icon={Search} title="No manual sources" description="Add specific URLs, RSS feeds, or sitemaps for the research engine to monitor." action={<Button size="sm" onClick={() => setOpen(true)}>Add source</Button>} />
          )}
        </TabsContent>
      </Tabs>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>Add research source</DialogTitle></DialogHeader>
          <form className="flex flex-col gap-3" onSubmit={(e) => { e.preventDefault(); addSource.mutate(); }}>
            <Input required value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://example.com/blog/feed.xml" />
            <Button type="submit" disabled={addSource.isPending}>{addSource.isPending ? "Adding…" : "Add source"}</Button>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
