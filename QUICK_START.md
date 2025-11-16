# Mind-Q V4.1 - البداية السريعة

## ⚠️ أهم شي: المسار الصحيح

**قبل أي شي، تأكد إنك في مجلد المشروع:**
```bash
cd /Users/haitham/development/Mind-Q-V4.1-port
```

---

## 🚀 التشغيل (3 خطوات بس)

### 1️⃣ Backend
```bash
./start_backend.sh
```
✅ Backend يشتغل على: http://localhost:9000

### 2️⃣ Frontend (في terminal جديد)
```bash
./start_frontend.sh
```
✅ Frontend يشتغل على: http://localhost:3000

### 3️⃣ Pipeline (في terminal جديد)
```bash
./run_pipeline.sh test-run data/sample.csv
```

---

## 🔧 ليش السكربتات؟

السكربتات تضبط `PYTHONPATH` تلقائياً عشان Python يلاقي مجلد `phases/`:
```bash
export PYTHONPATH=/Users/haitham/development/Mind-Q-V4.1-port:$PYTHONPATH
```

بدون هذا، راح تطلع رسالة خطأ:
```
❌ No module named 'phases.01_ingestion'
```

---

## 📝 تشغيل أوامر يدوية؟

لو بدك تشغل أي سكربت Python يدوي:

```bash
# خطوة 1: روح للمجلد الرئيسي
cd /Users/haitham/development/Mind-Q-V4.1-port

# خطوة 2: اضبط PYTHONPATH
export PYTHONPATH=/Users/haitham/development/Mind-Q-V4.1-port:$PYTHONPATH

# خطوة 3: شغّل السكربت
python3 your_script.py
```

---

## 💡 نصائح

✅ **استخدم السكربتات دائماً** - تضبط كل شي تلقائياً  
✅ **شغّل من الجذر** - `/Users/haitham/development/Mind-Q-V4.1-port`  
✅ **terminal منفصل لكل خدمة** - Backend, Frontend, Pipeline  

❌ **لا تشغل من `backend/` مباشرة** - ما راح يلاقي `phases/`  
❌ **لا تنسى `export PYTHONPATH`** - لو شغلت يدوي  

---

## 🆘 حل المشاكل السريع

### الخطأ: `No module named 'phases.01_ingestion'`
```bash
# الحل: استخدم السكربتات أو اضبط PYTHONPATH
cd /Users/haitham/development/Mind-Q-V4.1-port
export PYTHONPATH=$PWD:$PYTHONPATH
```

### الخطأ: `Address already in use`
```bash
# Backend
lsof -ti:9000 | xargs kill -9

# Frontend
lsof -ti:3000 | xargs kill -9
```

---

**للتفاصيل الكاملة، شوف:** [STARTUP.md](./STARTUP.md)
