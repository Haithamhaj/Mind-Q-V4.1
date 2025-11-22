# 📖 Documentation Automation - Quick Start

## ✅ What We Built

نظام تلقائي كامل لضمان بقاء `PHASES_DETAILED_GUIDE.md` متزامن مع الكود دائماً:

### 1️⃣ سكربت التوليد التلقائي (`generate_phase_docs.py`)
يستخرج من الكود الفعلي:
- ✅ `PIPELINE_PHASE_SEQUENCE` من `app.py`
- ✅ `PHASE_MODULES` mapping
- ✅ توقيعات دوال `run()` من كل stage
- ✅ ملفات الـ outputs (JSON, parquet, etc.)
- ✅ شروط STOP/WARN من التنفيذ الفعلي

### 2️⃣ سكربت التحقق (`validate_docs.py`)
يفحص الدليل ويكتشف:
- ❌ علامات `{{TO_FILL_DATE}}` المنسية
- ❌ أرقام أسطر خاطئة (مثل `#L173` بدل `#L174`)
- ❌ ملفات مذكورة لكن غير موجودة
- ❌ اختلاف بين PIPELINE_PHASE_SEQUENCE الموثق والفعلي
- ❌ شروط STOP/WARN غير مطابقة للكود

### 3️⃣ GitHub Actions CI
- 🤖 يشتغل تلقائياً على كل PR
- 🚫 يمنع merge إذا التوثيق قديم
- 💬 يعلق على PR بالمشاكل المكتشفة

### 4️⃣ Pre-commit Hooks
- ⚡ يفحص قبل كل commit محلياً
- 🛑 يمنع commit إذا فيه `{{TO_FILL_DATE}}`
- 🔄 يحدّث الـ appendix تلقائياً

---

## 🚀 الاستخدام اليومي

### للمطوّرين:

```bash
# قبل ما تعدّل ملفات impl.py
make validate-docs          # تأكد التوثيق صحيح

# بعد تعديل impl.py أو app.py
make docs                   # ولّد appendix جديد

# قبل إنشاء PR
make check-docs             # فحص شامل + توليد
```

### لأول مرة (setup):

```bash
# تثبيت pre-commit hooks
make pre-commit-install

# تشغيل اختبار أول
make validate-docs
```

---

## 📊 مثال على Output

### `generate_phase_docs.py`:
```
✅ Generated documentation appendix: docs/GENERATED_APPENDIX.md
📊 Total lines: 295
```

### `validate_docs.py`:
```
📖 Validating: docs/PHASES_DETAILED_GUIDE.md
📄 Total lines: 1994

🔍 Checking: Placeholders...
   Found 21 issue(s)
🔍 Checking: Line References...
   ✅ OK
🔍 Checking: Pipeline Sequence...
   ✅ OK

📊 Validation Summary:
   ❌ Errors:   0
   ⚠️  Warnings: 21
   ℹ️  Info:     0
```

---

## 🎯 كيف يضمن النظام التزامن؟

### تلقائياً في CI:
1. أي PR يعدّل `impl.py` أو الدليل → يشغّل الفحص
2. إذا اكتشف مشاكل → يفشل CI ويعلق بالتفاصيل
3. المطوّر يصلح → يدفع مرة ثانية
4. CI يمرر → merge ممكن ✅

### محلياً قبل commit:
1. Pre-commit hook يشتغل تلقائياً
2. يفحص `{{TO_FILL_DATE}}` والتوثيق
3. إذا فيه مشاكل → يمنع commit
4. المطوّر يصلح → commit يمشي ✅

---

## 🔧 إصلاح المشاكل الشائعة

### ⚠️ "Found {{TO_FILL_DATE}}"
```bash
# استبدل كلهم بتاريخ اليوم
sed -i '' 's/{{TO_FILL_DATE}}/2025-11-22/g' docs/PHASES_DETAILED_GUIDE.md
```

### ❌ "Line reference #L173 incorrect"
```bash
# اكتشف رقم السطر الصحيح
grep -n "PIPELINE_PHASE_SEQUENCE" backend/src/app/services/pipeline_api/app.py
# حدّث الدليل يدوياً
```

### ⚠️ "PIPELINE_PHASE_SEQUENCE mismatch"
```bash
# شوف الـ sequence الفعلي
make docs
cat docs/GENERATED_APPENDIX.md | grep -A 20 "PIPELINE_PHASE_SEQUENCE"
# حدّث الدليل ليطابق
```

---

## 📁 الملفات الجديدة

```
scripts/
├── generate_phase_docs.py    # مولّد التوثيق التلقائي
├── validate_docs.py           # فاحص التوثيق
└── README.md                  # دليل الاستخدام المفصّل

.github/workflows/
└── docs-validation.yml        # CI workflow

.pre-commit-config.yaml        # (محدّث) + doc hooks

Makefile                       # (محدّث) + doc commands

docs/
├── PHASES_DETAILED_GUIDE.md   # (لم يتغير)
└── GENERATED_APPENDIX.md      # (جديد) appendix تلقائي
```

---

## ⚡ أوامر Makefile الجديدة

| Command | الوصف |
|---------|-------|
| `make docs` | يولّد `GENERATED_APPENDIX.md` |
| `make validate-docs` | يفحص التوثيق (warnings OK) |
| `make validate-docs-strict` | يفحص بشدة (warnings = fail) |
| `make check-docs` | فحص + توليد معاً |
| `make pre-commit-install` | تثبيت hooks |
| `make pre-commit-run` | تشغيل كل الفحوصات يدوياً |

---

## 🎓 أفضل الممارسات

### ✅ افعل:
- شغّل `make validate-docs` قبل كل PR
- حدّث `{{TO_FILL_DATE}}` بتاريخ حقيقي
- راجع `GENERATED_APPENDIX.md` بعد تغيير app.py
- اقرأ رسائل CI failures بعناية

### ❌ لا تفعل:
- commit مع `{{TO_FILL_DATE}}` موجود
- تجاهل تحذيرات validation
- bypass pre-commit hooks بدون سبب (`--no-verify`)
- تعديل `GENERATED_APPENDIX.md` يدوياً (auto-generated!)

---

## 📚 تفاصيل أكثر

راجع `scripts/README.md` للتفاصيل الكاملة:
- شرح كل validator
- أمثلة troubleshooting
- بنية السكربتات الداخلية
- خطط التحسينات المستقبلية

---

## 🎉 النتيجة

الآن التوثيق:
- ✅ **يُولّد تلقائياً** من الكود الفعلي
- ✅ **يُفحص تلقائياً** على كل PR
- ✅ **يمنع merge** إذا كان قديماً
- ✅ **يعطي feedback واضح** للمطورين

**لا مجال بعد اليوم للتوثيق يتخلف عن الكود! 🚀**
