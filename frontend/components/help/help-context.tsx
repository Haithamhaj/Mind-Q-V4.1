"use client"

import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react"

export type HelpSource = {
  label: string
  href?: string
  description?: string
}

export type HelpTopic = {
  id: string
  title: string
  summary: string
  body?: string
  detailItems?: string[]
  sources?: HelpSource[]
  suggestedQuestions?: string[]
  onAsk?: (() => void) | null
}

type HelpContextValue = {
  activeTopic: HelpTopic | null
  isPanelOpen: boolean
  openTopic: (topic: HelpTopic) => void
  closeTopic: () => void
}

const HelpContext = createContext<HelpContextValue | undefined>(undefined)

export function HelpProvider({ children }: { children: ReactNode }) {
  const [activeTopic, setActiveTopic] = useState<HelpTopic | null>(null)
  const [isPanelOpen, setIsPanelOpen] = useState(false)

  const openTopic = useCallback((topic: HelpTopic) => {
    setActiveTopic(topic)
    setIsPanelOpen(true)
  }, [])

  const closeTopic = useCallback(() => {
    setIsPanelOpen(false)
    setTimeout(() => {
      setActiveTopic(null)
    }, 200)
  }, [])

  const value = useMemo<HelpContextValue>(
    () => ({
      activeTopic,
      isPanelOpen,
      openTopic,
      closeTopic,
    }),
    [activeTopic, closeTopic, isPanelOpen, openTopic],
  )

  return <HelpContext.Provider value={value}>{children}</HelpContext.Provider>
}

export function useHelpCenter(): HelpContextValue {
  const context = useContext(HelpContext)
  if (!context) {
    throw new Error("useHelpCenter must be used within a HelpProvider")
  }
  return context
}
