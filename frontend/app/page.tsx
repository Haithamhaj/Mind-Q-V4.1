"use client"

import Link from "next/link"
import { Activity, Brain, CheckCircle2, Database, LayoutDashboard, Play, Settings, Workflow } from "lucide-react"

import { Sidebar } from "@/components/sidebar"
import { Header } from "@/components/header"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { HelpTrigger } from "@/components/help/help-trigger"
import { useLanguage } from "@/context/language-context"

export default function DashboardPage() {
  const { translate } = useLanguage()

  const sections = [
    {
      title: translate("Operational dashboard"),
      description: translate("Track pipeline health and intelligence deliverables in one view."),
      icon: LayoutDashboard,
      cards: [
        {
          title: translate("Pipeline results"),
          href: "/results",
          icon: Workflow,
          description: translate("Review the latest run artifacts, diagnostics, and summaries."),
        },
        {
          title: translate("Business intelligence"),
          href: "/bi",
          icon: Brain,
          description: translate("Launch curated dashboards, metrics, and AI narratives for stakeholders."),
        },
      ],
    },
    {
      title: translate("Execution control"),
      description: translate("Orchestrate new runs, inspect phases, and enforce SLAs."),
      icon: Play,
      cards: [
        {
          title: translate("Run pipeline"),
          href: "/pipeline",
          icon: Play,
          description: translate("Configure datasets, SLA references, and execute the full automation."),
        },
        {
          title: translate("Processing phases"),
          href: "/phases",
          icon: Activity,
          description: translate("Drill into every phase for status, configuration, and BI outputs."),
        },
        {
          title: translate("SLA tracker"),
          href: "/sla",
          icon: CheckCircle2,
          description: translate("Monitor contractual KPIs, breach alerts, and recovery plans."),
        },
      ],
    },
    {
      title: translate("Data governance"),
      description: translate("Manage sources, access, and platform-level preferences."),
      icon: Database,
      cards: [
        {
          title: translate("Source catalog"),
          href: "/sources",
          icon: Database,
          description: translate("Register logistics feeds and align transformations across teams."),
        },
        {
          title: translate("Platform settings"),
          href: "/settings",
          icon: Settings,
          description: translate("Control notifications, credentials, and downstream integrations."),
        },
      ],
    },
  ] as const

  return (
    <div className="flex min-h-screen bg-background">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <Header />
        <main className="flex-1 overflow-y-auto bg-background px-6 py-8">
          <div className="mx-auto flex max-w-6xl flex-col gap-8">
            <header className="space-y-3 text-start">
              <p className="text-sm font-semibold uppercase tracking-wide text-primary">{translate("Mind-Q V4")}</p>
              <div className="flex items-center gap-2">
                <h1 className="text-3xl font-bold text-foreground md:text-4xl">
                  {translate("Logistics intelligence command center")}
                </h1>
                <HelpTrigger
                  topicId="dashboard.overview"
                  aria-label={translate("Explain the platform overview")}
                  buildTopic={() => ({
                    title: translate("Mind-Q V4 platform overview"),
                    summary: translate(
                      "Mind-Q V4 centralises data ingestion, SLA supervision, and BI storytelling in one workspace.",
                    ),
                    detailItems: [
                      translate("Automation phases: ingestion, quality, schema discovery, pipeline orchestration."),
                      translate("Compliance coverage: SLA monitoring, contract evidence, and escalation tracking."),
                      translate("BI outputs: curated dashboards, metrics catalog, and LLM narratives for stakeholders."),
                    ],
                    sources: [
                      {
                        label: translate("Mind-Q SOP handbook"),
                        description: translate("See chapter 1 for platform responsibilities and integrations."),
                      },
                    ],
                    suggestedQuestions: [
                      translate("How do we onboard a new data source?"),
                      translate("What KPIs are tracked in the SLA workspace?"),
                    ],
                  })}
                />
              </div>
              <p className="text-base text-muted-foreground md:text-lg">
                {translate(
                  "Monitor ingestion, quality gates, SLA performance, and BI delivery from a single control room.",
                )}
              </p>
            </header>

            <div className="grid gap-6">
              {sections.map((section) => (
                <section key={section.title} className="space-y-4">
                  <div className="flex items-center gap-3">
                    <section.icon className="h-6 w-6 text-primary" />
                    <div>
                      <h2 className="text-xl font-semibold text-foreground">{section.title}</h2>
                      <p className="text-sm text-muted-foreground">{section.description}</p>
                    </div>
                  </div>

                  <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                    {section.cards.map((card) => (
                      <Card
                        key={card.href}
                        className="group border-border/60 bg-card/80 shadow-sm transition hover:-translate-y-1 hover:border-primary/60 hover:shadow-lg"
                      >
                        <CardHeader className="space-y-2">
                          <div className="flex items-center gap-3">
                            <card.icon className="h-5 w-5 text-primary" />
                            <CardTitle className="text-lg">{card.title}</CardTitle>
                          </div>
                          <CardDescription className="text-sm text-muted-foreground">{card.description}</CardDescription>
                        </CardHeader>
                        <CardContent>
                          <Button asChild variant="secondary" className="w-full justify-start gap-2">
                            <Link href={card.href}>{translate("Open")}</Link>
                          </Button>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                </section>
              ))}
            </div>
          </div>
        </main>
      </div>
    </div>
  )
}
