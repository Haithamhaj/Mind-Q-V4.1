# Mind-Q V4.1 Pipeline Flow Map
## خريطة تدفق البيانات الشاملة

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Phase 01: Ingestion & SLA                        │
│  📥 Input: CSV/Parquet + SLA Docs (PDF/Excel/DOCX)                 │
│  📤 Output: raw.parquet + sla_manifest.json                        │
│  🎯 Purpose: تجميع البيانات من مصادر متعددة + استخراج SLA terms   │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│                    Phase 02: Quality Gates                          │
│  📥 Input: raw.parquet                                              │
│  📤 Output: quality_report.json + issues_catalog.json              │
│  🎯 Purpose: فحص جودة البيانات + كشف المشاكل البنيوية              │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│                    Phase 03: Schema & Terminology                   │
│  📥 Input: raw.parquet                                              │
│  📤 Output: schema_v1.json + terminology.json (LLM)                │
│  🎯 Purpose: توثيق المخطط + مصطلحات ثنائية اللغة (عربي/إنجليزي)   │
└─────────────────────────────────────────────────────────────────────┘
                    ↓                      ↓
      ┌─────────────────────┐    ┌──────────────────────────┐
      │   Phase 03.5:       │    │   Phase 04: Profiling    │
      │   TextOps (Async)   │    │                          │
      │  🔄 Runs in         │    │  📊 Statistical          │
      │     background       │    │     profiles             │
      └─────────────────────┘    └──────────────────────────┘
                    ↓                      ↓
┌─────────────────────────────────────────────────────────────────────┐
│                    Phase 05: Missing Data Strategy                  │
│  📥 Input: raw.parquet + quality reports                           │
│  📤 Output: clean_imputed.parquet (59 cols + 39 indicators)        │
│  🎯 Purpose: معالجة البيانات المفقودة + hybrid imputation          │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│              Phase 06: Standardize + Feature Engineering            │
│  📥 Input: clean_imputed.parquet (59 cols)                         │
│  📤 Output: clean.parquet (99 cols)                                │
│           = 59 original (renamed) + 40 engineered features         │
│  🎯 Purpose:                                                        │
│     1. توحيد الأسماء (SENDER NAME → sender_name)                   │
│     2. Feature Engineering (lead_time, entity_id, KPIs)            │
│     3. Type casting + PII masking                                   │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│            Phase 07: Readiness + Diagnostics + KNIME                │
│  📥 Input: features.parquet from Phase 06                          │
│  📤 Output:                                                         │
│     • 07: diagnostics.json + network.json                          │
│     • 07.5: feature_report.json/pdf                                │
│     • 07.6: LLM summary (bilingual narratives)                     │
│     • 07.7: business_correlation network                           │
│     • 07-KNIME: KNIME-compatible profiles (CRITICAL!)              │
│  🎯 Purpose:                                                        │
│     - تقييم جاهزية البيانات للنمذجة                                │
│     - كشف leakage + correlation networks                           │
│     - KNIME workflow integration (50K rows processing)             │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│                    Phase 08: Operational Insights                   │
│  📥 Input: features + correlations + TextOps (phase 03.5)          │
│  📤 Output: insights_report.json + cards.json + narratives.json    │
│  🎯 Purpose:                                                        │
│     - توليد رؤى تشغيلية (anomaly detection, trends)               │
│     - ECharts dashboards + diagnostic cards                        │
│     - KPI candidates + correlation explanations (LLM)              │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│              Phase 09: Business Validation + Decisions              │
│  📥 Input: clean.parquet (Phase 06) + insights_report.json         │
│  📤 Output:                                                         │
│     • bi_feed.parquet (~129 cols: 99 data + 30 KPIs)              │
│     • row_decisions.parquet (approve/flag/reject logic)            │
│     • benchmarks.parquet                                            │
│     • sla_summary.json (SLA validation vs targets)                 │
│  🎯 Purpose:                                                        │
│     - التحقق من SLA terms (PASS/WARN/STOP)                         │
│     - حساب KPIs التشغيلية (sla_pct, rto_pct, lead_time)          │
│     - تطبيق business rules + what-if scenarios                     │
│     - إنشاء bi_feed (المصدر الرئيسي لـ BI)                        │
└─────────────────────────────────────────────────────────────────────┘
                    ↓                      ↓
      ┌─────────────────────┐    ┌──────────────────────────┐
      │   Phase 09.5:       │    │                          │
      │   Causal Inference  │    │                          │
      │   (Optional)        │    │                          │
      │  📊 DoWhy + CausalML│    │                          │
      └─────────────────────┘    └──────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│          Phase 10: BI Delivery + Semantic Layer + AI Assistant      │
│  📥 Input: bi_feed.parquet + row_decisions + benchmarks            │
│  📤 Output:                                                         │
│     📊 BI Layer:                                                    │
│        • marts/*.parquet (fact_business, fact_decisions)           │
│        • datasets/orders.parquet (for detailed queries)            │
│     🧠 Semantic Layer:                                              │
│        • semantic/metrics.yaml (KPI definitions + SQL)             │
│        • semantic/dimensions.json (auto-detected dimensions)       │
│     🤖 AI Assistant:                                                │
│        • assistant/prompts.json (system prompts)                   │
│        • SLA chatbot context (JSONL)                               │
│  🎯 Purpose:                                                        │
│     - بناء BI marts للتحليلات المتقدمة                             │
│     - Auto-detect dimensions (categorical, temporal)               │
│     - Define metrics dynamically (total_orders, cod_rate, etc)     │
│     - Prepare AI context for chatbot                                │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│                    FRONTEND BI EXPERIENCE                           │
│  🎨 Components:                                                     │
│     1. Story BI Page (interactive dashboards)                      │
│     2. Layer1 Assistant (filter + metric selection)                │
│     3. Layer2 Assistant (deep analysis + recommendations)          │
│     4. SLA Chatbot (explain SLA terms + validation results)        │
│     5. ECharts visualizations (line, bar, pie, heatmap)            │
│  🤖 AI Capabilities:                                                │
│     - Natural language queries → SQL + Chart                       │
│     - Explain data patterns + anomalies                            │
│     - Give recommendations based on insights                        │
│     - Multilingual (Arabic/English)                                │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🔗 الترابط الحرج بين المراحل

### 1️⃣ **Phase 05 → Phase 06 (Feature Engineering)**
```
Phase 05 (59 clean columns)
    ↓ Feature Engineering + Standardization
Phase 06 (99 columns)
    = 59 renamed/standardized + 40 engineered
```
**لماذا مهمة؟**
- تضيف KPIs مثل `lead_time_hours`, `lead_time_p50`, `lead_time_p90`
- توحّد أسماء الأعمدة (SENDER NAME → sender_name)
- Type casting آمن للتواريخ والأرقام

### 2️⃣ **Phase 06 → Phase 07-KNIME (CRITICAL!)**
```
Phase 06 features.parquet
    ↓ KNIME Workflow
Phase 07-KNIME outputs
    ↓ Advanced analytics (50K rows, no sampling)
```
**لماذا KNIME حرجة؟**
- معالجة متقدمة للبيانات (50,000 صف كاملة)
- Correlation networks دقيقة
- Feature selection علمية
- Quality reports تفصيلية

### 3️⃣ **Phase 08 → Phase 09 (Insights → Validation)**
```
Phase 08 insights_report.json
    ↓ Business rules + SLA validation
Phase 09 bi_feed.parquet
    = Data + KPIs + Decisions
```
**لماذا مهمة؟**
- Phase 08 تكتشف الأنماط (trends, anomalies)
- Phase 09 تتحقق من SLA + تطبق business rules
- النتيجة: `bi_feed` جاهز للـ BI

### 4️⃣ **Phase 09 → Phase 10 (BI Delivery)**
```
Phase 09 bi_feed.parquet (129 columns)
    ↓ Semantic layer + Marts
Phase 10 BI Experience
    = Dashboards + AI Assistant
```
**لماذا مهمة؟**
- Phase 10 تبني semantic layer ديناميكي
- Auto-detect dimensions (ORIGIN, DESTINATION, STATUS)
- Define metrics (total_orders, cod_rate, sla_pct)
- Prepare AI chatbot context

---

## 🤖 نظام AI Assistant الحالي

### المكونات الموجودة:

#### 1. **SLA Chatbot** (`src/app/services/sla_chat/app.py`)
```python
Purpose: شرح SLA terms + validation results
Input: SLA context (JSONL) from Phase 09
Output: Answers with references [run123:sla:001]
Model: GPT-4o-mini (configurable)
```

#### 2. **Layer1 Assistant** (Frontend - `StoryBIPage.tsx`)
```typescript
Purpose: مساعدة المستخدم في اختيار الفلاتر والمقاييس
Input: User question + available metrics/dimensions
Output: Filter recommendations + chart selection
Logic: Deterministic keyword matching
```

#### 3. **Layer2 Assistant** (Frontend)
```typescript
Purpose: تحليل عميق + توصيات
Input: User question + chat history + filters
Output: Deep insights + recommendations
Fallback: Keyword-based if LLM fails
```

#### 4. **LLM Router** (`bi10/app/llm_router.py`)
```python
Purpose: تحويل سؤال المستخدم → SQL + Chart
Input: Natural language question + semantic catalog
Output: SQL query + chart type + ECharts config
Model: GPT-4o-mini
Fallback: Deterministic plan
```

---

## 🎯 ما المطلوب للوصول إلى BI ديناميكي تفاعلي كامل؟

### الأهداف:
1. ✅ **BI تفصيلي** - عرض كل التفاصيل من البيانات
2. ✅ **AI chatbot ذكي** - يشرح البيانات ويعطي توصيات
3. ✅ **ديناميكي 100%** - يعمل مع أي dataset

### الحالة الحالية:
| المكون | الحالة | الملاحظات |
|--------|--------|-----------|
| Phase 01-09 Pipeline | ✅ يعمل | بيانات تصل إلى bi_feed بنجاح |
| Phase 10 BI Delivery | ✅ يعمل | Semantic layer + marts جاهزة |
| SLA Chatbot | ✅ يعمل | يشرح SLA terms |
| Layer1/2 Assistants | ⚠️ محدود | Keyword-based, يحتاج تحسين |
| LLM Router | ✅ يعمل | يحوّل أسئلة → SQL |
| Dynamic Dimensions | ✅ يعمل | Auto-detect من bi_feed |

---

## 💡 التوصيات للتطوير:

### المرحلة الحالية (قصيرة المدى):
1. **التأكد من تدفق البيانات الكامل:**
   - ✅ Phase 06 → Phase 09: 99 عمود يصلون كاملين
   - ✅ Phase 09 → Phase 10: bi_feed ديناميكي
   - 🔄 اختبار على dataset حقيقي

2. **تحسين AI Assistant:**
   - دمج SLA chatbot + Layer2 assistant
   - إضافة context من insights_report.json
   - تحسين prompts (Arabic/English)

3. **Recommendations Engine:**
   - استخدام insights من Phase 08
   - استخدام correlation network من Phase 07.7
   - استخدام causal inference من Phase 09.5

### المرحلة القادمة (متوسطة المدى):
4. **Machine Learning Integration:**
   - استخدام features من Phase 06
   - بناء نماذج تنبؤية (demand forecasting)
   - Route optimization (Phase 12)

5. **Advanced Analytics:**
   - Anomaly detection أذكى
   - Trend forecasting
   - What-if scenario analysis

---

هل تريد أن:
1. **نختبر تدفق البيانات الكامل** على real-data-test؟
2. **نحسّن AI Assistant** ليعطي توصيات أفضل؟
3. **نضيف ميزات جديدة** للـ chatbot؟
