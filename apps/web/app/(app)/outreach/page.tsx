"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Send, Mail, ShieldCheck } from "lucide-react";
import { toast } from "sonner";
import { api, ApiError } from "@/lib/api-client";
import { useAppStore } from "@/lib/store";
import type { Company, Outreach } from "@/lib/types";
import { PageHeader } from "@/components/app/page-header";
import { EmptyState } from "@/components/app/empty-state";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";

export default function OutreachPage() {
  const { workspace, product } = useAppStore();
  const queryClient = useQueryClient();
  const [draftOpen, setDraftOpen] = useState(false);
  const [companyId, setCompanyId] = useState<string>("");

  const { data: outreach } = useQuery({
    queryKey: ["outreach", workspace?.id],
    queryFn: () => api.get<Outreach[]>(`/workspaces/${workspace!.id}/outreach`),
    enabled: !!workspace,
  });

  const { data: companies } = useQuery({
    queryKey: ["companies", workspace?.id, product?.id],
    queryFn: () => api.get<Company[]>(`/workspaces/${workspace!.id}/companies?product_id=${product!.id}`),
    enabled: !!workspace && !!product && draftOpen,
  });

  const draft = useMutation({
    mutationFn: () =>
      api.post<Outreach>(`/workspaces/${workspace!.id}/outreach/draft`, {
        product_id: product?.id,
        target_type: "company",
        target_id: companyId,
        channel: "email",
      }),
    onSuccess: () => {
      toast.success("Outreach drafted — review evidence before approving");
      setDraftOpen(false);
      queryClient.invalidateQueries({ queryKey: ["outreach"] });
    },
    onError: (err) => toast.error(err instanceof ApiError ? err.message : "Draft failed"),
  });

  if (!product) {
    return <EmptyState icon={Send} title="Select a product" description="Choose a product to draft outreach." />;
  }

  const companyById = new Map((companies ?? []).map((c) => [c.id, c]));

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="Outreach"
        description="Research → draft → your approval → send. Nothing goes out without you."
        action={<Button size="sm" onClick={() => setDraftOpen(true)}><Send className="mr-1.5 h-4 w-4" /> Draft outreach</Button>}
      />

      {outreach && outreach.length > 0 ? (
        <div className="flex flex-col gap-3">
          {outreach.map((o) => (
            <OutreachRow key={o.id} outreach={o} companyName={companyById.get(o.target_id)?.name} />
          ))}
        </div>
      ) : (
        <EmptyState icon={Send} title="No outreach yet" description="Draft a personalized, evidence-grounded message for a target company." action={<Button size="sm" onClick={() => setDraftOpen(true)}>Draft outreach</Button>} />
      )}

      <Dialog open={draftOpen} onOpenChange={setDraftOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Draft outreach</DialogTitle>
            <DialogDescription>AI drafts a personalized message grounded only in evidence about this company — you approve before anything sends.</DialogDescription>
          </DialogHeader>
          <form className="flex flex-col gap-3" onSubmit={(e) => { e.preventDefault(); draft.mutate(); }}>
            <Select value={companyId} onValueChange={setCompanyId}>
              <SelectTrigger><SelectValue placeholder="Select a company" /></SelectTrigger>
              <SelectContent>
                {(companies ?? []).map((c) => (
                  <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button type="submit" disabled={!companyId || draft.isPending}>{draft.isPending ? "Drafting…" : "Draft message"}</Button>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function OutreachRow({ outreach, companyName }: { outreach: Outreach; companyName?: string }) {
  const workspace = useAppStore((s) => s.workspace);
  const queryClient = useQueryClient();
  const [sendOpen, setSendOpen] = useState(false);
  const [toEmail, setToEmail] = useState("");
  const message = outreach.messages[outreach.messages.length - 1];

  const approve = useMutation({
    mutationFn: () => api.post(`/workspaces/${workspace!.id}/outreach/${outreach.id}/messages/${message.id}/approve`),
    onSuccess: () => {
      toast.success("Message approved");
      queryClient.invalidateQueries({ queryKey: ["outreach"] });
    },
    onError: (err) => toast.error(err instanceof ApiError ? err.message : "Approval failed"),
  });

  const send = useMutation({
    mutationFn: () =>
      api.post(`/workspaces/${workspace!.id}/outreach/${outreach.id}/messages/${message.id}/send`, {
        to_email: toEmail,
        subject: `A quick note re: ${companyName ?? "your team"}`,
      }),
    onSuccess: () => {
      toast.success("Sent");
      setSendOpen(false);
      queryClient.invalidateQueries({ queryKey: ["outreach"] });
    },
    onError: (err) => toast.error(err instanceof ApiError ? err.message : "Send failed — is an email provider configured?"),
  });

  return (
    <Card>
      <CardContent className="p-4">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <p className="text-sm font-medium">{companyName ?? outreach.target_type}</p>
            <Badge variant="outline">{outreach.channel}</Badge>
            <Badge>{outreach.status}</Badge>
          </div>
          <div className="flex gap-1.5">
            {message?.status === "drafted" && (
              <Button size="sm" variant="secondary" onClick={() => approve.mutate()} disabled={approve.isPending}>
                <ShieldCheck className="mr-1.5 h-3.5 w-3.5" /> Approve
              </Button>
            )}
            {message?.status === "approved" && (
              <Button size="sm" onClick={() => setSendOpen(true)}>
                <Mail className="mr-1.5 h-3.5 w-3.5" /> Send
              </Button>
            )}
          </div>
        </div>
        {message && <p className="mt-2 whitespace-pre-wrap text-xs text-[var(--muted-foreground)]">{message.draft_body}</p>}
      </CardContent>

      <Dialog open={sendOpen} onOpenChange={setSendOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Send via email</DialogTitle>
            <DialogDescription>Sends through your configured email provider (Resend/SMTP). Tracked in the outreach timeline.</DialogDescription>
          </DialogHeader>
          <form className="flex flex-col gap-3" onSubmit={(e) => { e.preventDefault(); send.mutate(); }}>
            <Input required type="email" value={toEmail} onChange={(e) => setToEmail(e.target.value)} placeholder="recipient@company.com" />
            <Button type="submit" disabled={send.isPending}>{send.isPending ? "Sending…" : "Send email"}</Button>
          </form>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
