"use client"

import { Globe } from "lucide-react"

import { useLanguage } from "@/context/language-context"
import { Button } from "@/components/ui/button"

export function LanguageToggle() {
  const { language, toggleLanguage, translate } = useLanguage()

  return (
    <Button
      variant="outline"
      size="sm"
      onClick={toggleLanguage}
      className="flex items-center gap-2 whitespace-nowrap"
    >
      <Globe className="h-4 w-4" />
      <span className="hidden text-xs font-medium sm:inline">{translate("Switch language")}</span>
      <span className="text-xs font-semibold uppercase">{language === "ar" ? "EN" : "AR"}</span>
    </Button>
  )
}
