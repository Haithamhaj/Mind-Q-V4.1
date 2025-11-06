"use client"

import { Bell, User } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { useLanguage } from "@/context/language-context"
import { LanguageToggle } from "@/components/language-toggle"

export function Header() {
  const { translate } = useLanguage()

  return (
    <header className="flex h-16 items-center justify-between border-b border-border bg-card px-6">
      <div className="flex items-center gap-4">
        <h2 className="text-lg font-semibold text-foreground">{translate("Pipeline Dashboard")}</h2>
      </div>

      <div className="flex items-center gap-4">
        <LanguageToggle />
        {/* Notifications */}
        <Button variant="ghost" size="icon" className="relative" aria-label={translate("Notifications")}>
          <Bell className="h-5 w-5" />
          <span className="absolute right-1 top-1 h-2 w-2 rounded-full bg-secondary" />
        </Button>

        {/* User Menu */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon">
              <User className="h-5 w-5" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuLabel>{translate("My Account")}</DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem>{translate("Profile")}</DropdownMenuItem>
            <DropdownMenuItem>{translate("Settings")}</DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem>{translate("Sign out")}</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  )
}
