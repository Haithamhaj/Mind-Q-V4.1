"use client"

import { useEffect, useRef } from "react"
import { MessageSquare, X } from "lucide-react"

import { useHelpCenter } from "@/components/help/help-context"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { useLanguage } from "@/context/language-context"
import { cn } from "@/lib/utils"

export function HelpPanel() {
  const { activeTopic, isPanelOpen, closeTopic } = useHelpCenter()
  const { translate } = useLanguage()
  const panelRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    if (!panelRef.current || !isPanelOpen) return
    panelRef.current.focus({ preventScroll: true })
  }, [isPanelOpen])

  if (!isPanelOpen || !activeTopic) {
    return null
  }

  return (
    <>
      <div className="fixed inset-0 z-40 bg-background/60 backdrop-blur-sm" aria-hidden="true" onClick={closeTopic} />

      <aside
        ref={panelRef}
        tabIndex={-1}
        className={cn(
          "fixed inset-y-0 right-0 z-50 flex w-full max-w-md flex-col border-l border-border bg-card shadow-2xl outline-none transition-transform duration-200",
          isPanelOpen ? "translate-x-0" : "translate-x-full",
        )}
      >
        <header className="border-b border-border p-5">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-primary">
                {translate("Guided explanation")}
              </p>
              <h2 className="mt-1 text-xl font-semibold text-foreground">{activeTopic.title}</h2>
            </div>
            <Button variant="ghost" size="icon" onClick={closeTopic} aria-label={translate("Close panel")}>
              <X className="h-4 w-4" />
            </Button>
          </div>
          <p className="mt-3 text-sm text-muted-foreground">{activeTopic.summary}</p>
        </header>

        <ScrollArea className="flex-1 px-5 py-4">
          <div className="space-y-6">
            {activeTopic.body ? <p className="text-sm leading-6 text-foreground">{activeTopic.body}</p> : null}

            {activeTopic.detailItems && activeTopic.detailItems.length > 0 ? (
              <div className="space-y-2">
                <h3 className="text-sm font-semibold text-foreground">{translate("Key takeaways")}</h3>
                <ul className="space-y-2 text-sm leading-6 text-muted-foreground">
                  {activeTopic.detailItems.map((detail, index) => (
                    <li key={`${activeTopic.id}-detail-${index}`} className="flex items-start gap-2">
                      <span className="mt-1 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-primary" />
                      <span>{detail}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            {activeTopic.sources && activeTopic.sources.length > 0 ? (
              <div className="space-y-2">
                <h3 className="text-sm font-semibold text-foreground">{translate("Source links")}</h3>
                <ul className="space-y-2 text-sm text-muted-foreground">
                  {activeTopic.sources.map((source, index) => (
                    <li key={`${activeTopic.id}-source-${index}`} className="rounded-md border border-border/40 p-3">
                      <p className="font-medium text-foreground">{source.label}</p>
                      {source.description ? <p className="mt-1 text-xs text-muted-foreground">{source.description}</p> : null}
                      {source.href ? (
                        <a
                          href={source.href}
                          className="mt-2 inline-flex text-xs font-semibold text-primary hover:underline"
                          target="_blank"
                          rel="noreferrer"
                        >
                          {translate("Open document")}
                        </a>
                      ) : null}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            {activeTopic.suggestedQuestions && activeTopic.suggestedQuestions.length > 0 ? (
              <div className="space-y-2">
                <h3 className="text-sm font-semibold text-foreground">{translate("Suggested questions")}</h3>
                <ul className="space-y-1 text-sm text-muted-foreground">
                  {activeTopic.suggestedQuestions.map((question, index) => (
                    <li key={`${activeTopic.id}-question-${index}`} className="rounded border border-border/30 bg-muted/30 px-3 py-2">
                      {question}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </div>
        </ScrollArea>

        <footer className="border-t border-border px-5 py-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            {activeTopic.onAsk ? (
              <Button
                className="w-full justify-start gap-2 sm:w-auto"
                variant="secondary"
                onClick={() => {
                  activeTopic.onAsk?.()
                  closeTopic()
                }}
              >
                <MessageSquare className="h-4 w-4" />
                {translate("Ask the assistant")}
              </Button>
            ) : null}
            <Button className="w-full sm:w-auto" onClick={closeTopic}>
              {translate("Close")}
            </Button>
          </div>
        </footer>
      </aside>
    </>
  )
}
