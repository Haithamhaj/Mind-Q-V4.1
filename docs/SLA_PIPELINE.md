# SLA Ingestion and Validation Workflow

This document explains how Service Level Agreement (SLA) artefacts flow through Mind‑Q from ingestion to business validation. The goal is to keep a verifiable trail between the documents uploaded by users and the SLA gates enforced in Phase 09.

## Phase 01 – Upload and Normalisation
- The ingestion stage now accepts two inputs:
  - `data_files` (or the legacy `files`) – operational datasets (CSV/Parquet) required for the pipeline.
  - `sla_files` – one or more SLA documents (PDF, DOCX, HTML, TXT/Markdown, CSV, TSV, Excel with multiple sheets).
- Every SLA file is:
  1. Copied to `artifacts/<run_id>/stage_01_ingestion/sla_raw/` with a stable hash-based name.
  2. Normalised through `shared.sla.process_sla_file`, producing a JSON snapshot under `contracts/sla_processed/<run_id>/`.
     - Tabular formats extract all sheets and sample rows.
     - Unstructured files capture a text summary when possible.
     - Tabular data is scanned for KPI rows and associated thresholds (target/warn/stop), direction (`gte`/`lte`), window sizes and units.
     - Any parsing issues are logged as notes rather than hard failures.
- A manifest is written to `artifacts/<run_id>/stage_01_ingestion/sla_manifest.json` with:
  - File metadata (size, hash, storage path).
  - Pointers to the normalised JSON artefacts.
  - All detected SLA terms.
  - Processing notes (e.g., missing parser dependencies).
- The manifest path and the bundled copy (`contracts/sla_processed/<run_id>/contracts.json`) are surfaced in the Stage 01 outputs so downstream phases can locate the material without re-scanning storage.

## Phase 09 – SLA Enforcement
- Phase 09 loads the manifest via `shared.sla.load_bundle`. If the manifest is missing entirely, a warning `sla_manifest_missing` is emitted for auditors.
- KPI and effect metrics computed during the phase are fed into `shared.sla.evaluate_terms`. Each SLA term is evaluated with direction-aware thresholds:
  - For `gte` terms, values below the warn/stop thresholds raise WARN/STOP conditions.
  - For `lte` terms, values above the thresholds raise WARN/STOP conditions.
  - Percentage thresholds automatically align with KPI scales (e.g., 95% vs 0.95).
- Results are written to `artifacts/<run_id>/stage_09_business_validation/sla_summary.json`, containing:
  - The original manifest entries (for traceability).
  - A per-term evaluation record (`PASS`/`WARN`/`STOP`, actual value, thresholds, source sheet/row).
  - Any manifest-level notes.
- SLA outcomes feed the phase gate:
  - Any STOP term forces the overall gate to STOP with reason `sla::<kpi_name>`.
  - WARN terms add gate warnings with the same prefix.
  - Missing manifests or parser notes are appended to the warning list for transparency.
- The validation report (`validation_report.json`) now includes an `sla` section mirroring the summary payload so BI consumers and auditors can review the evaluated terms without opening the raw file.

## Multi-sheet Excel Support
- Excel workbooks are read with `pandas.read_excel(sheet_name=None)`. Each sheet generates a dedicated table entry with up to 200 sample rows.
- Term extraction occurs per sheet, retaining the originating sheet name (`file.xlsx::Sheet1`) in the `source` block of every term.
- When a workbook does not contain machine-readable thresholds, the system records the document but raises a WARN (`sla::no_terms_detected`) so teams can supplement the template or provide additional context.

## Operational Notes
- Optional libraries (`pypdf`, `pandas`, Excel engines) are used when available. If a dependency is missing, the pipeline continues but documents the gap in the manifest and summary.
- All timestamps, hashes and storage locations are deterministic, allowing SLA artefacts to be reconciled during audits.
- To override storage locations, pass `sla_processed_root` in the Stage 01 config; Phase 09 will automatically pick up the same manifest via the artefact tree.

## سياق RAG للـ LLM
- سكربت `scripts/build_sla_context.py` يجمع نتائج المرحلة 09 (`sla_summary.json`, `validation_report.json`, `story_ops.json`, `segment_insights.parquet`) ويحفظ سياقاً جاهزاً للاسترجاع تحت `artifacts/context/<run_id>/<run_id>_sla.jsonl`.
- يتم توليد سجل manifest لكل تشغيل يعرض المصادر وعدد الإدخالات الُمهيكلة، ما يسهل تتبع التعديلات وإعادة البناء.
- لكل بند SLA تُكتب فقرة تحتوي على الحالة، القيم الفعلية، حدود التحذير/الإيقاف والأسباب، لضمان أن الـ LLM يستند إلى أرقام قابلة للتدقيق.
- التحديثات تشتغل عند كل تشغيل جديد للسكربت؛ التخزين مؤشّر بالزمن (`mtime`) ليضمن تحميل نسخة حديثة عند الطلب.

## بوابة LLM للتفاعل مع SLA
- خدمة `src/app/services/sla_chat/app.py` توفر API مبنية على FastAPI بعنوان `/v1/sla/chat`، وتسترجع أهم المقاطع من السياق عبر خوارزمية تطابق بسيطة قبل تمريرها إلى نموذج OpenAI (الإعداد الافتراضي `gpt-4o-mini`).
- يمكن تهيئة الخدمة عبر متغيرات البيئة:
  - `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_BASE_URL`, `OPENAI_TEMPERATURE`
  - `SLA_CONTEXT_ROOT` لتغيير مسار السياق.
- في حال تعذر الاتصال بالـ LLM، ترجع الخدمة إجابة احتياطية قائمة على المقاطع المسترجعة، مع الإشارة إلى ضرورة تفعيل المفتاح أو إعادة بناء السياق.
- كل جلسة محادثة تُسجَّل في `artifacts/context/<run_id>/logs/chat_sessions.jsonl` مع التوقيت، السؤال، والمعرّفات المرجعية المستخدمة، ما يسهّل التدقيق وتتبّع استخدام النموذج.
## لوحة القيادة المحدثة
- يوفر المسار /api/bi/sla الآن حمولة منسقة جاهزة للواجهة الأمامية. البنية الأساسية كالآتي:

`
{
  "summary": {
    "compliance_pct": 94.2,
    "status": "warn",
    "documents_total": 5,
    "terms_total": 62,
    "warn_terms": 4,
    "stop_terms": 1,
    "last_execution": "2025-10-25T03:41:02.114Z",
    "narrative": "تمت مراجعة...",
    "recommendations": ["راجع عقد المورد A...", "..."]
  },
  "documents": [
    {
      "display_name": "Supplier SLA October",
      "status": "warn",
      "compliance_pct": 87.5,
      "term_counts": { "evaluated": 8, "passed": 7, "warn": 1, "stop": 0 },
      "kpi_refs": [{ "kpi_id": "sla_pct", "value_pct": 94.0 }]
    }
  ],
  "kpis": [
    {
      "id": "sla_pct",
      "label": "On-Time Delivery Rate",
      "value_pct": 94.0,
      "warn_threshold_pct": 95.0,
      "stop_threshold_pct": 90.0,
      "status": "warn"
    }
  ],
  "alerts": [
    {
      "id": "kpi::sla_pct::warn",
      "category": "contract",
      "severity": "warning",
      "message": "...",
      "recommendation": "..."
    }
  ],
  "attachments": [
    {
      "name": "Supplier_SLA.pdf",
      "media_type": "application/pdf",
      "stored_path": "artifacts/run-20251015/.../file.pdf"
    }
  ],
  "metadata": {
    "generated_at": "2025-10-25T03:41:02.114Z",
    "sources": { "validation_report": "...", "sla_summary": "..." },
    "next_actions": [{ "message": "تواصل مع فريق العمليات...", "category": "contract" }]
  }
}
`

- تبقى الحقول السابقة (metrics, overall, gate, performance) متوافقة لأغراض التتبع وواجهات LLM، لكن الواجهة الأمامية الجديدة تعتمد على المفاتيح عالية المستوى (summary, documents, kpis, lerts, ttachments, metadata).
