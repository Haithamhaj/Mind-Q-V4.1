"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { CheckCircle2, XCircle, Clock, AlertTriangle } from "lucide-react"

interface PhaseStatus {
  phase: string
  name: string
  status: "pass" | "warn" | "stop" | "running" | "pending"
  duration?: string
  message?: string
}

interface PipelineStatusProps {
  runId: string
  phases: PhaseStatus[]
}

export function PipelineStatus({ runId, phases }: PipelineStatusProps) {
  const getStatusIcon = (status: PhaseStatus["status"]) => {
    switch (status) {
      case "pass":
        return <CheckCircle2 className="h-5 w-5 text-secondary" />
      case "warn":
        return <AlertTriangle className="h-5 w-5 text-yellow-500" />
      case "stop":
        return <XCircle className="h-5 w-5 text-destructive" />
      case "running":
        return <Clock className="h-5 w-5 animate-spin text-primary" />
      default:
        return <Clock className="h-5 w-5 text-muted-foreground" />
    }
  }

  const getStatusBadge = (status: PhaseStatus["status"]) => {
    const variants: Record<PhaseStatus["status"], string> = {
      pass: "bg-secondary/20 text-secondary border-secondary/30",
      warn: "bg-yellow-500/20 text-yellow-500 border-yellow-500/30",
      stop: "bg-destructive/20 text-destructive border-destructive/30",
      running: "bg-primary/20 text-primary border-primary/30",
      pending: "bg-muted/20 text-muted-foreground border-muted/30",
    }

    return (
      <Badge variant="outline" className={variants[status]}>
        {status.toUpperCase()}
      </Badge>
    )
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Pipeline Status: {runId}</CardTitle>
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {phases.map((phase) => (
            <div
              key={phase.phase}
              className="flex items-center justify-between rounded-lg border border-border bg-card/50 p-4"
            >
              <div className="flex items-center gap-4">
                {getStatusIcon(phase.status)}
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-sm font-semibold text-foreground">Phase {phase.phase}</span>
                    <span className="text-sm text-muted-foreground">-</span>
                    <span className="text-sm font-medium text-foreground">{phase.name}</span>
                  </div>
                  {phase.message && <p className="text-xs text-muted-foreground">{phase.message}</p>}
                </div>
              </div>
              <div className="flex items-center gap-3">
                {phase.duration && <span className="text-xs text-muted-foreground">{phase.duration}</span>}
                {getStatusBadge(phase.status)}
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
