"use client"

import { Sidebar } from "@/components/sidebar"
import { Header } from "@/components/header"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Database, FileText, LinkIcon, CheckCircle2, AlertCircle } from "lucide-react"

const dataSources = [
  {
    name: "Primary Logistics Database",
    type: "PostgreSQL",
    status: "connected",
    lastSync: "2 minutes ago",
    records: "2.4M",
  },
  {
    name: "SLA Document Repository",
    type: "File System",
    status: "connected",
    lastSync: "1 hour ago",
    records: "156 files",
  },
  {
    name: "External API - Shipping Provider",
    type: "REST API",
    status: "connected",
    lastSync: "5 minutes ago",
    records: "Real-time",
  },
  {
    name: "Historical Data Archive",
    type: "Parquet Files",
    status: "connected",
    lastSync: "1 day ago",
    records: "8.7M",
  },
]

export default function SourcesPage() {
  return (
    <div className="flex h-screen">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <Header />
        <main className="flex-1 overflow-y-auto bg-background p-6">
          <div className="mx-auto max-w-5xl space-y-6">
            <div>
              <h1 className="text-3xl font-bold text-foreground">Data Sources</h1>
              <p className="text-muted-foreground">Manage and monitor connected data sources</p>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              {dataSources.map((source, index) => (
                <Card key={index}>
                  <CardHeader>
                    <div className="flex items-start justify-between">
                      <div className="flex items-center gap-3">
                        {source.type.includes("Database") || source.type.includes("PostgreSQL") ? (
                          <Database className="h-5 w-5 text-primary" />
                        ) : source.type.includes("File") || source.type.includes("Parquet") ? (
                          <FileText className="h-5 w-5 text-secondary" />
                        ) : (
                          <LinkIcon className="h-5 w-5 text-primary" />
                        )}
                        <div>
                          <CardTitle className="text-base">{source.name}</CardTitle>
                          <CardDescription>{source.type}</CardDescription>
                        </div>
                      </div>
                      {source.status === "connected" ? (
                        <CheckCircle2 className="h-5 w-5 text-secondary" />
                      ) : (
                        <AlertCircle className="h-5 w-5 text-destructive" />
                      )}
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-3">
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-muted-foreground">Status</span>
                        <Badge
                          variant="outline"
                          className={
                            source.status === "connected"
                              ? "bg-secondary/20 text-secondary"
                              : "bg-destructive/20 text-destructive"
                          }
                        >
                          {source.status}
                        </Badge>
                      </div>
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-muted-foreground">Last Sync</span>
                        <span className="font-medium text-foreground">{source.lastSync}</span>
                      </div>
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-muted-foreground">Records</span>
                        <span className="font-medium text-foreground">{source.records}</span>
                      </div>
                      <Button variant="outline" className="w-full bg-transparent" size="sm">
                        Configure
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        </main>
      </div>
    </div>
  )
}
