"use client"

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react"

import { DEFAULT_LOCALE, LANGUAGES, dictionaries, getDirection } from "@/lib/i18n"

export type Language = (typeof LANGUAGES)[number]["code"]

const STORAGE_KEY = "mindq.preferred-language"

type LanguageContextValue = {
  language: Language
  setLanguage: (language: Language) => void
  toggleLanguage: () => void
  translate: (template: string, replacements?: Record<string, string | number>) => string
}

const LanguageContext = createContext<LanguageContextValue | undefined>(undefined)

const applyReplacements = (template: string, replacements?: Record<string, string | number>) => {
  if (!replacements) {
    return template
  }

  return template.replace(/\{(\w+)\}/g, (_, key: string) => {
    const value = replacements[key]
    return value === undefined || value === null ? `{${key}}` : String(value)
  })
}

const loadInitialLanguage = (): Language => {
  if (typeof window === "undefined") {
    return DEFAULT_LOCALE
  }

  const stored = window.localStorage.getItem(STORAGE_KEY)
  if (stored && (stored === "en" || stored === "ar")) {
    return stored
  }

  return DEFAULT_LOCALE
}

export function LanguageProvider({ children }: { children: React.ReactNode }) {
  const [language, setLanguageState] = useState<Language>(() => loadInitialLanguage())

  useEffect(() => {
    if (typeof window === "undefined") {
      return
    }
    const stored = window.localStorage.getItem(STORAGE_KEY)
    if (stored && (stored === "en" || stored === "ar") && stored !== language) {
      setLanguageState(stored)
    }
  }, [])

  useEffect(() => {
    if (typeof window === "undefined") {
      return
    }
    document.documentElement.lang = language
    document.documentElement.dir = getDirection(language)
    window.localStorage.setItem(STORAGE_KEY, language)
  }, [language])

  const translate = useCallback(
    (template: string, replacements?: Record<string, string | number>) => {
      const dictionary = dictionaries[language]
      const resolved = dictionary?.[template] ?? template
      return applyReplacements(resolved, replacements)
    },
    [language],
  )

  const value = useMemo<LanguageContextValue>(
    () => ({
      language,
      setLanguage: (next) => setLanguageState(next),
      toggleLanguage: () => setLanguageState((prev) => (prev === "ar" ? "en" : "ar")),
      translate,
    }),
    [language, translate],
  )

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>
}

export function useLanguage() {
  const context = useContext(LanguageContext)
  if (!context) {
    throw new Error("useLanguage must be used within LanguageProvider")
  }
  return context
}
