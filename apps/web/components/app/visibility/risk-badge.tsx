import { Badge } from "@/components/ui/badge";
import type { RiskLevelType } from "@/lib/types";

const CONFIG: Record<RiskLevelType, { label: string; variant: "success" | "warning" | "danger" | "muted" }> = {
  low: { label: "LOW risk", variant: "success" },
  medium: { label: "MEDIUM risk", variant: "warning" },
  high: { label: "HIGH risk", variant: "danger" },
  critical: { label: "CRITICAL — blocked", variant: "danger" },
};

export function RiskBadge({ level }: { level: RiskLevelType }) {
  const config = CONFIG[level] ?? CONFIG.medium;
  return <Badge variant={config.variant}>{config.label}</Badge>;
}
