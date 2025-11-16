# Mind-Q V4.1 - دليل التشغيل السريع

## متطلبات التشغيل

- Python 3.11+
- Node.js 18+
- npm أو pnpm

## طريقة التشغيل الصحيحة

### ⚠️ مهم جداً: المسار الصحيح

يجب أن تكون دائماً في المجلد الرئيسي للمشروع:
```bash
cd /Users/haitham/development/Mind-Q-V4.1-port
```

---

## 🚀 الطريقة الأسهل: استخدام السكربتات

### 1️⃣ تشغيل Backend
```bash
./start_backend.sh
```

### 2️⃣ تشغيل Frontend (في terminal جديد)
```bash
./start_frontend.sh
```

### 3️⃣ تشغيل Pipeline (في terminal جديد)
```bash
./run_pipeline.sh test-run data/sample.csv
```

السكربتات تضبط `PYTHONPATH` تلقائياً وتتأكد من المسارات الصحيحة.

---

## 📝 الطريقة اليدوية

### 1️⃣ تشغيل Backend

من المجلد الرئيسي، شغّل:

```bash
python3 -c "import sys; sys.path.insert(0, '.'); sys.path.insert(0, 'backend'); from backend.src.app.services.pipeline_api.app import app; import uvicorn; uvicorn.run(app, host='0.0.0.0', port=9000)"
```

**Backend سيكون متاح على:**
- API: http://localhost:9000
- Swagger Docs: http://localhost:9000/docs
- ReDoc: http://localhost:9000/redoc

### 2️⃣ تشغيل Frontend

في terminal منفصل:

```bash
cd /Users/haitham/development/Mind-Q-V4.1-port/frontend
npm run dev
```

**Frontend سيكون متاح على:**
- http://localhost:3000

## 🔧 حل المشاكل الشائعة

### المشكلة: `No module named 'phases.01_ingestion'`

**السبب:** تشغيل السكربت من مسار خاطئ أو PYTHONPATH غير صحيح

**الحل السريع:** استخدم السكربتات الجاهزة:
```bash
./start_backend.sh   # للـ Backend
./run_pipeline.sh    # للـ Pipeline
```

**الحل اليدوي:**
1. تأكد أنك في المجلد الرئيسي: `cd /Users/haitham/development/Mind-Q-V4.1-port`
2. أضف المسار إلى PYTHONPATH:
   ```bash
   export PYTHONPATH=/Users/haitham/development/Mind-Q-V4.1-port:$PYTHONPATH
   ```
3. أو أضف في بداية السكربت:
   ```python
   import sys
   from pathlib import Path
   PROJECT_ROOT = Path(__file__).resolve().parent
   sys.path.insert(0, str(PROJECT_ROOT))
   ```

### المشكلة: `Address already in use`

**الحل:**
```bash
# إيقاف Backend
lsof -ti:9000 | xargs kill -9

# إيقاف Frontend
lsof -ti:3000 | xargs kill -9
```

### المشكلة: Frontend يتوقف عند تشغيل أوامر أخرى

**الحل:** استخدم terminal منفصل لكل خدمة (Backend و Frontend)

## 📁 هيكل المشروع

```
Mind-Q-V4.1-port/
├── backend/           # Backend FastAPI
│   └── src/
│       └── app/
├── frontend/          # Frontend Next.js
├── phases/            # Pipeline phases (مهم للـ imports!)
├── shared/            # Shared utilities
├── contracts/         # Data contracts
├── data/             # Data files
└── artifacts/        # Run artifacts
```

## 🚀 تشغيل Pipeline

من المجلد الرئيسي:

```bash
python3 cli/runner.py flow --run-id test-run-001 --dataset data/your_data.csv
```

## 🧪 اختبار LLM

```bash
python3 test_llm.py
```

## 📝 ملاحظات مهمة

1. **دائماً شغّل من المجلد الرئيسي** `/Users/haitham/development/Mind-Q-V4.1-port`
2. **استخدم terminals منفصلة** للـ Backend والـ Frontend
3. **لا تغلق terminal** اللي فيه Backend أو Frontend شغال
4. **تأكد من PYTHONPATH** إذا واجهت مشاكل في الـ imports

## 🔑 Environment Variables

تأكد من وجود ملف `backend/llm.env` مع:
```
OPENAI_API_KEY=your-key-here
OPENAI_MODEL=gpt-4
```

---

**آخر تحديث:** نوفمبر 16، 2025
