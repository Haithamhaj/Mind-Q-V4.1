'use client'

import { useEffect, useMemo, useState } from "react"
import { Loader2 } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import type { Language } from "@/context/language-context"
import type { SchemaTerminologyRecord } from "@/lib/api"
import { cn } from "@/lib/utils"

type SchemaGlossaryCardProps = {
  records: SchemaTerminologyRecord[]
  aliasesByColumn?: Record<string, string[]>
  language: Language
  loading?: boolean
  error?: string | null
  resetKey?: string | number
  className?: string
}

const buildSearchIndex = (record: SchemaTerminologyRecord, aliases: string[]): string[] => {
  const values: string[] = []
  if (record.column_id) values.push(record.column_id)
  if (record.original_name) values.push(record.original_name)
  if (record.display_en) values.push(record.display_en)
  if (record.display_ar) values.push(record.display_ar)
  if (record.description_en) values.push(record.description_en)
  if (record.description_ar) values.push(record.description_ar)
  if (Array.isArray(record.synonyms_en)) values.push(...record.synonyms_en)
  if (Array.isArray(record.synonyms_ar)) values.push(...record.synonyms_ar)
  if (Array.isArray(record.tags)) values.push(...record.tags)
  if (Array.isArray(record.kpi_links)) values.push(...record.kpi_links)
  if (aliases.length) values.push(...aliases)
  return values
}

export const SchemaGlossaryCard = ({
  records,
  aliasesByColumn = {},
  language,
  loading = false,
  error = null,
  resetKey,
  className,
}: SchemaGlossaryCardProps) => {
  const [internalQuery, setInternalQuery] = useState("")

  useEffect(() => {
    setInternalQuery("")
  }, [resetKey])

  const placeholder =
    language === "ar" ? "ابحث باسم العمود أو الوصف أو العلامات..." : "Search by column name, description, or tags..."

  const filteredRecords = useMemo(() => {
    if (!records.length) {
      return []
    }
    const trimmed = internalQuery.trim().toLowerCase()
    if (!trimmed) {
      return records
    }
    return records.filter((record) => {
      const aliases = aliasesByColumn[record.column_id ?? ""] ?? []
      return buildSearchIndex(record, aliases).some((value) => value.toLowerCase().includes(trimmed))
    })
  }, [records, internalQuery, aliasesByColumn])

  const totalCount = records.length
  const columnLabel = language === "ar" ? "العمود" : "Column"
  const descriptionLabel = language === "ar" ? "الوصف" : "Description"
  const profileLabel = language === "ar" ? "ملف البيانات" : "Profile"
  const annotationsLabel = language === "ar" ? "السمات" : "Annotations"
  const synonymsLabel = language === "ar" ? "المرادفات" : "Synonyms"
  const aliasesLabel = language === "ar" ? "الأسماء البديلة" : "Aliases"
  const examplesLabel = language === "ar" ? "أمثلة على القيم" : "Value samples"
  const dataTypeLabel = language === "ar" ? "نوع البيانات" : "Data type"
  const nullLabel = language === "ar" ? "نسبة القيم المفقودة" : "Missing ratio"
  const uniqueLabel = language === "ar" ? "عدد القيم الفريدة" : "Unique count"
  const noRecordsLabel = language === "ar" ? "لا توجد مخرجات للمسرد بعد." : "No glossary records have been generated yet."
  const noMatchesLabel =
    language === "ar" ? "لم يتم العثور على أعمدة تطابق البحث." : "No columns match the current search."
  const kpiLabel = language === "ar" ? "مؤشر أداء" : "KPI"
  const kpiLinksLabel = language === "ar" ? "روابط KPI" : "KPI links"
  const missingValueLabel = language === "ar" ? "غير متوفر" : "Not available"

  const renderContent = () => {
    if (loading) {
      return (
        <div className="flex items-center justify-center py-16 text-muted-foreground">
          <Loader2 className="mr-3 h-5 w-5 animate-spin" />
          {language === "ar" ? "جاري تحميل المسرد..." : "Loading glossary..."}
        </div>
      )
    }

    if (error) {
      return (
        <div className="rounded-md border border-destructive/40 bg-destructive/10 p-4 text-destructive">
          <p className="font-semibold">
            {language === "ar" ? "تعذر تحميل مسرد المخطط." : "Failed to load schema glossary."}
          </p>
          <p className="text-sm">{error}</p>
        </div>
      )
    }

    if (!records.length) {
      return (
        <div className="rounded-md border border-border/60 bg-muted/20 p-6 text-sm text-muted-foreground">
          {noRecordsLabel}
        </div>
      )
    }

    if (!filteredRecords.length) {
      return (
        <div className="rounded-md border border-border/60 bg-muted/20 p-6 text-sm text-muted-foreground">
          {noMatchesLabel}
        </div>
      )
    }

    return (
      <div className="overflow-x-auto">
        <table className="w-full table-fixed text-sm">
          <thead>
            <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted-foreground">
              <th className="w-48 px-3 py-2">{columnLabel}</th>
              <th className="w-[38%] px-3 py-2">{descriptionLabel}</th>
              <th className="w-40 px-3 py-2">{profileLabel}</th>
              <th className="px-3 py-2">{annotationsLabel}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {filteredRecords.map((record) => {
              const columnId = record.column_id ?? ""
              const displayName =
                language === "ar"
                  ? record.display_ar ?? record.display_en ?? columnId
                  : record.display_en ?? record.display_ar ?? columnId
              const description =
                language === "ar"
                  ? record.description_ar ?? record.description_en ?? ""
                  : record.description_en ?? record.description_ar ?? ""
              const synonyms =
                language === "ar"
                  ? record.synonyms_ar ?? record.synonyms_en ?? []
                  : record.synonyms_en ?? record.synonyms_ar ?? []
              const aliasList = (aliasesByColumn[columnId] ?? []).slice().sort((a, b) => a.localeCompare(b))
              const examples = (record.value_examples ?? []).slice(0, 5).map((value) => String(value))
              const nullFraction =
                typeof record.null_fraction === "number"
                  ? record.null_fraction > 1
                    ? record.null_fraction
                    : record.null_fraction * 100
                  : null
              const nullFormatted =
                nullFraction === null
                  ? missingValueLabel
                  : `${nullFraction >= 1 ? nullFraction.toFixed(1) : nullFraction.toFixed(2)}%`
              const uniqueFormatted =
                typeof record.unique_count === "number" ? record.unique_count.toLocaleString() : missingValueLabel

              return (
                <tr key={columnId || record.original_name ?? Math.random().toString(36)}>
                  <td className="px-3 py-3 align-top">
                    <p className="font-semibold text-foreground">{displayName}</p>
                    <p className="text-xs text-muted-foreground">
                      {columnId || record.original_name || missingValueLabel}
                    </p>
                    {aliasList.length ? (
                      <p className="mt-1 text-xs text-muted-foreground">
                        <span className="font-medium">{aliasesLabel}:</span> {aliasList.join(", ")}
                      </p>
                    ) : null}
                  </td>
                  <td className="px-3 py-3 align-top">
                    <p className="text-sm text-foreground">{description || missingValueLabel}</p>
                    {synonyms.length ? (
                      <p className="mt-2 text-xs text-muted-foreground">
                        <span className="font-medium">{synonymsLabel}:</span> {synonyms.join(", ")}
                      </p>
                    ) : null}
                    {examples.length ? (
                      <p className="mt-2 text-xs text-muted-foreground">
                        <span className="font-medium">{examplesLabel}:</span> {examples.join(", ")}
                      </p>
                    ) : null}
                  </td>
                  <td className="px-3 py-3 align-top">
                    <div className="space-y-1 text-xs text-muted-foreground">
                      <p>
                        <span className="font-medium text-foreground">{dataTypeLabel}:</span>{" "}
                        {record.dtype ?? missingValueLabel}
                      </p>
                      <p>
                        <span className="font-medium text-foreground">{nullLabel}:</span> {nullFormatted}
                      </p>
                      <p>
                        <span className="font-medium text-foreground">{uniqueLabel}:</span> {uniqueFormatted}
                      </p>
                    </div>
                  </td>
                  <td className="px-3 py-3 align-top">
                    <div className="flex flex-wrap gap-2">
                      {record.is_kpi ? (
                        <Badge variant="outline" className="border-primary/50 text-primary">
                          {kpiLabel}
                        </Badge>
                      ) : null}
                      {(record.tags ?? []).map((tag) => (
                        <Badge key={`${columnId}-tag-${tag}`} variant="secondary" className="bg-muted text-muted-foreground">
                          {tag}
                        </Badge>
                      ))}
                    </div>
                    {record.kpi_links?.length ? (
                      <p className="mt-2 text-xs text-muted-foreground">
                        <span className="font-medium">{kpiLinksLabel}:</span> {record.kpi_links.join(", ")}
                      </p>
                    ) : null}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    )
  }

  return (
    <Card className={cn(className)}>
      <CardHeader>
        <CardTitle>{language === "ar" ? "مسرد المخطط" : "Schema Glossary"}</CardTitle>
        <CardDescription>
          {language === "ar"
            ? "تعرض هذه القائمة الوصف المنهجي لكل عمود كما تم إنشاؤه في المرحلة الثالثة مع أسماء العرض والمرادفات والتصنيفات."
            : "Stage 03 documentation for every column, including display names, descriptions, synonyms, and classifications."}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <Input
            value={internalQuery}
            onChange={(event) => setInternalQuery(event.target.value)}
            placeholder={placeholder}
            className="md:w-80"
          />
          <p className="text-xs text-muted-foreground">
            {language === "ar" ? "عدد الأعمدة الموثقة:" : "Documented columns:"}{" "}
            <span className="font-semibold text-foreground">{totalCount}</span>
          </p>
        </div>
        {renderContent()}
      </CardContent>
    </Card>
  )
}

export default SchemaGlossaryCard
