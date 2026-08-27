"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Settings as SettingsIcon, Plug, CheckCircle2, XCircle } from "lucide-react";
import { toast } from "sonner";
import { api, ApiError } from "@/lib/api-client";
import { useAppStore } from "@/lib/store";
import type { IntegrationCatalogEntry } from "@/lib/types";
import { PageHeader } from "@/components/app/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

export default function SettingsPage() {
  const workspace = useAppStore((s) => s.workspace);
  const queryClient = useQueryClient();

  const { data: catalog } = useQuery({
    queryKey: ["integration-catalog", workspace?.id],
    queryFn: () => api.get<IntegrationCatalogEntry[]>(`/workspaces/${workspace!.id}/integrations/catalog`),
    enabled: !!workspace,
  });

  const connect = useMutation({
    mutationFn: (providerName: string) =>
      api.post(`/workspaces/${workspace!.id}/integrations/${providerName}/connect`, { credential_payload: {} }),
    onSuccess: () => {
      toast.success("Connected");
      queryClient.invalidateQueries({ queryKey: ["integration-catalog"] });
    },
    onError: (err) => toast.error(err instanceof ApiError ? err.message : "Connect failed (requires admin role)"),
  });

  const disconnect = useMutation({
    mutationFn: (providerName: string) => api.post(`/workspaces/${workspace!.id}/integrations/${providerName}/disconnect`),
    onSuccess: () => {
      toast.success("Disconnected");
      queryClient.invalidateQueries({ queryKey: ["integration-catalog"] });
    },
  });

  return (
    <div className="animate-fade-in">
      <PageHeader title="Settings" description="Workspace configuration and the integration marketplace." />

      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><SettingsIcon className="h-4 w-4" /> Workspace</CardTitle>
        </CardHeader>
        <CardContent className="pt-0 text-sm text-[var(--muted-foreground)]">
          {workspace?.name} {workspace?.is_demo && <Badge variant="muted" className="ml-2">DEMO</Badge>}
        </CardContent>
      </Card>

      <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold"><Plug className="h-4 w-4" /> Integration marketplace</h2>
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        {catalog?.map((entry) => (
          <Card key={entry.provider_name}>
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <p className="text-sm font-medium capitalize">{entry.provider_name.replace("_", " ")}</p>
                {entry.configured ? (
                  entry.connected ? (
                    <Badge variant="success"><CheckCircle2 className="mr-1 h-3 w-3" /> Connected</Badge>
                  ) : (
                    <Badge variant="warning">Configured</Badge>
                  )
                ) : (
                  <Badge variant="muted"><XCircle className="mr-1 h-3 w-3" /> Not configured</Badge>
                )}
              </div>
              <p className="mt-1.5 text-xs text-[var(--muted-foreground)]">{entry.notes || "No additional details."}</p>
              <div className="mt-2 flex flex-wrap gap-1">
                {Object.entries(entry.capabilities)
                  .filter(([k, v]) => typeof v === "boolean" && v && k !== "notes")
                  .map(([k]) => (
                    <Badge key={k} variant="outline">{k.replace("can_", "").replace("_", " ")}</Badge>
                  ))}
              </div>
              {entry.configured && (
                <div className="mt-3">
                  {entry.connected ? (
                    <Button size="sm" variant="secondary" onClick={() => disconnect.mutate(entry.provider_name)}>Disconnect</Button>
                  ) : (
                    <Button size="sm" onClick={() => connect.mutate(entry.provider_name)}>Connect</Button>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
