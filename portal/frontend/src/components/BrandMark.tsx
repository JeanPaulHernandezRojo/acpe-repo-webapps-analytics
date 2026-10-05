import { cn } from "@/lib/utils";

/** Logo + nombre + subtítulo del portal. */

interface BrandMarkProps {
  name: string;
  subtitle: string;
  compact: boolean;
  className?: string;
}

export function BrandMark({ name, subtitle, compact, className }: BrandMarkProps) {
  return (
    <div className={cn("flex items-center gap-3", className)}>
      <img src="/logo.svg" alt="" className="size-9 shrink-0" />
      {!compact && (
        <div className="min-w-0">
          <div className="font-display text-[1.05rem] font-bold leading-tight tracking-wide text-primary-500">
            {name}
          </div>
          <div className="truncate text-[0.72rem] font-medium text-secondary-400">{subtitle}</div>
        </div>
      )}
    </div>
  );
}
