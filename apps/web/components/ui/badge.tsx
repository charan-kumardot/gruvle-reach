import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium",
  {
    variants: {
      variant: {
        default: "border-transparent bg-[var(--accent-soft)] text-[var(--accent)]",
        outline: "border-[var(--border)] text-[var(--muted-foreground)]",
        success: "border-transparent bg-[color-mix(in_srgb,var(--success)_15%,transparent)] text-[var(--success)]",
        warning: "border-transparent bg-[color-mix(in_srgb,var(--warning)_15%,transparent)] text-[var(--warning)]",
        danger: "border-transparent bg-[color-mix(in_srgb,var(--danger)_15%,transparent)] text-[var(--danger)]",
        muted: "border-transparent bg-[var(--border-subtle)] text-[var(--muted-foreground)]",
      },
    },
    defaultVariants: { variant: "default" },
  }
);

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement>, VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant, className }))} {...props} />;
}
