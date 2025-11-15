# 🚀 دليل استخدام Mind-Q Analytics على Google Colab

## ملخص سريع
هذا النوتبوك **يحول عمليات KNIME المعقدة إلى كود Python عملي وسريع** على Google Colab بدون الحاجة لتثبيت أي شيء محلياً!

---

## 🎯 المميزات

### ✅ **Insights Generation**
- تحليل توزيعات البيانات
- حساب الارتباطات (Correlations)
- الكشف عن القيم الشاذة (Outliers)
- تصور بياني تفاعلي (Plotly)

### ✅ **Clustering**
- **KMeans**: اختيار تلقائي لأفضل K
- **DBSCAN**: تجميع كثافة محسّن
- **Hierarchical Clustering**: تجميع هرمي
- **Elbow و Silhouette Methods**: لاختيار أفضل عدد عناقيد

### ✅ **Recommendations**
- توصيات مخصصة لكل عنقود
- تقييم الأداء وتحديد نقاط الضعف
- أولويات واضحة (Critical, High, Medium)

### ✅ **Predictions**
- **Classification**: التنبؤ بـ SLA Compliance
- **Regression**: التنبؤ بوقت التسليم
- **نماذج متعددة**: Logistic, Random Forest, XGBoost
- **مقاييس شاملة**: Accuracy, Precision, Recall, F1, R²

### ✅ **Explainability**
- **SHAP**: شرح تأثير كل ميزة
- **Feature Importance**: أهم الميزات
- **رسوم بيانية تفاعلية**: سهولة الفهم

---

## 🚀 كيفية الاستخدام

### الخطوة 1: فتح النوتبوك على Colab
```bash
# انسخ الرابط:
https://colab.research.google.com/github/Haithamhaj/Mind-Q-V4.1/blob/main/Mind_Q_Analytics_Colab.ipynb
```

### الخطوة 2: إعداد البيانات

#### الخيار A: من Google Drive
```python
# في Cell 2, غيّر المسار:
data_path = "/content/drive/MyDrive/Mind-Q/logistics_data.csv"
```

#### الخيار B: رفع ملف مباشرة
```python
from google.colab import files
uploaded = files.upload()
df = pd.read_csv(list(uploaded.keys())[0])
```

#### الخيار C: استخدام بيانات تجريبية
سيتم توليد بيانات تجريبية تلقائياً إذا لم يكن الملف موجوداً.

### الخطوة 3: تشغيل الخلايا بالترتيب
1. **Cell 1**: استيراد المكتبات
2. **Cell 2**: تحميل البيانات
3. **Cell 3**: توليد Insights
4. **Cell 4**: رسوم بيانية
5. **Cell 5**: معالجة البيانات
6. **Cell 6**: تقليل الأبعاد
7. **Cell 7**: التجميع (Clustering)
8. **Cell 8**: نظام التوصيات
9. **Cell 9**: التنبؤات
10. **Cell 10**: تفسير النتائج (SHAP)
11. **Cell 11**: حفظ النتائج

---

## 📊 مثال على البيانات المتوقعة

### يجب أن يحتوي CSV على:

```csv
order_id,delivery_time_hours,distance_km,cod_amount,carrier,region,sla_achieved,customer_rating,num_attempts,weather
1,24.5,50.2,500,Carrier_A,North,1,5,1,Sunny
2,48.3,75.1,1500,Carrier_B,South,0,3,2,Rainy
3,36.1,45.8,300,Carrier_C,East,1,4,1,Cloudy
...
```

### الأعمدة المهمة:
- `delivery_time_hours`: وقت التسليم (للانحدار)
- `sla_achieved`: الامتثال للـ SLA (للتصنيف)
- `distance_km`: المسافة (ميزة)
- `customer_rating`: تقييم العميل (للتوصيات)
- `carrier`: شركة النقل (فئة)
- `region`: المنطقة (فئة)

---

## 🔧 التخصيص والضبط

### تغيير عدد العناقيد
```python
# في Cell 7, غيّر K_range:
K_range = range(2, 15)  # بحث عن 2-14 عناقيد
```

### تغيير نماذج التنبؤ
```python
# في Cell 9, أضف نماذج جديدة:
models = {
    'SVM': SVC(kernel='rbf'),
    'KNN': KNeighborsClassifier(n_neighbors=5),
}
```

### تغيير عدد العينات للـ SHAP
```python
# في Cell 10, غيّر 100 إلى رقم آخر:
shap_values = explainer.shap_values(X_test_scaled[:200])
```

---

## 📁 المخرجات المحفوظة

كل شيء يتم حفظه في `outputs/`:

```
outputs/
├── best_model_*.joblib          # النموذج المدرب
├── kmeans_model.joblib          # نموذج KMeans
├── scaler.joblib                # المقياس
├── processed_data.parquet       # البيانات المعالجة
├── analysis_results.json        # النتائج (Insights, Recommendations)
└── analysis_report.md           # تقرير نصي
```

---

## ⚡ نصائح للأداء

### لتسريع التنفيذ:
1. استخدم عينة من البيانات في البداية
2. قلل عدد العناقيد المختبرة
3. قلل عدد التكرارات في t-SNE

### مثال:
```python
# في البداية, استخدم عينة:
df = df.sample(n=10000, random_state=42)
```

---

## 🐛 استكشاف الأخطاء

### خطأ: `ModuleNotFoundError: No module named 'umap'`
**الحل**: UMAP اختياري، سيعمل النوتبوك بدونه

### خطأ: `MemoryError`
**الحل**: استخدم عينة أصغر من البيانات

### خطأ: `File not found`
**الحل**: تأكد من المسار الصحيح في Cell 2

---

## 🔗 الربط مع Mind-Q الرئيسي

لاستخدام هذه النتائج في نظام Mind-Q الرئيسي:

```python
# استخدم المخرجات المحفوظة:
import joblib
import json

# تحميل النموذج
model = joblib.load('best_model_Random_Forest.joblib')
scaler = joblib.load('scaler.joblib')

# تحميل النتائج
with open('analysis_results.json', 'r') as f:
    results = json.load(f)

# استخدام النموذج للتنبؤ
new_data_scaled = scaler.transform(new_data)
predictions = model.predict(new_data_scaled)
```

---

## 📞 الدعم والأسئلة

- 📧 للمزيد من المعلومات: راجع [PHASES_DETAILED_GUIDE.md](./docs/PHASES_DETAILED_GUIDE.md)
- 📚 معلومات عن Mind-Q: راجع [README.md](./README.md)

---

## 📝 الترخيص

هذا النوتبوك جزء من مشروع Mind-Q V4.1

**تم الإنشاء**: نوفمبر 2025
**الإصدار**: 1.0
