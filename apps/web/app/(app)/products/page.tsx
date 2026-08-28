"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Package, Plus, Rocket, Sparkles, Trash2, Wand2 } from "lucide-react";
import { toast } from "sonner";
import { api, ApiError } from "@/lib/api-client";
import { useAppStore } from "@/lib/store";
import type { ICPProfile, Product, ProductProfile, ResearchRun } from "@/lib/types";
import { PageHeader } from "@/components/app/page-header";
import { EmptyState } from "@/components/app/empty-state";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input, Textarea } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ScoreBadge } from "@/components/app/score-badge";

export default function ProductsPage() {
  const { workspace, product: selected, setProduct } = useAppStore();
  const queryClient = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const [form, setForm] = useState({ name: "", website: "", description: "", category: "" });
  const [deleteTarget, setDeleteTarget] = useState<Product | null>(null);

  const { data: products } = useQuery({
    queryKey: ["products", workspace?.id],
    queryFn: () => api.get<Product[]>(`/workspaces/${workspace!.id}/products`),
    enabled: !!workspace,
  });

  const createProduct = useMutation({
    mutationFn: () => api.post<Product>(`/workspaces/${workspace!.id}/products`, form),
    onSuccess: (product) => {
      toast.success("Product created");
      setCreateOpen(false);
      setForm({ name: "", website: "", description: "", category: "" });
      queryClient.invalidateQueries({ queryKey: ["products", workspace?.id] });
      setProduct(product);
    },
    onError: (err) => toast.error(err instanceof ApiError ? err.message : "Failed to create product"),
  });

  const deleteProduct = useMutation({
    mutationFn: (id: string) => api.delete(`/workspaces/${workspace!.id}/products/${id}`),
    onSuccess: (_data, id) => {
      toast.success("Product deleted");
      setDeleteTarget(null);
      queryClient.invalidateQueries({ queryKey: ["products", workspace?.id] });
      if (selected?.id === id) setProduct(null);
    },
    onError: (err) => toast.error(err instanceof ApiError ? err.message : "Delete failed — requires the admin role"),
  });

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="Products"
        description="Every Gruvle product researched independently."
        action={
          <Button size="sm" onClick={() => setCreateOpen(true)}>
            <Plus className="mr-1.5 h-4 w-4" /> New product
          </Button>
        }
      />

      {products && products.length > 0 ? (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {products.map((p) => (
            <ProductCard
              key={p.id}
              product={p}
              selected={selected?.id === p.id}
              onSelect={() => setProduct(p)}
              onDelete={() => setDeleteTarget(p)}
            />
          ))}
        </div>
      ) : (
        <EmptyState
          icon={Package}
          title="No products yet"
          description="Create your first product — e.g. Gruvle Radar — and Gruvle Reach will start researching its market."
          action={<Button size="sm" onClick={() => setCreateOpen(true)}>Create product</Button>}
        />
      )}

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>New product</DialogTitle>
          </DialogHeader>
          <form
            className="flex flex-col gap-3"
            onSubmit={(e) => {
              e.preventDefault();
              createProduct.mutate();
            }}
          >
            <div className="flex flex-col gap-1.5">
              <Label>Name</Label>
              <Input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Gruvle Radar" />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label>Website</Label>
              <Input value={form.website} onChange={(e) => setForm({ ...form, website: e.target.value })} placeholder="https://gruvle.com" />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label>Category</Label>
              <Input value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} placeholder="B2B SaaS" />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label>Description</Label>
              <Textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="AI-powered change intelligence for businesses." />
            </div>
            <Button type="submit" className="mt-1" disabled={createProduct.isPending}>
              {createProduct.isPending ? "Creating…" : "Create product"}
            </Button>
          </form>
        </DialogContent>
      </Dialog>

      <Dialog open={!!deleteTarget} onOpenChange={(v) => !v && setDeleteTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete {deleteTarget?.name}?</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-[var(--muted-foreground)]">
            This permanently deletes the product and everything researched under it — companies, ICPs, investor
            matches, content, campaigns, outreach, and competitor tracking. This can&apos;t be undone.
          </p>
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setDeleteTarget(null)} disabled={deleteProduct.isPending}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={() => deleteTarget && deleteProduct.mutate(deleteTarget.id)}
              disabled={deleteProduct.isPending}
            >
              {deleteProduct.isPending ? "Deleting…" : "Delete product"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function ProductCard({
  product, selected, onSelect, onDelete,
}: {
  product: Product; selected: boolean; onSelect: () => void; onDelete: () => void;
}) {
  const workspace = useAppStore((s) => s.workspace);
  const queryClient = useQueryClient();

  const { data: profile } = useQuery({
    queryKey: ["product-profile", product.id],
    queryFn: () => api.get<ProductProfile | null>(`/workspaces/${workspace!.id}/products/${product.id}/profile`),
    enabled: !!workspace,
  });

  const { data: icps } = useQuery({
    queryKey: ["icps", product.id],
    queryFn: () => api.get<ICPProfile[]>(`/workspaces/${workspace!.id}/products/${product.id}/icp`),
    enabled: !!workspace,
  });

  const understand = useMutation({
    mutationFn: () => api.post<ProductProfile>(`/workspaces/${workspace!.id}/products/${product.id}/understand`),
    onSuccess: () => {
      toast.success("AI product understanding generated");
      queryClient.invalidateQueries({ queryKey: ["product-profile", product.id] });
    },
    onError: (err) =>
      toast.error(err instanceof ApiError ? err.message : "AI understanding failed — check your AI_PROVIDER config"),
  });

  const generateIcp = useMutation({
    mutationFn: () => api.post<ICPProfile[]>(`/workspaces/${workspace!.id}/products/${product.id}/icp/generate`),
    onSuccess: () => {
      toast.success("ICP hypotheses generated");
      queryClient.invalidateQueries({ queryKey: ["icps", product.id] });
    },
    onError: (err) => toast.error(err instanceof ApiError ? err.message : "ICP generation failed"),
  });

  const runDiscovery = useMutation({
    mutationFn: () => api.post<ResearchRun>(`/workspaces/${workspace!.id}/products/${product.id}/autonomous-discovery`),
    onSuccess: (run) => {
      const summary = run.result_summary as { companies_found?: number; triggers_found?: number };
      toast.success(
        run.status === "completed"
          ? `Discovery complete — ${summary.companies_found ?? 0} companies, ${summary.triggers_found ?? 0} triggers found`
          : `Discovery ${run.status}${run.error ? `: ${run.error}` : ""}`,
      );
      queryClient.invalidateQueries({ queryKey: ["companies"] });
      queryClient.invalidateQueries({ queryKey: ["product-profile", product.id] });
      queryClient.invalidateQueries({ queryKey: ["icps", product.id] });
    },
    onError: (err) => toast.error(err instanceof ApiError ? err.message : "Autonomous discovery failed"),
  });

  return (
    <Card className={selected ? "ring-2 ring-[var(--ring)]" : ""} onClick={onSelect}>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>{product.name}</CardTitle>
          <div className="flex items-center gap-1.5">
            {product.is_demo && <Badge variant="muted">DEMO</Badge>}
            <Button
              size="icon"
              variant="ghost"
              className="h-7 w-7 text-[var(--muted-foreground)] hover:text-[var(--danger)]"
              onClick={(e) => { e.stopPropagation(); onDelete(); }}
              aria-label={`Delete ${product.name}`}
            >
              <Trash2 className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>
        <CardDescription>{product.description || "No description yet."}</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-3 pt-0">
        {profile ? (
          <div className="flex flex-col gap-1 text-xs text-[var(--muted-foreground)]">
            <p><span className="font-medium text-[var(--foreground)]">Category:</span> {profile.product_category}</p>
            <p><span className="font-medium text-[var(--foreground)]">Buyer:</span> {profile.primary_buyer}</p>
          </div>
        ) : (
          <p className="text-xs text-[var(--muted-foreground)]">AI hasn&apos;t analyzed this product yet.</p>
        )}

        {icps && icps.length > 0 && (
          <div className="flex flex-col gap-1.5">
            <p className="text-xs font-medium text-[var(--muted-foreground)]">ICP hypotheses</p>
            {icps.slice(0, 2).map((icp) => (
              <div key={icp.id} className="flex items-center justify-between gap-2 rounded-[var(--radius-sm)] bg-[var(--border-subtle)] px-2 py-1.5">
                <span className="truncate text-xs">{icp.name}</span>
                <ScoreBadge score={icp.score} showLabel={false} />
              </div>
            ))}
          </div>
        )}

        <div className="flex gap-2 pt-1">
          <Button
            size="sm"
            variant="secondary"
            onClick={(e) => {
              e.stopPropagation();
              understand.mutate();
            }}
            disabled={understand.isPending}
          >
            <Wand2 className="mr-1.5 h-3.5 w-3.5" /> {understand.isPending ? "Analyzing…" : "AI understand"}
          </Button>
          <Button
            size="sm"
            variant="secondary"
            onClick={(e) => {
              e.stopPropagation();
              generateIcp.mutate();
            }}
            disabled={generateIcp.isPending}
          >
            <Sparkles className="mr-1.5 h-3.5 w-3.5" /> {generateIcp.isPending ? "Generating…" : "Generate ICP"}
          </Button>
          <Button
            size="sm"
            onClick={(e) => {
              e.stopPropagation();
              runDiscovery.mutate();
            }}
            disabled={runDiscovery.isPending}
          >
            <Rocket className="mr-1.5 h-3.5 w-3.5" /> {runDiscovery.isPending ? "Running…" : "Run Autonomous Discovery"}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
