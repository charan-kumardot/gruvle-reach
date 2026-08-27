import type { LucideIcon } from "lucide-react";

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
}: {
  icon: LucideIcon;
  title: string;
  description: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-[var(--radius-lg)] border border-dashed border-[var(--border)] px-6 py-16 text-center">
      <div className="flex h-10 w-10 items-center justify-center rounded-full bg-[var(--border-subtle)]">
        <Icon className="h-5 w-5 text-[var(--muted-foreground)]" />
      </div>
      <div>
        <p className="text-sm font-medium">{title}</p>
        <p className="mt-1 max-w-sm text-xs text-[var(--muted-foreground)]">{description}</p>
      </div>
      {action}
    </div>
  );
}
