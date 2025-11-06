# دليل ربط LLM مع سياق SLA

يوضح هذا الدليل كيفية تفعيل التكامل بين خدمة الـ LLM (OpenAI/GPT) وسياق SLA الذي تبنيه مراحل Mind-Q، ابتداءً من تجهيز البيانات وحتى استهلاك الـ API في واجهة BI.

## 1. المتطلبات
- Python 3.11، الاعتمادات مضافة في `pyproject.toml` (`fastapi`, `uvicorn`, `openai`).
- مفتاح OpenAI صالح (`OPENAI_API_KEY`) ونموذج مناسب (`OPENAI_MODEL`، الافتراضي `gpt-4o-mini`).
- ملفات المرحلة 09 متاحة على الأقل (`sla_summary.json`, `validation_report.json`).

## 2. بناء السياق
1. شغّل سكربت ETL بعد اكتمال المرحلة 09:
   ```bash
   python scripts/build_sla_context.py --run-id fastcoo-final --artifacts-root artifacts
   ```
2. السجلات الناتجة تخزن في:
   - `artifacts/context/<run_id>/<run_id>_sla.jsonl` (مقاطع السياق)
   - `artifacts/context/<run_id>/<run_id>_manifest.json` (بيانات المصدر)
3. أعد تشغيل السكربت عند ظهور تشغيل جديد أو تحديث في نتائج المرحلة 09.

## 3. تشغيل واجهة الـ API
1. عيّن متغيرات البيئة:
   ```bash
   set OPENAI_API_KEY=sk-...
   set OPENAI_MODEL=gpt-4o-mini
   set SLA_CONTEXT_ROOT=artifacts/context
   ```
2. شغّل الخدمة:
   ```bash
   uvicorn app.services.sla_chat.app:app --host 0.0.0.0 --port 8080 --reload
   ```
3. اختبر صحة الخدمة:
   ```bash
   curl http://localhost:8080/healthz
   ```

## 4. استخدام واجهة الدردشة
- مثال لطلب POST:
  ```bash
  curl -X POST http://localhost:8080/v1/sla/chat ^
       -H "Content-Type: application/json" ^
       -d "{\"run_id\": \"fastcoo-final\", \"question\": \"ما حالة KPI التسليم في الوقت المحدد؟\"}"
  ```
- الاستجابة تتضمن:
  - `answer`: نص يشرح الحالة مدعوماً بالمعرفات `[run:sla:xxx]`.
  - `references`: أهم المقاطع المستخدمة، مع درجة التطابق والبيانات الوصفية.
  - `usage`: إحصائيات استهلاك الـ tokens أو رسائل الخطأ/التحذير.

## 5. التخزين والتحكم في الوصول
- سجلات المحادثة تحفظ في `artifacts/context/<run_id>/logs/chat_sessions.jsonl` وتشمل السؤال، الوقت، والمعرّفات المرجعية.
- نفّذ ضوابط وصول (Gateway أو VPN) لضمان عدم وصول العملاء إلا إلى تشغيلاتهم أو أحمالهم المصرح بها (`run_id`, `customer_id`).
- لتوسيع RAG يمكنك استبدال التخزين المحلي بقاعدة بيانات أو محرك بحث (DuckDB، Elasticsearch، Qdrant) مع الاحتفاظ بمخطط JSON نفسه.

## 6. التكامل مع واجهة BI
- أضف نموذج محادثة في واجهة العميل يستدعي `/v1/sla/chat`.
- اعرض المصادر (`references`) في الواجهة لتمكين المستخدم من فتح الملفات الأصلية (`sla_summary.json`، `validation_report.json`).
- فعّل تنبيه عند وجود `usage.error` للإشارة إلى انقطاع الـ LLM أو الحاجة إلى إعادة بناء السياق.

## 7. ممارسات موصى بها
- حدّد درجة حرارة منخفضة (`OPENAI_TEMPERATURE=0.2`) للحفاظ على الإجابات الواقعية.
- استخدم بثاً (stream) أو تقطيعاً للمحتوى إذا زادت أحجام ملفات SLA.
- أضف اختبارات تكامل للتأكد من أن إجابات الـ LLM تحتوي على المعرفات المطلوبة وأن القيم الرقمية تطابق المصدر.

باتباع الخطوات أعلاه ستحصل على مساعد SLA ذكي يعتمد على البيانات الحقيقية ويقدم سرداً تفاعلياً قابلاً للتدقيق لعملائك وفريق التشغيل.

