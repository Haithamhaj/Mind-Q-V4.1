"use client"

import type { ReactNode } from "react"
import { CircleHelp } from "lucide-react"

import { Button } from "@/components/ui/button"
import { useHelpCenter, type HelpTopic } from "@/components/help/help-context"
import { cn } from "@/lib/utils"

type HelpTriggerProps = {
  topicId: string
  buildTopic: () => Omit<HelpTopic, "id">
  className?: string
  "aria-label"?: string
  variant?: "icon" | "link"
  children?: ReactNode
}

export function HelpTrigger({ topicId, buildTopic, className, variant = "icon", children, ...rest }: HelpTriggerProps) {
  const { openTopic } = useHelpCenter()
  const handleOpen = () => {
    const topic = buildTopic()
    openTopic({ id: topicId, ...topic })
  }

  if (variant === "link") {
    return (
      <button
        type="button"
        onClick={handleOpen}
        className={cn(
          "inline-flex items-center gap-2 text-sm font-medium text-primary transition hover:text-primary/80",
          className,
        )}
        {...rest}
      >
        <CircleHelp className="h-4 w-4" />
        {children}
      </button>
    )
  }

  return (
    <Button
      type="button"
      variant="ghost"
      size="icon"
      onClick={handleOpen}
      className={cn("h-7 w-7 text-muted-foreground hover:text-primary", className)}
      {...rest}
    >
      <CircleHelp className="h-4 w-4" />
      <span className="sr-only">{rest["aria-label"]}</span>
    </Button>
  )
}
