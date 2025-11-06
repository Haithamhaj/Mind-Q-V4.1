# 🚀 دليل إعداد Mind-Q على Replit

## 📋 نظرة عامة

Mind-Q هو نظام متكامل لتحليل البيانات وإدارة الجودة يتكون من:
- **Backend**: FastAPI (Python) - على المنفذ 8000
- **Frontend**: Next.js (TypeScript/React) - على المنفذ 3000

## 🔗 روابط المشروع

- **GitHub Repository**: https://github.com/Haithamhaj/Mind-Q-V5
- **الفرع المطلوب**: `port/update-2025-10-11`
- **رابط الفرع المباشر**: https://github.com/Haithamhaj/Mind-Q-V5/tree/port/update-2025-10-11

## 📁 هيكل المشروع

```
Mind-Q-V4.1/
├── backend/           # FastAPI backend application
│   ├── src/
│   ├── adapters/
│   ├── phases/
│   └── tests/
├── frontend/          # Next.js frontend application
│   ├── app/
│   ├── components/
│   ├── lib/
│   ├── public/
│   └── styles/
├── phases/            # Data processing phases
├── config/            # Configuration files
├── contracts/         # Data contracts and schemas
└── requirements.txt   # Python dependencies
```

## 🛠️ إعداد المشروع على Replit

### الخطوة 1: إنشاء Repl جديد

1. اذهب إلى https://replit.com
2. انقر على **Create Repl**
3. اختر **Import from GitHub**
4. الصق الرابط: `https://github.com/Haithamhaj/Mind-Q-V5`
5. اختر الفرع: `port/update-2025-10-11`

### الخطوة 2: تكوين Backend (Python)

#### 2.1 تثبيت المتطلبات

```bash
# تفعيل البيئة الافتراضية (إن وجدت)
# Replit يفعلها تلقائياً

# تثبيت المكتبات
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

#### 2.2 إنشاء ملف البيئة (.env)

أنشئ ملف `.env` في المجلد الرئيسي:

```env
# Backend Configuration
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
DEBUG=True

# Frontend URL
FRONTEND_URL=http://localhost:3000

# Database (إن كان موجود)
DATABASE_URL=sqlite:///./mind_q.db

# API Keys (إن كانت مطلوبة)
# OPENAI_API_KEY=your-key-here
# ANTHROPIC_API_KEY=your-key-here
```

#### 2.3 تشغيل Backend

```bash
# من المجلد الرئيسي
python start_server.py

# أو باستخدام uvicorn مباشرة
uvicorn backend.src.app.main:app --host 0.0.0.0 --port 8000 --reload
```

### الخطوة 3: تكوين Frontend (Next.js)

#### 3.1 تثبيت المتطلبات

```bash
cd frontend
npm install
# أو
pnpm install
```

#### 3.2 إنشاء ملف البيئة

أنشئ ملف `frontend/.env.local`:

```env
# Backend API URL
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000

# Frontend Configuration
NEXT_PUBLIC_APP_NAME=Mind-Q
NEXT_PUBLIC_APP_VERSION=4.1
```

#### 3.3 تشغيل Frontend

```bash
cd frontend
npm run dev
# أو
pnpm dev
```

## 🔧 إعداد Replit.nix (متقدم)

إذا كنت تريد التحكم الكامل في البيئة، أنشئ ملف `replit.nix`:

```nix
{ pkgs }: {
  deps = [
    pkgs.python310
    pkgs.nodejs-18_x
    pkgs.nodePackages.pnpm
    pkgs.postgresql
  ];
}
```

## 📝 ملف .replit للتشغيل التلقائي

أنشئ ملف `.replit` في المجلد الرئيسي:

```toml
run = "bash start.sh"

[languages.python]
pattern = "**/*.py"
[languages.python.languageServer]
start = "pylsp"

[languages.javascript]
pattern = "**/{*.js,*.jsx,*.ts,*.tsx}"
[languages.javascript.languageServer]
start = "typescript-language-server --stdio"

[nix]
channel = "stable-22_11"

[deployment]
run = ["sh", "-c", "bash start.sh"]
```

## 🚀 سكربت التشغيل الموحد

أنشئ ملف `start.sh` لتشغيل الباك إند والفرونت معاً:

```bash
#!/bin/bash

echo "🚀 Starting Mind-Q Application..."

# Start Backend in background
echo "🔧 Starting Backend..."
python start_server.py &
BACKEND_PID=$!

# Wait for backend to be ready
sleep 5

# Start Frontend
echo "🎨 Starting Frontend..."
cd frontend
npm install
npm run dev &
FRONTEND_PID=$!

echo "✅ Application started!"
echo "📊 Backend: http://localhost:8000"
echo "🎨 Frontend: http://localhost:3000"

# Keep script running
wait $BACKEND_PID $FRONTEND_PID
```

اجعل السكربت قابل للتنفيذ:

```bash
chmod +x start.sh
```

## 🌐 الوصول إلى التطبيق

بعد التشغيل، ستكون التطبيقات متاحة على:

- **Backend API**: `http://0.0.0.0:8000`
- **API Documentation**: `http://0.0.0.0:8000/docs` (Swagger UI)
- **Frontend**: `http://localhost:3000`

في Replit، سيتم تحويل هذه المنافذ تلقائياً إلى روابط عامة.

## 🔍 API Endpoints الرئيسية

### Backend Endpoints

```
GET  /                    # Health check
GET  /health             # Health status
POST /api/upload         # Upload CSV file
GET  /api/pipelines      # List pipelines
POST /api/pipelines/run  # Run pipeline
GET  /api/results/{id}   # Get results
```

## 📊 مراحل معالجة البيانات (Phases)

المشروع يحتوي على 10 مراحل لمعالجة البيانات:

1. **Phase 01**: Data Ingestion
2. **Phase 02**: Quality Check
3. **Phase 03**: Schema Validation
4. **Phase 04**: Data Profiling
5. **Phase 05**: Missing Data Handling
6. **Phase 06**: Feature Engineering
7. **Phase 07**: Readiness Assessment
8. **Phase 08**: Insights Generation
9. **Phase 09**: Business Validation
10. **Phase 10**: BI Reporting

## 🐛 استكشاف الأخطاء

### مشكلة: Backend لا يعمل

```bash
# تحقق من السجلات
tail -f backend.err

# تحقق من المنفذ
lsof -i :8000

# أعد تشغيل Backend
pkill -f "python start_server"
python start_server.py
```

### مشكلة: Frontend لا يعمل

```bash
# حذف node_modules وإعادة التثبيت
cd frontend
rm -rf node_modules
npm install

# تحقق من ملف .env.local
cat .env.local
```

### مشكلة: خطأ في الاتصال بين Frontend و Backend

تأكد من:
1. Backend يعمل على المنفذ 8000
2. `NEXT_PUBLIC_API_URL` في `.env.local` صحيح
3. لا توجد مشاكل CORS

## 📦 المكتبات الرئيسية المستخدمة

### Backend (Python)
- FastAPI
- Pandas
- NumPy
- Pydantic
- Uvicorn
- SQLAlchemy

### Frontend (Next.js)
- React 18
- Next.js 14
- TypeScript
- Tailwind CSS
- Shadcn/ui
- Recharts

## 🔐 الأمان

تأكد من:
- عدم رفع ملفات `.env` إلى GitHub
- استخدام متغيرات البيئة في Replit Secrets
- تفعيل CORS بشكل صحيح
- استخدام HTTPS في الإنتاج

## 📚 موارد إضافية

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Next.js Documentation](https://nextjs.org/docs)
- [Replit Documentation](https://docs.replit.com/)

## 🤝 المساهمة

للمساهمة في المشروع:
1. Fork الريبو
2. أنشئ فرع جديد
3. قم بالتعديلات
4. أرسل Pull Request

## 📧 الدعم

للحصول على الدعم:
- افتح Issue على GitHub
- تواصل مع الفريق

---

**ملاحظة**: هذا المشروع يستخدم الفرع `port/update-2025-10-11`. تأكد من استخدام هذا الفرع عند الاستنساخ أو العمل على المشروع.

**تم التحديث**: نوفمبر 2025
