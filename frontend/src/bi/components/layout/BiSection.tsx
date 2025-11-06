import React from "react";

import { cn } from "@/lib/utils";

export type BiSectionProps = {
  id?: string;
  title?: string;
  subtitle?: string;
  description?: string;
  actions?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  contentClassName?: string;
  headerClassName?: string;
};

export const BiSection: React.FC<BiSectionProps> = ({
  id,
  title,
  subtitle,
  description,
  actions,
  children,
  className,
  contentClassName,
  headerClassName,
}) => {
  const showHeader = Boolean(title || subtitle || description || actions);

  return (
    <section
      id={id}
      className={cn(
        "rounded-3xl border border-border/50 bg-background/80 shadow-sm shadow-black/5 backdrop-blur",
        "dark:border-border/40 dark:bg-background/60",
        className,
      )}
    >
      {showHeader ? (
        <header
          className={cn(
            "flex flex-col gap-2 border-b border-border/50 px-5 py-4 text-start",
            "sm:px-6 sm:py-5",
            "dark:border-border/30",
            headerClassName,
          )}
        >
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="space-y-1 text-start">
              {subtitle ? (
                <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground/80">
                  {subtitle}
                </span>
              ) : null}
              {title ? <h2 className="text-lg font-semibold text-foreground sm:text-xl">{title}</h2> : null}
            </div>
            {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
          </div>
          {description ? <p className="text-sm text-muted-foreground/90 sm:text-base">{description}</p> : null}
        </header>
      ) : null}
      <div className={cn("flex flex-col gap-4 px-5 py-5 sm:px-6 sm:py-6", contentClassName)}>{children}</div>
    </section>
  );
};

export default BiSection;
