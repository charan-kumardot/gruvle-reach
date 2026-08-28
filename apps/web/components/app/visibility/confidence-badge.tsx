import { Badge } from "@/components/ui/badge";
import type { ConfidenceLabelType } from "@/lib/types";

const CONFIG: Record<ConfidenceLabelType, { label: string; variant: "success" | "warning" | "muted" }> = {
  verified: { label: "VERIFIED", variant: "success" },
  estimated: { label: "ESTIMATED", variant: "warning" },
  unknown: { label: "UNKNOWN", variant: "muted" },
};

export function ConfidenceBadge({ label }: { label: ConfidenceLabelType }) {
  const config = CONFIG[label] ?? CONFIG.unknown;
  return <Badge variant={config.variant}>{config.label}</Badge>;
}
