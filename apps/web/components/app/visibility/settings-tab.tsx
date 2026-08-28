"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { api, ApiError } from "@/lib/api-client";
import { useAppStore } from "@/lib/store";
import type { ProductTruth, Website, WebsiteGuardrails } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

interface ProtectedPath {
  id: string;
  path_pattern: string;
  label: string;
}

const GUARDRAIL_LABELS: { key: keyof Omit<WebsiteGuardrails, "id" | "website_id">; label: string }[] = [
  { key: "protect_product_meaning", label: "Protect product meaning" },
  { key: "protect_brand_voice", label: "Protect brand voice" },
  { key: "protect_visual_design", label: "Protect visual design" },
  { key: "require_approval_content", label: "Require approval for content" },
  { key: "require_approval_code", label: "Require approval for code" },
  { key: "require_approval_production", label: "Require approval for production" },
  { key: "block_unsupported_claims", label: "Block unsupported claims" },
  { key: "run_build_checks", label: "Run build checks" },
  { key: "run_visual_checks", label: "Run visual checks" },
];

export function SettingsTab({ website }: { website: Website }) {
  const workspace = useAppStore((s) => s.workspace);
  const queryClient = useQueryClient();

  const { data: truth } = useQuery({
    queryKey: ["product-truth", website.product_id],
    queryFn: () => api.get<ProductTruth | null>(`/workspaces/${workspace!.id}/products/${website.product_id}/product-truth`),
    enabled: !!workspace,
  });

  const { data: guardrails } = useQuery({
    queryKey: ["website-guardrails", website.id],
    queryFn: () => api.get<WebsiteGuardrails>(`/workspaces/${workspace!.id}/websites/${website.id}/guardrails`),
    enabled: !!workspace,
  });

  const { data: protectedPaths } = useQuery({
    queryKey: ["protected-paths", website.id],
    queryFn: () => api.get<ProtectedPath[]>(`/workspaces/${workspace!.id}/websites/${website.id}/protected-paths`),
    enabled: !!workspace,
  });

  const [truthForm, setTruthForm] = useState({
    definition: "", problem: "", solution: "", positioning: "", target_customer: "",
    approved_claims: "", forbidden_claims: "",
  });

  useEffect(() => {
    if (truth) {
      setTruthForm({
        definition: truth.definition, problem: truth.problem, solution: truth.solution,
        positioning: truth.positioning, target_customer: truth.target_customer,
        approved_claims: truth.approved_claims.join("\n"), forbidden_claims: truth.forbidden_claims.join("\n"),
      });
    }
  }, [truth]);

  const saveTruth = useMutation({
    mutationFn: () =>
      api.put(`/workspaces/${workspace!.id}/products/${website.product_id}/product-truth`, {
        ...truthForm,
        approved_claims: truthForm.approved_claims.split("\n").map((s) => s.trim()).filter(Boolean),
        forbidden_claims: truthForm.forbidden_claims.split("\n").map((s) => s.trim()).filter(Boolean),
        core_features: truth?.core_features ?? [],
        competitors: truth?.competitors ?? [],
        differentiators: truth?.differentiators ?? [],
        brand_voice: truth?.brand_voice ?? "",
        pricing: truth?.pricing ?? "",
      }),
    onSuccess: () => {
      toast.success("Product Truth saved");
      queryClient.invalidateQueries({ queryKey: ["product-truth", website.product_id] });
    },
    onError: (err) => toast.error(err instanceof ApiError ? err.message : "Failed to save"),
  });

  const toggleGuardrail = useMutation({
    mutationFn: (next: WebsiteGuardrails) => api.put(`/workspaces/${workspace!.id}/websites/${website.id}/guardrails`, next),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["website-guardrails", website.id] }),
    onError: (err) => toast.error(err instanceof ApiError ? err.message : "Failed to update guardrails"),
  });

  const [newPath, setNewPath] = useState("");
  const addPath = useMutation({
    mutationFn: () => api.post(`/workspaces/${workspace!.id}/websites/${website.id}/protected-paths`, { path_pattern: newPath }),
    onSuccess: () => {
      setNewPath("");
      queryClient.invalidateQueries({ queryKey: ["protected-paths", website.id] });
    },
  });
  const removePath = useMutation({
    mutationFn: (id: string) => api.delete(`/workspaces/${workspace!.id}/websites/${website.id}/protected-paths/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["protected-paths", website.id] }),
  });

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader><CardTitle>Product Truth</CardTitle></CardHeader>
        <CardContent className="flex flex-col gap-3 pt-0">
          <p className="text-xs text-[var(--muted-foreground)]">
            Every proposed change is checked against this — AI can never introduce a claim that isn&apos;t supported here.
          </p>
          <div className="flex flex-col gap-1.5">
            <Label>Definition</Label>
            <Textarea value={truthForm.definition} onChange={(e) => setTruthForm({ ...truthForm, definition: e.target.value })} placeholder="What is this product, in one or two sentences?" />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Problem it solves</Label>
            <Textarea value={truthForm.problem} onChange={(e) => setTruthForm({ ...truthForm, problem: e.target.value })} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Solution</Label>
            <Textarea value={truthForm.solution} onChange={(e) => setTruthForm({ ...truthForm, solution: e.target.value })} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Approved claims (one per line)</Label>
            <Textarea value={truthForm.approved_claims} onChange={(e) => setTruthForm({ ...truthForm, approved_claims: e.target.value })} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Forbidden claims (one per line)</Label>
            <Textarea value={truthForm.forbidden_claims} onChange={(e) => setTruthForm({ ...truthForm, forbidden_claims: e.target.value })} placeholder="automatically prevents outages" />
          </div>
          <Button size="sm" className="self-start" onClick={() => saveTruth.mutate()} disabled={saveTruth.isPending}>
            {saveTruth.isPending ? "Saving…" : "Save Product Truth"}
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Website Guardrails</CardTitle></CardHeader>
        <CardContent className="flex flex-col gap-2 pt-0">
          {guardrails && GUARDRAIL_LABELS.map(({ key, label }) => (
            <label key={key} className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={guardrails[key]}
                onChange={(e) => toggleGuardrail.mutate({ ...guardrails, [key]: e.target.checked })}
                className="h-4 w-4 rounded border-[var(--border)] accent-[var(--accent)]"
              />
              {label}
            </label>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Protected paths</CardTitle></CardHeader>
        <CardContent className="flex flex-col gap-2 pt-0">
          <p className="text-xs text-[var(--muted-foreground)]">Files/directories the optimization agent can never modify — e.g. navigation, hero, pricing, billing.</p>
          <div className="flex gap-2">
            <Input value={newPath} onChange={(e) => setNewPath(e.target.value)} placeholder="components/navigation/*" />
            <Button size="sm" onClick={() => addPath.mutate()} disabled={!newPath || addPath.isPending}><Plus className="h-3.5 w-3.5" /></Button>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {protectedPaths?.map((p) => (
              <span key={p.id} className="flex items-center gap-1 rounded-full bg-[var(--border-subtle)] px-2.5 py-1 text-xs">
                {p.path_pattern}
                <button onClick={() => removePath.mutate(p.id)}><Trash2 className="h-3 w-3 text-[var(--muted-foreground)]" /></button>
              </span>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
