# 🚀 Mind-Q على Replit - دليل سريع

## ⚡ البدء السريع

### 1️⃣ استيراد المشروع على Replit

1. اذهب إلى: https://replit.com
2. انقر **Create Repl** → **Import from GitHub**
3. الصق الرابط:
   ```
   https://github.com/Haithamhaj/Mind-Q-V4.1
   ```
4. اختر الفرع: `port/update-2025-10-11` ✅
5. انقر **Import from GitHub**

### 2️⃣ التشغيل

بعد الاستيراد، ببساطة اضغط على زر **Run** ▶️

أو في Terminal:
```bash
bash start.sh
```

### 3️⃣ الوصول إلى التطبيق

- **Backend API**: سيظهر في Webview أو على المنفذ 8000
- **API Docs**: `/docs` (Swagger UI)
- **Frontend**: سيظهر على المنفذ 3000

## 📋 ما يحدث تلقائياً

✅ تثبيت Python dependencies  
✅ تثبيت Node.js dependencies  
✅ تشغيل Backend (FastAPI)  
✅ تشغيل Frontend (Next.js)  

## 🔧 إعدادات إضافية

### متغيرات البيئة (Environment Variables)

في Replit، اذهب إلى **Secrets** (🔒) وأضف:

**للـ Backend:**
```
BACKEND_PORT=8000
DEBUG=True
```

**للـ Frontend:** (في `frontend/.env.local`)
```
NEXT_PUBLIC_API_URL=https://your-repl-name.your-username.repl.co
```

## 📊 الروابط المهمة

- **Repository**: https://github.com/Haithamhaj/Mind-Q-V4.1
- **الفرع**: `port/update-2025-10-11`
- **الرابط المباشر**: https://github.com/Haithamhaj/Mind-Q-V4.1/tree/port/update-2025-10-11

## 🆘 حل المشاكل

### Backend لا يعمل؟
```bash
python start_server.py
```

### Frontend لا يعمل؟
```bash
cd frontend
npm install
npm run dev
```

### إعادة تشغيل كل شيء؟
```bash
bash start.sh
```

## 📖 دليل كامل

راجع [REPLIT_SETUP.md](./REPLIT_SETUP.md) للتفاصيل الكاملة.

---

**نصيحة**: Replit قد يحتاج بضع دقائق لتثبيت جميع المكتبات في أول مرة! ☕
