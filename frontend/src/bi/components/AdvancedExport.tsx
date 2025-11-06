"use client";

import React, { useCallback, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Download, FileSpreadsheet, FileText, Table } from "lucide-react";

export type AdvancedExportColumn = {
  key: string;
  label: string;
  labelAr?: string;
  formatter?: (value: unknown, row: Record<string, unknown>) => string;
};

export type AdvancedExportConfig = {
  fileName?: string;
  reportTitle?: string;
  reportTitleAr?: string;
  columns: AdvancedExportColumn[];
  rows: Record<string, unknown>[];
  disabled?: boolean;
};

const escapeCsvValue = (value: unknown): string => {
  if (value === null || value === undefined) return "";
  const text = String(value);
  if (text.includes('"') || text.includes(",") || text.includes("\n")) {
    return `"${text.replace(/"/g, '""')}"`;
  }
  return text;
};

const generateCSV = (
  columns: AdvancedExportColumn[],
  rows: Record<string, unknown>[]
): string => {
  const header = columns.map((column) => {
    const bilingual =
      column.labelAr && column.labelAr !== column.label
        ? `${column.label} / ${column.labelAr}`
        : column.label;
    return escapeCsvValue(bilingual);
  });

  const lines = rows.map((row) =>
    columns
      .map((column) => {
        const cell = column.formatter
          ? column.formatter(row[column.key], row)
          : row[column.key];
        return escapeCsvValue(cell);
      })
      .join(",")
  );

  return [header.join(","), ...lines].join("\r\n");
};

const generateHTML = (
  title: string,
  columns: AdvancedExportColumn[],
  rows: Record<string, unknown>[]
): string => {
  const headerRow = columns
    .map(
      (col) =>
        `<th style="border: 1px solid #ddd; padding: 8px; background-color: #f2f2f2; text-align: right;">${col.labelAr || col.label}</th>`
    )
    .join("");

  const dataRows = rows
    .map(
      (row) =>
        `<tr>${columns
          .map((col) => {
            const cell = col.formatter
              ? col.formatter(row[col.key], row)
              : row[col.key];
            return `<td style="border: 1px solid #ddd; padding: 8px; text-align: right;">${cell || "—"}</td>`;
          })
          .join("")}</tr>`
    )
    .join("");

  return `
<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${title}</title>
  <style>
    body {
      font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
      margin: 20px;
      direction: rtl;
    }
    h1 {
      color: #333;
      border-bottom: 3px solid #4CAF50;
      padding-bottom: 10px;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      margin-top: 20px;
    }
    @media print {
      @page { size: A4 landscape; margin: 1cm; }
      body { margin: 0; }
    }
  </style>
</head>
<body>
  <h1>${title}</h1>
  <p style="color: #666;">تم إنشاؤه في: ${new Date().toLocaleDateString("ar-SA", {
    year: "numeric",
    month: "long",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  })}</p>
  <p style="color: #666;">عدد السجلات: ${rows.length.toLocaleString("ar-SA")}</p>
  <table>
    <thead>
      <tr>${headerRow}</tr>
    </thead>
    <tbody>
      ${dataRows}
    </tbody>
  </table>
</body>
</html>`;
};

export const AdvancedExport: React.FC<AdvancedExportConfig> = ({
  fileName = "mind-q-report",
  reportTitle = "Mind-Q Report",
  reportTitleAr = "تقرير Mind-Q",
  columns,
  rows,
  disabled,
}) => {
  const [isExporting, setIsExporting] = useState(false);

  const downloadFile = useCallback((content: string | Blob, filename: string, type: string) => {
    const blob = typeof content === "string" ? new Blob(["\ufeff" + content], { type }) : content;
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
    URL.revokeObjectURL(url);
  }, []);

  const exportCSV = useCallback(() => {
    if (!rows?.length || !columns?.length) return;
    const csvContent = generateCSV(columns, rows);
    downloadFile(csvContent, `${fileName}.csv`, "text/csv;charset=utf-8;");
  }, [columns, rows, fileName, downloadFile]);

  const exportExcel = useCallback(() => {
    if (!rows?.length || !columns?.length) return;
    
    // Excel XML format (SpreadsheetML) with RTL support
    const header = columns.map(col => col.labelAr || col.label).join("</Cell><Cell><Data ss:Type=\"String\">");
    const dataRows = rows.map(row => {
      const cells = columns.map(col => {
        const cell = col.formatter ? col.formatter(row[col.key], row) : row[col.key];
        const value = String(cell || "");
        const type = typeof cell === "number" ? "Number" : "String";
        return value;
      }).join("</Data></Cell><Cell><Data ss:Type=\"String\">");
      return `<Row><Cell><Data ss:Type=\"String\">${cells}</Data></Cell></Row>`;
    }).join("");

    const excelContent = `<?xml version="1.0"?>
<?mso-application progid="Excel.Sheet"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:o="urn:schemas-microsoft-com:office:office"
 xmlns:x="urn:schemas-microsoft-com:office:excel"
 xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:html="http://www.w3.org/TR/REC-html40">
 <DocumentProperties xmlns="urn:schemas-microsoft-com:office:office">
  <Title>${reportTitleAr}</Title>
  <Author>Mind-Q V4.1</Author>
  <Created>${new Date().toISOString()}</Created>
 </DocumentProperties>
 <Styles>
  <Style ss:ID="Header">
   <Font ss:Bold="1"/>
   <Interior ss:Color="#CCCCCC" ss:Pattern="Solid"/>
  </Style>
 </Styles>
 <Worksheet ss:Name="${reportTitleAr.substring(0, 30)}" ss:RightToLeft="1">
  <Table>
   <Row ss:StyleID="Header">
    <Cell><Data ss:Type="String">${header}</Data></Cell>
   </Row>
   ${dataRows}
  </Table>
 </Worksheet>
</Workbook>`;

    downloadFile(excelContent, `${fileName}.xls`, "application/vnd.ms-excel;charset=utf-8;");
  }, [columns, rows, fileName, reportTitleAr, downloadFile]);

  const exportPDF = useCallback(() => {
    if (!rows?.length || !columns?.length) return;
    
    setIsExporting(true);
    
    // Generate HTML and open print dialog (browser will handle PDF)
    const htmlContent = generateHTML(reportTitleAr, columns, rows);
    const printWindow = window.open("", "_blank");
    
    if (printWindow) {
      printWindow.document.write(htmlContent);
      printWindow.document.close();
      
      // Wait for content to load, then print
      printWindow.onload = () => {
        setTimeout(() => {
          printWindow.print();
          setIsExporting(false);
        }, 250);
      };
    } else {
      setIsExporting(false);
      alert("تعذر فتح نافذة الطباعة. تأكد من السماح بالنوافذ المنبثقة.");
    }
  }, [columns, rows, reportTitleAr]);

  const exportHTML = useCallback(() => {
    if (!rows?.length || !columns?.length) return;
    const htmlContent = generateHTML(reportTitleAr, columns, rows);
    downloadFile(htmlContent, `${fileName}.html`, "text/html;charset=utf-8;");
  }, [columns, rows, fileName, reportTitleAr, downloadFile]);

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          className="flex items-center gap-2"
          disabled={disabled || !rows?.length || isExporting}
        >
          <Download className="h-4 w-4" />
          <span>تصدير</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-48">
        <DropdownMenuLabel>اختر نوع التصدير</DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={exportCSV} className="cursor-pointer">
          <Table className="ml-2 h-4 w-4" />
          <span>CSV (Excel)</span>
        </DropdownMenuItem>
        <DropdownMenuItem onClick={exportExcel} className="cursor-pointer">
          <FileSpreadsheet className="ml-2 h-4 w-4" />
          <span>Excel (XLS)</span>
        </DropdownMenuItem>
        <DropdownMenuItem onClick={exportPDF} className="cursor-pointer">
          <FileText className="ml-2 h-4 w-4" />
          <span>PDF (طباعة)</span>
        </DropdownMenuItem>
        <DropdownMenuItem onClick={exportHTML} className="cursor-pointer">
          <FileText className="ml-2 h-4 w-4" />
          <span>HTML</span>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
};
