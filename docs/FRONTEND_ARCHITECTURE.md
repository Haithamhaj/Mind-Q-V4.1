# 🎨 Mind-Q V4.1 - بنية Frontend الشاملة

📅 **آخر تحديث**: نوفمبر 2025  
🎯 **الحالة**: Production-Ready  
🔧 **ينطبق على**: Mind-Q V4.1 Frontend Architecture

---

## 📋 جدول المحتويات

1. [نظرة عامة على البنية](#نظرة-عامة-على-البنية)
2. [التقنيات والمكتبات المستخدمة](#التقنيات-والمكتبات-المستخدمة)
3. [هيكل المشروع](#هيكل-المشروع)
4. [الصفحات الرئيسية](#الصفحات-الرئيسية)
5. [المكونات الأساسية](#المكونات-الأساسية)
6. [إدارة الحالة والسياق](#إدارة-الحالة-والسياق)
7. [الاتصال مع Backend](#الاتصال-مع-backend)
8. [نظام الترجمة](#نظام-الترجمة)
9. [التصورات والرسوم البيانية](#التصورات-والرسوم-البيانية)
10. [نظام المساعدة](#نظام-المساعدة)
11. [Generative AI & LLM Integration](#generative-ai--llm-integration)
12. [الأداء والتحسينات](#الأداء-والتحسينات)

---

## 🏗️ نظرة عامة على البنية

### الفلسفة المعمارية
Mind-Q Frontend هو **تطبيق React/Next.js** حديث يوفر واجهة مستخدم ثنائية اللغة (عربي/إنجليزي) لإدارة وتحليل بيانات اللوجستيات. التطبيق مبني على:

- **Next.js 15.2.4** - App Router للتوجيه وSSR
- **React 19** - مكتبة واجهة المستخدم الأساسية
- **TypeScript** - للكتابة الآمنة (Type Safety)
- **Tailwind CSS 4.1.9** - للتصميم والتنسيق
- **shadcn/ui** - نظام مكونات UI قابل للتخصيص
- **ECharts 5.6.0** - محرك الرسوم البيانية الرئيسي

### المبادئ الأساسية
1. **Component-Driven Development** - كل شيء عبارة عن مكون قابل لإعادة الاستخدام
2. **Type Safety First** - TypeScript في كل مكان
3. **Accessibility** - دعم RTL/LTR، ARIA، وإمكانية الوصول
4. **Performance** - Lazy loading، Code splitting، وOptimization
5. **i18n Native** - دعم متعدد اللغات من البداية

### 🧭 Mind-Q V2 (Clean Slate Protocol)
- **مسارات جديدة معزولة**: كل ما يتعلق بـ V2 يعيش داخل `app/(v2-mindq)/{command-center,data-lab}` مع `layout.tsx` يحقن Global Filter Bar الذي يقرأ/يكتب حالة التطبيق من خلال URL.
- **مكونات Tiered BI**: المكونات التنفيذية والتحليلية موجودة داخل `components/v2-bi/` وتشمل `ActionFeed`, `PerformanceHeatmap`, `AnalystGrid`, و `GenerativeCopilot` مع اعتماد كامل على Shadcn/Tailwind وAG Grid Community.
- **حالة مبنية على URL**: GlobalFilterBar يتحكم في `run_id`, `city`, `carrier`, `date_from`, `date_to`, `kpi`، وكل المكونات تستخدم `useSearchParams` للتزامن الفوري.
- **جسر DuckDB (V2 API)**: تم إضافة `/api/v2/bi_bridge.py` في الـ backend لخدمة JSON ديناميكي من `artifacts/<run_id>/stage_10_bi/marts/fact_business.parquet`، ويشمل:
  - `/api/v2/bi/table` لــ Analyst Grid (AG Grid) مع Pagination/Filtering.
  - `/api/v2/bi/heatmap` يرجع مصفوفة Heatmap لـ Apache ECharts.
  - `/api/v2/ml/insights/feed` يحول `story_ops.json` إلى Action Feed داخل Command Center.
- **BI Copilot**: مكوّن `GenerativeCopilot` يطبّق Orchestrator بأسلوب Vercel AI SDK (generate_chart/deep_link) بدون لمس مصادر البيانات مباشرة، مكتفيًا بالتنقل عبر URL أو تحفيز Smart Chart داخلي.

---

## 🛠️ التقنيات والمكتبات المستخدمة

### Core Framework
```json
{
  "next": "15.2.4",           // Framework رئيسي (App Router)
  "react": "^19",             // مكتبة UI
  "react-dom": "^19",         // React DOM renderer
  "typescript": "^5"          // Language
}
```

### UI Components & Styling
```json
{
  // Radix UI Primitives - مكونات UI أساسية غير منسقة
  "@radix-ui/react-accordion": "1.2.2",
  "@radix-ui/react-alert-dialog": "1.1.4",
  "@radix-ui/react-avatar": "1.1.2",
  "@radix-ui/react-checkbox": "1.1.3",
  "@radix-ui/react-dialog": "1.1.4",
  "@radix-ui/react-dropdown-menu": "2.1.4",
  "@radix-ui/react-popover": "1.1.4",
  "@radix-ui/react-select": "2.1.4",
  "@radix-ui/react-tabs": "latest",
  "@radix-ui/react-toast": "1.2.4",
  "@radix-ui/react-tooltip": "1.1.6",
  // ... والمزيد من مكونات Radix
  
  // Styling
  "tailwindcss": "^4.1.9",              // CSS Framework
  "tailwindcss-animate": "^1.0.7",      // Animation utilities
  "class-variance-authority": "^0.7.1", // CVA للـ variants
  "clsx": "^2.1.1",                     // Class name utility
  "tailwind-merge": "^2.5.5",           // Merge Tailwind classes
  
  // Theming
  "next-themes": "^0.4.6",              // Dark/Light mode
  "geist": "latest"                     // Vercel Geist font
}
```

### Data Visualization
```json
{
  "echarts": "^5.6.0",                  // محرك الرسوم البيانية الرئيسي
  "echarts-for-react": "^3.0.2"        // React wrapper لـ ECharts
}
```

### Form Management
```json
{
  "react-hook-form": "^7.60.0",         // إدارة النماذج
  "@hookform/resolvers": "^3.10.0",    // Validation resolvers
  "zod": "3.25.76"                      // Schema validation
}
```

### Utilities & Helpers
```json
{
  "date-fns": "4.1.0",                  // Date manipulation
  "lucide-react": "^0.454.0",           // Icons library
  "sonner": "^1.7.4",                   // Toast notifications
  "cmdk": "1.0.4",                      // Command palette
  "vaul": "^0.9.9",                     // Drawer component
  "input-otp": "1.4.1",                 // OTP inputs
  "embla-carousel-react": "8.5.1",      // Carousel
  "react-resizable-panels": "^2.1.7"   // Resizable layouts
}
```

### Analytics & Monitoring
```json
{
  "@vercel/analytics": "latest"         // Vercel Analytics
}
```

---

## 📁 هيكل المشروع

```
frontend/
├── app/                          # Next.js App Router (الصفحات)
│   ├── layout.tsx               # Root layout (RTL/LTR + Providers)
│   ├── page.tsx                 # الصفحة الرئيسية (Dashboard)
│   ├── globals.css              # Global styles
│   │
│   ├── api/                     # API Routes (Next.js)
│   │   ├── mindq/              # Proxy للـ Backend API
│   │   └── uploads/            # File upload endpoint
│   │
│   ├── pipeline/               # صفحة تشغيل Pipeline
│   ├── results/                # عرض نتائج Runs
│   ├── phases/                 # معلومات المراحل
│   ├── bi/                     # Business Intelligence
│   ├── bi-enhanced/            # BI متقدم
│   ├── bi-intelligence/        # BI Intelligence
│   ├── bi-raw/                 # Raw BI Data
│   ├── sla/                    # SLA Tracking
│   ├── sources/                # إدارة مصادر البيانات
│   ├── settings/               # الإعدادات
│   └── runs/                   # إدارة Runs
│       └── [runId]/           # صفحات Run محدد
│           └── analysis/      # تحليل Run
│
├── components/                  # المكونات القابلة لإعادة الاستخدام
│   ├── ui/                     # shadcn/ui components
│   │   ├── button.tsx
│   │   ├── card.tsx
│   │   ├── dialog.tsx
│   │   ├── select.tsx
│   │   ├── tabs.tsx
│   │   └── ... (40+ components)
│   │
│   ├── BI/                     # مكونات BI
│   ├── help/                   # نظام المساعدة
│   │   ├── help-context.tsx   # Help state management
│   │   ├── help-panel.tsx     # Help sidebar
│   │   └── help-trigger.tsx   # Help buttons
│   │
│   ├── header.tsx              # Header component
│   ├── sidebar.tsx             # Sidebar navigation
│   ├── pipeline-status.tsx     # Pipeline status tracker
│   ├── language-toggle.tsx     # زر تبديل اللغة
│   ├── theme-provider.tsx      # Dark/Light mode provider
│   ├── schema-glossary.tsx     # عرض Schema
│   ├── bi-chart.tsx            # مكون الرسوم البيانية
│   └── VisualizationAdapter.tsx # محول التصورات المتقدمة
│
├── context/                     # React Contexts
│   └── language-context.tsx    # إدارة اللغة العالمية
│
├── lib/                        # Utilities & Helpers
│   ├── api.ts                  # API client class
│   ├── i18n.ts                 # نظام الترجمة
│   └── utils.ts                # Helper functions
│
├── src/                        # مكونات إضافية منظمة
│   └── bi/                     # BI-specific modules
│       ├── components/
│       │   └── layer2/        # مخططات متقدمة
│       │       ├── HeatmapChart.tsx
│       │       ├── BoxPlotChart.tsx
│       │       ├── WaterfallChart.tsx
│       │       ├── ScatterChart.tsx
│       │       └── MultiAxisLineChart.tsx
│       ├── data/
│       │   └── provider.tsx   # BI data provider
│       └── pages/             # BI pages
│
├── hooks/                      # Custom React Hooks
├── config/                     # Configuration files
│   └── features.ts            # Feature flags
│
├── public/                     # Static assets
├── styles/                     # Additional styles
├── scripts/                    # Build & utility scripts
│   ├── run-prebuild.mjs       # Pre-build checks
│   └── check-performance-budget.mjs
│
├── package.json               # Dependencies
├── tsconfig.json              # TypeScript config
├── next.config.mjs            # Next.js config
├── tailwind.config.js         # Tailwind config
├── postcss.config.mjs         # PostCSS config
└── components.json            # shadcn/ui config
```

---

## 📄 الصفحات الرئيسية

### 1. الصفحة الرئيسية (`/`)
**الملف**: `app/page.tsx`

**الوظيفة**:
- Dashboard رئيسي مع بطاقات سريعة
- روابط إلى جميع الأقسام الرئيسية
- نظرة عامة على الحالة

**المكونات المستخدمة**:
- `Card` - لعرض أقسام مختلفة
- `Button` - للتنقل
- `HelpTrigger` - للمساعدة السياقية

---

### 2. صفحة Pipeline (`/pipeline`)
**الملف**: `app/pipeline/page.tsx`

**الوظيفة**:
- تشغيل Pipeline كامل (Stages 01-10)
- رفع ملفات البيانات و SLA
- إعدادات Pipeline (stop_on_error، llm_summary)
- متابعة حالة التنفيذ

**المكونات الرئيسية**:
```tsx
<FileUpload />           // رفع CSV/Parquet
<SLAUpload />           // رفع SLA PDFs
<PipelineConfig />      // إعدادات التشغيل
<PipelineStatus />      // Progress tracker
<PhaseList />           // قائمة المراحل وحالتها
```

**API المستخدمة**:
```typescript
// رفع الملفات
api.uploadFile(file) → UploadResponse

// تشغيل Pipeline
api.runFullPipeline(runId, {
  data_files: string[],
  sla_files: string[],
  stop_on_error: boolean,
  llm_summary: boolean
}) → PipelineResponse

// متابعة الحالة (polling كل 5 ثوانٍ)
api.getPipelineStatus(runId) → PipelineProgress
```

---

### 3. صفحة النتائج (`/results`)
**الملف**: `app/results/page.tsx`

**الوظيفة**:
- عرض جميع Runs السابقة
- استعراض Artifacts كل Run
- تنزيل ملفات JSON/Parquet
- معاينة محتوى الملفات

**المكونات**:
```tsx
<RunsList />            // قائمة Runs
<ArtifactBrowser />     // متصفح Artifacts
<FilePreview />         // معاينة JSON/CSV
<DownloadButton />      // تنزيل ملفات
```

**API**:
```typescript
// قائمة Runs
api.listRuns() → RunListResponse

// Artifacts لـ Run محدد
api.listRunArtifacts(runId) → RunArtifactsResponse

// محتوى ملف محدد
api.getArtifactContent(runId, path) → ArtifactContentResponse
```

---

### 4. صفحة BI (`/bi`)
**الملف**: `app/bi/page.tsx`

**الوظيفة**:
- عرض metrics ومؤشرات الأداء
- رسوم بيانية تفاعلية
- KPI Dashboard
- Insights & Recommendations

**المكونات**:
```tsx
<MetricsGrid />         // شبكة المؤشرات
<BiChart />             // رسوم بيانية
<InsightsPanel />       // Insights
<CorrelationMatrix />   // مصفوفة الارتباطات
<KpiCards />           // بطاقات KPI
```

**API**:
```typescript
// استرجاع Metrics
api.getBiMetrics(run) → Record<string, unknown>

// KPI Catalog
api.getBiKpiCatalog(run) → Record<string, unknown>

// Insights
api.getBiInsights(run) → Record<string, unknown>

// Correlations
api.getBiCorrelations(run, top) → Record<string, unknown>

// BI Query (SQL)
api.biQuery(runId, sql, options) → { rows, n }
```

---

### 5. صفحة SLA (`/sla`)
**الملف**: `app/sla/page.tsx`

**الوظيفة**:
- تتبع SLA Compliance
- Gap Analysis
- SOP (Standard Operating Procedures)
- AI Assistant للأسئلة عن SLA

**المكونات**:
```tsx
<SlaOverview />         // نظرة عامة
<GapAnalysis />         // تحليل الفجوات
<SopViewer />           // عرض SOPs
<SlaAssistant />        // AI Chat للاستفسارات
```

**API**:
```typescript
// SLA Summary
api.getSlaSummary(run) → Record<string, unknown>

// SOP
api.getSlaSop(run) → Record<string, unknown>

// Gap Analysis
api.getSlaGapAnalysis(run) → Record<string, unknown>

// AI Assistant
api.converseSlaAssistant({
  run, question, history, provider, model
}) → SlaAssistantResponse
```

---

### 6. صفحة Sources (`/sources`)
**الملف**: `app/sources/page.tsx`

**الوظيفة**:
- إدارة مصادر البيانات
- عرض Datasets المسجلة
- Configurations

---

### 7. صفحة Settings (`/settings`)
**الملف**: `app/settings/page.tsx`

**الوظيفة**:
- تفضيلات المستخدم
- إعدادات النظام
- API Credentials (LLM providers)

---

### 8. صفحة Phases (`/phases`)
**الملف**: `app/phases/page.tsx`

**الوظيفة**:
- معلومات تفصيلية عن كل مرحلة (01-10)
- شرح المدخلات والمخرجات
- Common failures ونصائح

---

## 🧩 المكونات الأساسية

### 1. Layout Components

#### `Sidebar` (`components/sidebar.tsx`)
```tsx
// التنقل الجانبي الرئيسي
<Sidebar>
  - Dashboard
  - Pipeline
  - Results
  - BI
  - SLA
  - Sources
  - Settings
</Sidebar>
```

**الميزات**:
- تصميم عمودي قابل للطي
- أيقونات من `lucide-react`
- دعم RTL/LTR
- Active state highlighting

---

#### `Header` (`components/header.tsx`)
```tsx
// الرأس العلوي
<Header>
  - Logo
  - Page title
  - Language toggle
  - Theme toggle
  - Help trigger
</Header>
```

---

### 2. Form Components

#### `FileUpload`
```tsx
// رفع ملفات
<FileUpload
  accept=".csv,.parquet"
  multiple={true}
  onUpload={(files) => {
    // استخدام api.uploadFile()
  }}
/>
```

**تقنيات**:
- `react-hook-form` للإدارة
- Drag & drop support
- Progress indicators
- File type validation

---

### 3. Data Display Components

#### `BiChart` (`components/bi-chart.tsx`)
```tsx
import { BiChart } from "@/components/bi-chart"

<BiChart
  data={rows}
  chartType="bar" // bar, line, area, pie, scatter
  xKey="date"
  valueKey="amount"
  height={400}
/>
```

**المحرك**: ECharts 5.6.0
**الميزات**:
- Canvas renderer (أداء عالٍ)
- Progressive rendering
- Responsive
- Theme-aware (dark/light)
- RTL-compatible

---

#### `VisualizationAdapter` (`components/VisualizationAdapter.tsx`)
```tsx
import { VisualizationAdapter } from "@/components/VisualizationAdapter"

<VisualizationAdapter
  data={rows}
  viz={{
    chartType: "heatmap", // heatmap, boxplot, waterfall, scatter, multi-line
    xKey: "dt",
    valueKey: "val"
  }}
  height={360}
/>
```

**الرسوم المدعومة**:
- **Heatmap** - خرائط حرارية
- **BoxPlot** - رسوم الصندوق
- **Waterfall** - رسوم الشلال
- **Scatter** - مخططات التشتت
- **Multi-Axis Line** - خطوط متعددة المحاور

**تقنية التحميل**:
```tsx
// Dynamic imports للأداء
const HeatmapChart = dynamic(
  () => import("@/src/bi/components/layer2/HeatmapChart"),
  { ssr: false }
)
```

---

### 4. Status & Progress Components

#### `PipelineStatus` (`components/pipeline-status.tsx`)
```tsx
<PipelineStatus
  runId={runId}
  onComplete={(result) => {
    // معالجة الاكتمال
  }}
/>
```

**الميزات**:
- Real-time polling (كل 5 ثوانٍ)
- Progress bar
- Phase-by-phase status
- Error handling
- Deferred jobs tracking

---

### 5. UI Primitives (shadcn/ui)

جميع المكونات الأساسية موجودة في `components/ui/`:

```tsx
// Examples
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Dialog } from "@/components/ui/dialog"
import { Select } from "@/components/ui/select"
import { Tabs } from "@/components/ui/tabs"
import { Toast } from "@/components/ui/toast"

// Usage
<Button variant="default" size="lg">
  Submit
</Button>

<Card>
  <CardHeader>
    <CardTitle>Title</CardTitle>
  </CardHeader>
  <CardContent>
    Content here
  </CardContent>
</Card>
```

**المكونات المتوفرة** (40+ component):
- Accordion
- Alert Dialog
- Avatar
- Badge
- Button
- Calendar
- Card
- Checkbox
- Collapsible
- Command
- Context Menu
- Dialog
- Dropdown Menu
- Form
- Hover Card
- Input
- Label
- Menubar
- Navigation Menu
- Popover
- Progress
- Radio Group
- Scroll Area
- Select
- Separator
- Sheet
- Skeleton
- Slider
- Switch
- Table
- Tabs
- Textarea
- Toast
- Toggle
- Tooltip
- ... والمزيد

---

## 🌐 إدارة الحالة والسياق

### 1. Language Context (`context/language-context.tsx`)

**الوظيفة**: إدارة اللغة (عربي/إنجليزي) على مستوى التطبيق

```tsx
"use client"
import { useLanguage } from "@/context/language-context"

function MyComponent() {
  const { language, setLanguage, toggleLanguage, translate } = useLanguage()
  
  return (
    <div>
      <p>{translate("welcome_message")}</p>
      <button onClick={toggleLanguage}>
        {language === "ar" ? "Switch to English" : "التحويل للعربية"}
      </button>
    </div>
  )
}
```

**الميزات**:
- Persistent storage في `localStorage`
- تحديث `<html dir="rtl|ltr">`
- نظام ترجمة مدمج
- Hot-swapping بدون reload

**التخزين**: `localStorage.getItem("mindq.preferred-language")`

---

### 2. Help Context (`components/help/help-context.tsx`)

**الوظيفة**: إدارة نظام المساعدة السياقية

```tsx
import { useHelpCenter } from "@/components/help/help-context"

function MyComponent() {
  const { openTopic } = useHelpCenter()
  
  return (
    <button onClick={() => openTopic({
      id: "pipeline-basics",
      title: "كيفية تشغيل Pipeline",
      summary: "دليل سريع لتشغيل تحليل البيانات",
      body: "...",
      sources: [{ label: "Documentation", href: "/docs" }],
      suggestedQuestions: ["كيف أرفع الملفات؟"]
    })}>
      المساعدة
    </button>
  )
}
```

**المكونات**:
- `HelpProvider` - Context provider
- `HelpPanel` - Sidebar للمساعدة
- `HelpTrigger` - أزرار المساعدة
- `useHelpCenter` - Hook للوصول

---

### 3. Theme (Dark/Light Mode)

**المكتبة**: `next-themes`
**المكون**: `components/theme-provider.tsx`

```tsx
import { useTheme } from "next-themes"

function ThemeToggle() {
  const { theme, setTheme } = useTheme()
  
  return (
    <button onClick={() => setTheme(theme === "dark" ? "light" : "dark")}>
      Toggle Theme
    </button>
  )
}
```

---

## 🔌 الاتصال مع Backend

### API Client Class

**الملف**: `lib/api.ts`

**البنية**:
```typescript
class MindQAPI {
  private baseURL: string
  private biQueryCache: Map<...>
  
  constructor(baseURL: string = API_BASE_URL)
  
  // Core methods
  private buildURL(path: string): string
  private handleResponse<T>(response: Response): Promise<T>
  private get<T>(path: string): Promise<T>
  private post<T>(path: string, payload?: unknown): Promise<T>
  
  // Public API methods (60+ methods)
  async healthCheck(): Promise<Record<string, unknown>>
  async uploadFile(file: File): Promise<UploadResponse>
  async runFullPipeline(...): Promise<PipelineResponse>
  async getPipelineStatus(...): Promise<PipelineProgress>
  async getBiMetrics(...): Promise<Record<string, unknown>>
  // ... المزيد
}

export const api = new MindQAPI()
```

---

### Configuration

**متغيرات البيئة**:
```env
# Backend API Base URL
NEXT_PUBLIC_API_BASE_URL=http://localhost:9000

# أو في Production
NEXT_PUBLIC_API_BASE_URL=https://api.mindq.example.com
```

**الافتراضي**: `/api/mindq` (Next.js API proxy)

---

### API Proxy (Next.js Route)

**الملف**: `app/api/mindq/[...segments]/route.ts`

**الوظيفة**: إعادة توجيه الطلبات إلى Backend مع معالجة CORS

```typescript
// مثال على الطلب
fetch("/api/mindq/v1/runs/demo/pipeline/status")
// يُعاد توجيهه إلى:
// http://localhost:9000/v1/runs/demo/pipeline/status
```

**الفوائد**:
- تجنب CORS issues
- نفس الـ origin للـ cookies
- Caching محتمل
- Error handling موحد

---

### API Methods Categories

#### 1. Pipeline Management
```typescript
// تشغيل مراحل فردية
api.runPhase01(runId, request)
api.runPhase(runId, "02", request)
api.runPhase10(runId, request)

// تشغيل Pipeline كامل
api.runFullPipeline(runId, request, { asyncMode: true })

// متابعة الحالة
api.getPipelineStatus(runId)

// Timeline & Artifacts
api.getRunTimeline(runId)
api.listRunArtifacts(runId)
api.getArtifactContent(runId, path)
```

#### 2. BI & Analytics
```typescript
// Metrics & KPIs
api.getBiMetrics(run)
api.getBiKpiCatalog(run)
api.getBiDimensions(run)

// Data queries
api.biQuery(runId, sql, options)
api.biPlan(runId, question, options) // LLM query planning

// Insights
api.getBiInsights(run)
api.getBiCorrelations(run, top)
api.explainBiCorrelation(request)
api.explainBiChart(request)
```

#### 3. SLA Management
```typescript
api.getSlaSummary(run)
api.getSlaSop(run)
api.getSlaGapAnalysis(run)
api.converseSlaAssistant(request)
```

#### 4. File Operations
```typescript
api.uploadFile(file)
```

#### 5. Schema & Terminology
```typescript
api.getSchemaTerminology(runId, artifactsRoot, format)
```

---

### Request/Response Types

جميع الأنواع موثقة في `lib/api.ts`:

```typescript
// Examples
interface PipelineRequest {
  data_files: string[]
  sla_files?: string[]
  artifacts_root?: string
  stop_on_error?: boolean
  llm_credentials_file?: string
  llm_summary?: boolean
}

interface PipelineProgress {
  run_id?: string
  status: "running" | "completed" | "failed" | "completed_with_deferred"
  current_phase?: string | null
  completed_count: number
  total_count: number
  percent_complete: number
  phases: PipelineProgressPhase[]
  updated_at: string
  skipped?: string[]
  error?: string
  deferred?: string[]
  async_jobs?: Record<string, AsyncJobInfo>
}

interface BiPhaseResponse {
  status: string
  run_id: string
  artifacts_root: string
  semantic: BiSemanticPayload
  marts: BiMartPreview[]
  llm_enabled: boolean
  llm: BiLlmState
  builder?: Record<string, unknown>
}
```

---

### Error Handling

```typescript
try {
  const result = await api.getBiMetrics("demo")
} catch (error) {
  // Error message مُستخرج من response
  console.error(error.message)
  
  // مثال:
  // "Request failed with 404 Not Found"
  // "Run 'demo' not found"
}
```

**المعالجة**:
- استخراج `detail` من JSON responses
- استخراج رسائل validation من FastAPI
- Fallback لـ status text

---

## 🌍 نظام الترجمة (i18n)

### البنية

**الملف**: `lib/i18n.ts`

```typescript
export const LANGUAGES = [
  { code: "ar", name: "العربية", direction: "rtl" },
  { code: "en", name: "English", direction: "ltr" }
]

export const DEFAULT_LOCALE = "ar"

export const dictionaries = {
  ar: {
    "welcome_message": "مرحباً بك في Mind-Q",
    "pipeline_page_title": "تشغيل Pipeline",
    "run_pipeline": "تشغيل التحليل",
    // ... مئات المفاتيح
  },
  en: {
    "welcome_message": "Welcome to Mind-Q",
    "pipeline_page_title": "Run Pipeline",
    "run_pipeline": "Run Analysis",
    // ...
  }
}

export function getDirection(lang: Language): "rtl" | "ltr" {
  return lang === "ar" ? "rtl" : "ltr"
}
```

---

### الاستخدام

#### 1. في المكونات
```tsx
import { useLanguage } from "@/context/language-context"

function MyComponent() {
  const { translate } = useLanguage()
  
  return (
    <div>
      <h1>{translate("welcome_message")}</h1>
      <p>{translate("user_count", { count: 42 })}</p>
      {/* Output: "لديك 42 مستخدم" */}
    </div>
  )
}
```

#### 2. مع Placeholders
```typescript
// Dictionary
{
  "user_count": "لديك {count} مستخدم"
}

// Usage
translate("user_count", { count: 42 })
// → "لديك 42 مستخدم"
```

#### 3. تبديل اللغة
```tsx
function LanguageToggle() {
  const { language, toggleLanguage } = useLanguage()
  
  return (
    <button onClick={toggleLanguage}>
      {language === "ar" ? "EN" : "عربي"}
    </button>
  )
}
```

---

### RTL/LTR Support

**تلقائي في Layout**:
```tsx
// app/layout.tsx
<html lang={language} dir={getDirection(language)}>
```

**Tailwind RTL Classes**:
```tsx
// يتحول تلقائياً حسب dir
<div className="mr-4">  {/* يصبح ml-4 في RTL */}
  Content
</div>

// أو استخدام rtl: و ltr:
<div className="rtl:text-right ltr:text-left">
  Text
</div>
```

---

## 📊 التصورات والرسوم البيانية

### ECharts Integration

**المكتبة الأساسية**: `echarts` + `echarts-for-react`

**الميزات**:
- Canvas renderer (أداء عالٍ)
- Lazy loading
- Progressive rendering
- DataZoom, Brush, Toolbox
- Theme support

---

### BiChart Component

**الملف**: `components/bi-chart.tsx`

```tsx
import { BiChart } from "@/components/bi-chart"

<BiChart
  data={[
    { dt: "2025-01-01", val: 100 },
    { dt: "2025-01-02", val: 150 },
  ]}
  chartType="line"      // bar, line, area, pie, scatter
  xKey="dt"
  valueKey="val"
  height={400}
  title="Sales Over Time"
  color="#3b82f6"       // Custom color
/>
```

**الخيارات**:
- `chartType`: نوع الرسم
- `xKey`: مفتاح المحور X
- `valueKey`: مفتاح القيمة
- `height`: الارتفاع بالبكسل
- `title`: العنوان
- `color`: لون مخصص

---

### Advanced Charts (Layer 2)

**المجلد**: `src/bi/components/layer2/`

#### 1. Heatmap Chart
```tsx
import { HeatmapChart } from "@/src/bi/components/layer2/HeatmapChart"

<HeatmapChart
  data={[
    { x: "Mon", y: "Morning", value: 23 },
    { x: "Mon", y: "Evening", value: 45 },
  ]}
  height={400}
/>
```

**Use Cases**: Correlation matrices، جداول التكرار، أنماط زمنية

---

#### 2. Box Plot Chart
```tsx
import { BoxPlotChart } from "@/src/bi/components/layer2/BoxPlotChart"

<BoxPlotChart
  data={distributionData}
  height={400}
/>
```

**Use Cases**: توزيع البيانات، outliers، quartiles

---

#### 3. Waterfall Chart
```tsx
import { WaterfallChart } from "@/src/bi/components/layer2/WaterfallChart"

<WaterfallChart
  data={[
    { category: "Initial", value: 1000 },
    { category: "Sales", value: 500 },
    { category: "Costs", value: -200 },
    { category: "Final", value: 1300 }
  ]}
  height={400}
/>
```

**Use Cases**: التدفقات المالية، التغيرات التراكمية

---

#### 4. Scatter Chart
```tsx
import { ScatterChart } from "@/src/bi/components/layer2/ScatterChart"

<ScatterChart
  data={[
    { x: 10, y: 20, size: 5, category: "A" },
    { x: 15, y: 25, size: 8, category: "B" },
  ]}
  height={400}
/>
```

**Use Cases**: علاقات بين متغيرين، clustering visual

---

#### 5. Multi-Axis Line Chart
```tsx
import { MultiAxisLineChart } from "@/src/bi/components/layer2/MultiAxisLineChart"

<MultiAxisLineChart
  data={multiSeriesData}
  height={400}
/>
```

**Use Cases**: مقارنة metrics مختلفة القياس

---

### VisualizationAdapter

**الاستخدام الموحد**:
```tsx
import { VisualizationAdapter } from "@/components/VisualizationAdapter"

<VisualizationAdapter
  data={rows}
  viz={{
    engine: "echarts",      // محرك الرسم
    chartType: "heatmap",   // نوع الرسم
    xKey: "date",          // محور X
    valueKey: "amount"     // القيمة
  }}
  height={400}
/>
```

**الفوائد**:
- واجهة موحدة
- Dynamic imports (code splitting)
- Fallback للرسوم الأساسية
- SSR-safe

---

### Chart Performance

**التحسينات**:
1. **Canvas Renderer** - أسرع من SVG للبيانات الكثيرة
2. **Progressive Rendering** - رسم تدريجي للبيانات الضخمة
3. **Data Sampling** - أخذ عينات للبيانات >10k نقطة
4. **Lazy Loading** - تحميل المخططات المتقدمة عند الحاجة
5. **Caching** - cache النتائج في API client

```tsx
// مثال على Performance Budget
// scripts/check-performance-budget.mjs
{
  maxBundleSize: "500kb",
  maxInitialLoad: "2s"
}
```

---

## 🆘 نظام المساعدة

### Help Context System

**المكونات**:
1. **HelpProvider** - Context provider
2. **HelpPanel** - Sidebar للمساعدة
3. **HelpTrigger** - أزرار تفعيل

---

### HelpTrigger Usage

```tsx
import { HelpTrigger } from "@/components/help/help-trigger"

<HelpTrigger
  topic={{
    id: "pipeline-config",
    title: "إعدادات Pipeline",
    summary: "شرح خيارات التشغيل",
    body: `
      ### stop_on_error
      إيقاف Pipeline عند أول خطأ
      
      ### llm_summary
      إنشاء ملخص بواسطة AI
    `,
    sources: [
      {
        label: "PHASES_DETAILED_GUIDE.md",
        href: "/docs/phases"
      }
    ],
    suggestedQuestions: [
      "ماذا يحدث عند stop_on_error؟",
      "كم يكلف LLM summary؟"
    ]
  }}
/>
```

---

### HelpPanel Features

**الميزات**:
- Slide-in من اليمين (RTL) أو اليسار (LTR)
- Markdown rendering
- روابط للمصادر
- أسئلة مقترحة
- Close button

**التصميم**:
```tsx
<Sheet>
  <SheetContent side={language === "ar" ? "left" : "right"}>
    <SheetHeader>
      <SheetTitle>{topic.title}</SheetTitle>
    </SheetHeader>
    
    <div className="prose">
      {/* Markdown body */}
    </div>
    
    {topic.sources && (
      <div className="sources">
        {/* روابط المصادر */}
      </div>
    )}
    
    {topic.suggestedQuestions && (
      <div className="suggested">
        {/* أسئلة مقترحة */}
      </div>
    )}
  </SheetContent>
</Sheet>
```

---

## 🤖 Generative AI في Frontend

### نظرة عامة

واجهة Mind-Q تحتوي على **ميزات AI تفاعلية** تظهر للمستخدم مباشرة:

1. **🔍 شرح الرسوم البيانية** (Chart Explain Button)
2. **🔗 شرح الارتباطات** (Correlation Explain)
3. **🎯 تخطيط BI ذكي** (Smart BI Planning)

كل هذه الميزات تستدعي **Backend LLM APIs** وتعرض النتائج بشكل تفاعلي.

---

### 1️⃣ شرح الرسوم البيانية (Chart Explain)

**المكون**: `ChartExplainButton.tsx`  
**الموقع**: `frontend/src/bi/components/ChartExplainButton.tsx`

#### كيف يعمل في الواجهة؟

```tsx
import { ChartExplainButton } from "@/src/bi/components/ChartExplainButton"

// استخدام المكون مع أي رسم بياني
<BiChart
  data={salesData}
  chartType="line"
  xKey="date"
  valueKey="amount"
/>

<ChartExplainButton
  chartTitle="مبيعات الشهر"
  chartType="line"
  dataSummary={`${salesData.length} نقطة بيانات`}
  onExplain={async (context) => {
    // استدعاء Backend API
    const response = await fetch("/api/bi/charts/explain", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        chart_title: context.title,
        chart_type: context.type,
        data_summary: context.summary,
        language: "ar",
        use_llm: true
      })
    })
    
    const data = await response.json()
    return data.explanation  // النص العربي
  }}
/>
```

#### ما يراه المستخدم:

1. **زر "اشرح بواسطة LLM"** 🤖 مع أيقونة Sparkles ✨
2. عند الضغط:
   - يتحول الزر → **"جاري التحليل..."** مع spinner
   - استدعاء Backend API
   - بعد 2-5 ثواني تظهر **Card** بالشرح

3. **الشرح يظهر في Card** بالعربية:
   ```
   ✨ هذا الرسم البياني الخطي يوضح اتجاه المبيعات على مدار 30 يوماً.
   
   الملاحظات الرئيسية:
   - ارتفاع ملحوظ في الأسبوع الثالث (+25%)
   - انخفاض طفيف في نهاية الشهر
   
   التوصيات:
   - التركيز على فترات الذروة
   - مراجعة أسباب الانخفاض
   ```

#### الميزات:
- ✅ **Compact mode** (زر صغير)
- ✅ **Loading state** (spinner أثناء التحميل)
- ✅ **Error handling** (رسائل خطأ واضحة)
- ✅ **RTL Support** (عربي/إنجليزي)
- ✅ **Cache explanation** (حفظ الشرح بدون إعادة طلب)

---

### 2️⃣ شرح الارتباطات (Correlation Explain)

**الموقع**: `frontend/src/bi/pages/StoryBIPage.tsx`

#### كيف يعمل؟

عند عرض **مصفوفة الارتباطات** (Correlation Matrix)، المستخدم يمكنه:

```tsx
// في StoryBIPage.tsx
const handleExplainCorrelation = async (featureA: string, featureB: string) => {
  try {
    const response = await api.explainBiCorrelation({
      run: runId,
      feature_a: featureA,
      feature_b: featureB,
      language: "ar",
      use_llm: true,
      provider: "openai",
      model: "gpt-4o-mini"
    })
    
    // عرض الشرح
    setCorrelationExplanation(response.explanation.summary)
  } catch (error) {
    console.error("Failed to explain correlation")
  }
}

// في الواجهة
<CorrelationMatrix
  data={correlations}
  onCellClick={(a, b) => handleExplainCorrelation(a, b)}
/>
```

#### ما يراه المستخدم:

1. **مصفوفة حرارية** تعرض الارتباطات بين المتغيرات
2. عند الضغط على خلية (مثلاً: ارتباط بين "وقت التوصيل" و "رضا العميل")
3. يظهر **شرح ذكي**:
   ```
   🔗 الارتباط: -0.72 (ارتباط سلبي قوي)
   
   التفسير:
   كلما زاد وقت التوصيل، انخفض رضا العميل بشكل ملحوظ.
   هذه علاقة عكسية قوية تشير إلى أن تحسين سرعة التوصيل
   سيؤدي مباشرة إلى زيادة رضا العملاء.
   
   الإجراءات الموصى بها:
   - تقليل متوسط وقت التوصيل من 45 إلى 30 دقيقة
   - التركيز على المناطق ذات الأداء المنخفض
   - مراجعة إجراءات التوجيه
   ```

#### الميزات:
- ✅ **Context-aware** (يفهم نوع البيانات واللوجستيات)
- ✅ **Actionable insights** (توصيات عملية)
- ✅ **Statistical context** (قوة الارتباط، الاتجاه)
- ✅ **Bilingual** (عربي/إنجليزي)

---

### 3️⃣ تخطيط BI ذكي (Smart BI Planning)

**API Method**: `api.biPlan()`  
**الموقع**: `frontend/lib/api.ts`

#### كيف يعمل؟

المستخدم يكتب **سؤال بلغة طبيعية** ↓ LLM يحوله إلى:
- SQL query
- نوع الرسم المناسب
- تكوين ECharts

```tsx
import { api } from "@/lib/api"

// استخدام في مكون
const [query, setQuery] = useState("")
const [result, setResult] = useState(null)

const handleAskBI = async () => {
  try {
    const response = await api.biPlan(
      "demo",
      "أريد رسم بياني لمتوسط وقت التوصيل حسب المدينة",
      { llm_enabled: true }
    )
    
    // النتيجة:
    // {
    //   plan: {
    //     sql: "SELECT city, AVG(delivery_time) FROM ...",
    //     chart_type: "bar",
    //     explain_ar: "رسم بياني عمودي يقارن ..."
    //   },
    //   data: [ ... ]
    // }
    
    setResult(response)
  } catch (error) {
    console.error("BI Planning failed")
  }
}

// في الواجهة
<div>
  <Input
    value={query}
    onChange={(e) => setQuery(e.target.value)}
    placeholder="اسأل عن بياناتك بلغة طبيعية..."
  />
  <Button onClick={handleAskBI}>تحليل</Button>
  
  {result && (
    <>
      <p>{result.plan.explain_ar}</p>
      <BiChart
        data={result.data}
        chartType={result.plan.chart_type}
        xKey="city"
        valueKey="avg_time"
      />
    </>
  )}
</div>
```

#### أمثلة أسئلة يفهمها:

| السؤال بالعربية | النتيجة |
|-----------------|---------|
| "أريد رسم خطي لاتجاه المبيعات" | Line chart + SQL لـ daily sales trend |
| "قارن الأداء بين الفروع" | Bar chart + SQL لـ performance by branch |
| "ما هي أكثر المنتجات مبيعاً؟" | Pie chart + SQL لـ top products |
| "اتجاه التكاليف الشهرية" | Line chart + SQL لـ monthly costs |

---

### 📊 كيفية دمج AI في الصفحات

```tsx
// في StoryBIPage.tsx
const [chartExplanations, setChartExplanations] = useState<Record<string, string>>({})
const [chartExplainingKey, setChartExplainingKey] = useState<string | null>(null)

const handleExplainChart = async (chartKey: string, context) => {
  setChartExplainingKey(chartKey)
  
  try {
    const response = await fetch("/api/bi/charts/explain", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        chart_title: context.title,
        chart_type: context.type,
        language: "ar",
        use_llm: true
      })
    })
    
    const data = await response.json()
    setChartExplanations(prev => ({ ...prev, [chartKey]: data.explanation }))
    return data.explanation
  } finally {
    setChartExplainingKey(null)
  }
}

// استخدام مع أي رسم
<>
  <BiChart data={dailyData} chartType="line" />
  
  <ChartExplainButton
    chartTitle="الطلبات اليومية"
    chartType="line"
    onExplain={(ctx) => handleExplainChart("daily", ctx)}
    explanation={chartExplanations["daily"]}
    isLoading={chartExplainingKey === "daily"}
  />
</>
```

---

### 🎨 UI/UX للـ AI Features

#### **Loading State**:
```tsx
<Button disabled={isLoading}>
  {isLoading ? (
    <>
      <Loader2 className="h-4 w-4 animate-spin" />
      جاري التحليل...
    </>
  ) : (
    <>
      <Sparkles className="h-4 w-4" />
      اشرح بواسطة LLM
    </>
  )}
</Button>
```

#### **Explanation Card**:
```tsx
{explanation && (
  <Card className="border-primary/30 bg-primary/5">
    <CardContent className="pt-4">
      <div className="flex items-start gap-2">
        <Sparkles className="h-4 w-4 text-primary" />
        <p className="text-sm whitespace-pre-wrap">
          {explanation}
        </p>
      </div>
    </CardContent>
  </Card>
)}
```

---

### 📋 TypeScript Types

**الملف**: `frontend/lib/api.ts`

```typescript
// Chart Explanation
export interface ChartExplainRequest {
  chart_title: string
  chart_type?: string
  data_summary?: string | null
  language?: "ar" | "en"
  use_llm?: boolean
  provider?: string | null
  model?: string | null
}

export interface ChartExplainResponse {
  explanation: string
  mode: "llm" | "fallback"
  provider?: string
  tokens_in?: number
  tokens_out?: number
  cost_estimate?: number
}

// Correlation Explanation
export interface BiCorrelationExplainRequest {
  run: string
  feature_a: string
  feature_b: string
  language?: "ar" | "en"
  use_llm?: boolean
}

// BI Planning
interface BiPlanResponse {
  plan: {
    sql: string
    chart_type: string
    explain_ar: string
  }
  data: Array<Record<string, unknown>>
}
```

---

### 💡 Best Practices

#### 1. **Cache Explanations**:
```tsx
const [cache, setCache] = useState(new Map())

const getExplanation = async (key, data) => {
  if (cache.has(key)) return cache.get(key)
  
  const explanation = await api.explainChart(data)
  setCache(prev => new Map(prev).set(key, explanation))
  return explanation
}
```

#### 2. **Error Handling**:
```tsx
try {
  return await api.explainChart({ use_llm: true, ...data })
} catch (error) {
  // Fallback
  return `رسم ${data.chart_type} يعرض ${data.points} نقطة`
}
```

#### 3. **Progressive Enhancement**:
```tsx
// تفعيل LLM فقط إذا كان متاحاً
const useLLM = process.env.NEXT_PUBLIC_LLM_ENABLED === "true"

<ChartExplainButton
  onExplain={useLLM ? handleLLMExplain : undefined}
/>
```

---

### 🎯 ملخص

| الميزة | المكون | Endpoint | الوظيفة |
|--------|--------|----------|---------|
| **شرح الرسوم** | `ChartExplainButton` | `/api/bi/charts/explain` | شرح أي رسم بياني |
| **شرح الارتباطات** | `StoryBIPage` | `api.explainBiCorrelation()` | شرح علاقات بين المتغيرات |
| **تخطيط ذكي** | Input field | `api.biPlan()` | تحويل أسئلة → SQL + Charts |

---

---

## ⚡ الأداء والتحسينات

### 1. Code Splitting

**Next.js Automatic**:
```typescript
// كل صفحة في app/ هي route منفصل
app/
  pipeline/     → /pipeline bundle
  results/      → /results bundle
  bi/           → /bi bundle
```

**Dynamic Imports**:
```tsx
// تحميل lazy للمخططات المتقدمة
const HeatmapChart = dynamic(
  () => import("@/src/bi/components/layer2/HeatmapChart"),
  { ssr: false }
)
```

---

### 2. API Caching

**BI Query Cache**:
```typescript
class MindQAPI {
  private biQueryCache: Map<string, CachedResult>
  
  async biQuery(runId, sql, options) {
    const key = JSON.stringify({ runId, sql, options })
    const cached = this.biQueryCache.get(key)
    
    if (cached && Date.now() - cached.ts < 60_000) {
      return cached.result
    }
    
    const result = await this.post(...)
    this.biQueryCache.set(key, { result, ts: Date.now() })
    return result
  }
}
```

**TTL**: 60 ثانية

---

### 3. Image Optimization

**Next.js Image**:
```tsx
import Image from "next/image"

<Image
  src="/logo.png"
  alt="Mind-Q Logo"
  width={200}
  height={50}
  priority // للصور المهمة
/>
```

**الفوائد**:
- Lazy loading تلقائي
- Responsive images
- WebP conversion
- Blur placeholder

---

### 4. Font Optimization

**Geist Fonts**:
```tsx
import { GeistSans } from "geist/font/sans"
import { GeistMono } from "geist/font/mono"

<body className={`${GeistSans.variable} ${GeistMono.variable}`}>
```

**الفوائد**:
- Self-hosted (لا طلبات خارجية)
- Variable fonts (حجم أصغر)
- Preloaded

---

### 5. Rendering Strategy

**Server Components** (افتراضي):
```tsx
// app/page.tsx - Server Component
export default function Page() {
  // يتم تصييره على السيرفر
  return <div>Content</div>
}
```

**Client Components** (عند الحاجة):
```tsx
"use client"  // Directive

export default function InteractiveComponent() {
  const [state, setState] = useState()
  // يعمل في المتصفح فقط
}
```

**متى نستخدم `"use client"`**:
- useState, useEffect
- Event handlers
- Browser APIs
- Context consumers

---

### 6. Bundle Size Budget

**الملف**: `scripts/check-performance-budget.mjs`

```javascript
const BUDGET = {
  maxBundleSize: 500 * 1024,  // 500KB
  maxInitialLoad: 2000         // 2s
}
```

**التشغيل**: `npm run perf:check`

---

### 7. Prefetching

**Next.js Link**:
```tsx
import Link from "next/link"

<Link href="/pipeline" prefetch={true}>
  Go to Pipeline
</Link>
```

**الفائدة**: تحميل مسبق للصفحة عند hover

---

## 🔒 الأمان

### 1. API Security

**HTTPS في Production**:
```env
NEXT_PUBLIC_API_BASE_URL=https://api.mindq.example.com
```

**CORS Handling**: عبر Next.js API proxy

---

### 2. Input Validation

**Zod Schemas**:
```tsx
import { z } from "zod"

const pipelineSchema = z.object({
  data_files: z.array(z.string()).min(1),
  stop_on_error: z.boolean().optional(),
  llm_summary: z.boolean().optional()
})

// في Form
<form onSubmit={async (data) => {
  const validated = pipelineSchema.parse(data)
  await api.runFullPipeline(runId, validated)
}}>
```

---

### 3. XSS Protection

**React/Next.js Built-in**:
- Automatic escaping
- Sanitized innerHTML
- CSP headers

---

## 🚀 Deployment

### Build Process

```bash
# 1. Pre-build checks
npm run prebuild          # scripts/run-prebuild.mjs

# 2. Build
npm run build            # next build

# 3. Start production
npm run start            # next start
```

---

### Environment Variables

**Production**:
```env
NODE_ENV=production
NEXT_PUBLIC_API_BASE_URL=https://api.mindq.example.com
NEXT_PUBLIC_FEATURE_BI_LAYER2=true
```

---

### Vercel Deployment

**تلقائي**:
- Push إلى `main` → auto-deploy
- Preview deployments للـ PRs
- Analytics مدمج

**التهيئة**: `vercel.json` (إذا لزم)

---

## 📚 الموارد الإضافية

### المستندات
- [Next.js Documentation](https://nextjs.org/docs)
- [React Documentation](https://react.dev)
- [Tailwind CSS](https://tailwindcss.com/docs)
- [shadcn/ui](https://ui.shadcn.com)
- [ECharts Documentation](https://echarts.apache.org/en/index.html)

### الأدلة الداخلية
- `PHASES_DETAILED_GUIDE.md` - شرح المراحل
- `README.md` - نظرة عامة
- `COLAB_GUIDE.md` - دليل Colab

---

## 🔄 سير العمل النموذجي

### تشغيل Pipeline من البداية للنهاية

```typescript
// 1. رفع ملفات البيانات
const dataFile = await api.uploadFile(csvFile)
const slaFile = await api.uploadFile(slaDoc)

// 2. تشغيل Pipeline
const runId = `run-${Date.now()}`
await api.runFullPipeline(runId, {
  data_files: [dataFile.path],
  sla_files: [slaFile.path],
  stop_on_error: false,
  llm_summary: true
})

// 3. متابعة الحالة (polling)
const pollStatus = async () => {
  const status = await api.getPipelineStatus(runId)
  
  if (status.status === "running") {
    setTimeout(pollStatus, 5000)  // كل 5 ثوانٍ
  } else {
    console.log("Pipeline completed!")
    
    // 4. عرض النتائج
    const biData = await api.getBiMetrics(runId)
    const insights = await api.getBiInsights(runId)
    
    // 5. عرض الرسوم البيانية
    // ... استخدام BiChart أو VisualizationAdapter
  }
}

pollStatus()
```

---

## 📝 ملاحظات نهائية

### Best Practices

1. **استخدم TypeScript دائماً** - للأمان وال IntelliSense
2. **Component Reusability** - أنشئ مكونات قابلة لإعادة الاستخدام
3. **Error Handling** - معالجة الأخطاء في كل API call
4. **Loading States** - أظهر حالة التحميل للمستخدم
5. **Accessibility** - ARIA labels، keyboard navigation
6. **RTL Support** - اختبر في كلا الاتجاهين
7. **Performance** - استخدم dynamic imports للمكونات الثقيلة

---

### Common Patterns

#### Loading State
```tsx
const [loading, setLoading] = useState(false)
const [data, setData] = useState(null)

useEffect(() => {
  setLoading(true)
  api.getBiMetrics(runId)
    .then(setData)
    .catch(console.error)
    .finally(() => setLoading(false))
}, [runId])

if (loading) return <Skeleton />
if (!data) return <div>No data</div>

return <DataDisplay data={data} />
```

#### Error Boundary
```tsx
"use client"
import { useEffect } from "react"

export default function Error({
  error,
  reset
}: {
  error: Error
  reset: () => void
}) {
  useEffect(() => {
    console.error(error)
  }, [error])
  
  return (
    <div>
      <h2>Something went wrong!</h2>
      <button onClick={reset}>Try again</button>
    </div>
  )
}
```

---

## 🎓 للمطورين الجدد

### Quick Start

```bash
# 1. Clone المشروع
git clone <repo-url>
cd Mind-Q-V4.1-port/frontend

# 2. تثبيت Dependencies
npm install

# 3. تشغيل Dev Server
npm run dev

# 4. افتح المتصفح
open http://localhost:3000
```

### File Structure للمطور الجديد

```
ابدأ بـ:
1. app/page.tsx          - الصفحة الرئيسية
2. components/ui/        - المكونات الأساسية
3. lib/api.ts            - فهم API client
4. context/              - فهم Contexts
5. app/pipeline/page.tsx - مثال متكامل
```

---

**📧 للدعم**: راجع `help-context.tsx` أو افتح issue في GitHub

**🔄 آخر تحديث**: نوفمبر 2025

**✨ Built with ❤️ for Logistics Intelligence**
