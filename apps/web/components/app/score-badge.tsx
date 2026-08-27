import { cn } from "@/lib/utils";

function tierFor(score: number): { label: string; color: string } {
  if (score >= 90) return { label: "Excellent", color: "var(--success)" };
  if (score >= 75) return { label: "Strong", color: "var(--accent)" };
  if (score >= 60) return { label: "Potential", color: "var(--warning)" };
  return { label: "Low priority", color: "var(--muted-foreground)" };
}

export function ScoreBadge({ score, showLabel = true, className }: { score: number; showLabel?: boolean; className?: string }) {
  const tier = tierFor(score);
  return (
    <div className={cn("inline-flex items-center gap-1.5", className)}>
      <span
        className="flex h-6 min-w-6 items-center justify-center rounded-full px-1.5 text-[11px] font-semibold"
        style={{ backgroundColor: `color-mix(in srgb, ${tier.color} 16%, transparent)`, color: tier.color }}
      >
        {Math.round(score)}
      </span>
      {showLabel && <span className="text-xs text-[var(--muted-foreground)]">{tier.label}</span>}
    </div>
  );
}
