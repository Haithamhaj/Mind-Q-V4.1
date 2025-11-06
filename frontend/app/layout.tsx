import type React from "react"
import type { Metadata } from "next"
import { GeistSans } from "geist/font/sans"
import { GeistMono } from "geist/font/mono"
import { Analytics } from "@vercel/analytics/next"
import { Suspense } from "react"
import "./globals.css"
import { LanguageProvider } from "@/context/language-context"
import { HelpProvider } from "@/components/help/help-context"
import { HelpPanel } from "@/components/help/help-panel"

export const metadata: Metadata = {
  title: "Mind-Q V4 | Logistics Intelligence Platform",
  description:
    "End-to-end logistics data platform covering ingestion, data quality, business validation, SLA tracking, and BI delivery",
  generator: "v0.app",
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="ar" dir="rtl" className="dark" suppressHydrationWarning>
      <body suppressHydrationWarning className={`font-sans ${GeistSans.variable} ${GeistMono.variable} antialiased`}>
        <LanguageProvider>
          <HelpProvider>
            <Suspense fallback={null}>{children}</Suspense>
            <Analytics />
            <HelpPanel />
          </HelpProvider>
        </LanguageProvider>
      </body>
    </html>
  )
}
