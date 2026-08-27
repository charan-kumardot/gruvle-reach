import { Badge } from "@/components/ui/badge";
import type { EvidenceStatus } from "@/lib/types";

const CONFIG: Record<EvidenceStatus, { label: string; variant: "success" | "default" | "warning" | "muted" }> = {
  fact: { label: "FACT", variant: "success" },
  hypothesis: { label: "HYPOTHESIS", variant: "default" },
  inference: { label: "INFERENCE", variant: "warning" },
  unknown: { label: "UNKNOWN", variant: "muted" },
};

export function EvidenceBadge({ status }: { status: EvidenceStatus }) {
  const config = CONFIG[status] ?? CONFIG.unknown;
  return <Badge variant={config.variant}>{config.label}</Badge>;
}
