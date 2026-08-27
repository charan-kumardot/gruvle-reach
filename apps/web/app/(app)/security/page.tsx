"use client";

import { useQuery } from "@tanstack/react-query";
import { Shield, Download } from "lucide-react";
import { api } from "@/lib/api-client";
import { useAppStore } from "@/lib/store";
import { PageHeader } from "@/components/app/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

interface AuditLogRow {
  id: string;
  action: string;
  resource_type: string;
  resource_id: string;
  created_at: string;
}

const EXPORTABLE = ["companies", "investors", "opportunities"];

export default function SecurityPage() {
  const workspace = useAppStore((s) => s.workspace);

  const { data: logs } = useQuery({
    queryKey: ["audit-logs", workspace?.id],
    queryFn: () => api.get<AuditLogRow[]>(`/workspaces/${workspace!.id}/audit-logs`),
    enabled: !!workspace,
  });

  function exportEntity(entity: string) {
    const token = window.localStorage.getItem("gruvle_token");
    const base = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
    fetch(`${base}/api/v1/workspaces/${workspace!.id}/export/${entity}?format=csv`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => r.blob())
      .then((blob) => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `${entity}.csv`;
        a.click();
        URL.revokeObjectURL(url);
      });
  }

  return (
    <div className="animate-fade-in">
      <PageHeader title="Security" description="Audit trail, credential handling, and data controls." />

      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><Shield className="h-4 w-4" /> Data handling</CardTitle>
        </CardHeader>
        <CardContent className="pt-0 text-xs text-[var(--muted-foreground)] flex flex-col gap-1">
          <p>• Integration credentials are encrypted at rest and never appear in logs.</p>
          <p>• Every external send (email, social) requires human approval before it executes.</p>
          <p>• Research requests are blocked from reaching private networks and cloud metadata endpoints.</p>
        </CardContent>
      </Card>

      <Card className="mb-6">
        <CardHeader><CardTitle>Export data</CardTitle></CardHeader>
        <CardContent className="flex flex-wrap gap-2 pt-0">
          {EXPORTABLE.map((e) => (
            <Button key={e} size="sm" variant="secondary" onClick={() => exportEntity(e)}>
              <Download className="mr-1.5 h-3.5 w-3.5" /> {e}
            </Button>
          ))}
        </CardContent>
      </Card>

      <h2 className="mb-3 text-sm font-semibold">Audit log</h2>
      <div className="flex flex-col gap-1.5">
        {logs?.map((log) => (
          <div key={log.id} className="flex items-center justify-between rounded-[var(--radius-sm)] border border-[var(--border)] px-3 py-2 text-xs">
            <div className="flex items-center gap-2">
              <Badge variant="outline">{log.action}</Badge>
              <span className="text-[var(--muted-foreground)]">{log.resource_type}</span>
            </div>
            <span className="text-[var(--muted-foreground)]">{new Date(log.created_at).toLocaleString()}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
