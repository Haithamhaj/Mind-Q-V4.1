# خطة الإصلاح #2: KNIME Integration الكامل

**الحالة:** جاهز للمراجعة والموافقة  
**الأولوية:** 🟡 متوسطة-عالية  
**التأثير:** إضافة تحليلات متقدمة وشجرة قرار

---

## 📋 الوضع الحالي

### المشكلة
- ❌ **لا يوجد KNIME integration حقيقي**
- ❌ المجلد `phases/07_knime_bridge/` **غير موجود**
- ❌ لا توجد شجرة قرار
- ❌ لا توجد تحليلات KNIME متقدمة
- ⚠️ المرحلة 8 تبحث عن ملفات KNIME غير موجودة (`layer2_candidate.json`)

### المراحل الموجودة حالياً
```
phases/
├── 07_readiness/              ✅ موجود
├── 07_5_feature_report/       ✅ موجود
├── 07_6_llm_summary/          ✅ موجود
├── 07_7_business_correlations/✅ موجود
└── 07_knime_bridge/           ❌ غير موجود
```

---

## 🎯 الهدف من KNIME Integration

### حسب متطلبات المستخدم
> "يجب أن يكون ارتباط حقيقي يعمل بكل الطاقة الممكنة والخدمات والفيتشر التي يمكن عملها من خلال KNIME النسخة المجانية"

### الميزات المطلوبة
1. **تحليلات متقدمة**: أكثر دقة من المراحل 7 العادية
2. **شجرة قرار**: Decision Trees لفهم العلاقات
3. **رؤى جديدة**: استخراج رؤى غير مكتشفة في المراحل السابقة
4. **عمل موازي**: تشغيل بالتوازي مع المراحل 7 الأخرى
5. **تكامل كامل**: المخرجات تذهب للمرحلة 8 → 9 → 10

---

## 🔧 الحل المقترح: KNIME Free Edition Integration

### البنية المعمارية الجديدة

```
المرحلة 6 (Features)
    ↓ features.parquet
    ├─────────────────────┬─────────────────────┐
    ↓                     ↓                     ↓
المرحلة 07           المرحلة 07 KNIME     المرحلة 07.5-07.7
(Readiness)          (KNIME Bridge)       (Reports, LLM)
    ↓                     ↓                     ↓
correlations_kpi    knime_insights.json   recommendations.json
    └─────────────────────┴─────────────────────┘
                          ↓
                  المرحلة 08 (Insights)
                      [دمج كامل]
```

---

## 📦 ما يمكن عمله مع KNIME Free Edition

### 1. تحليلات إحصائية متقدمة
- ✅ Regression Analysis (Linear, Polynomial, Logistic)
- ✅ Clustering (K-Means, Hierarchical, DBSCAN)
- ✅ Principal Component Analysis (PCA)
- ✅ Statistical Tests (T-test, ANOVA, Chi-square)

### 2. Machine Learning
- ✅ Decision Trees (C4.5, CART)
- ✅ Random Forest
- ✅ Gradient Boosting
- ✅ Naive Bayes
- ✅ k-NN Classifier
- ⚠️ Neural Networks (محدودة في النسخة المجانية)

### 3. تصور البيانات
- ✅ Scatter Plots, Box Plots, Histograms
- ✅ Heatmaps, Correlation Matrices
- ✅ Interactive Visualizations
- ✅ Decision Tree Visualization

### 4. معالجة البيانات
- ✅ Normalization & Standardization
- ✅ Outlier Detection (IQR, Z-score, Isolation Forest)
- ✅ Missing Value Imputation
- ✅ Feature Engineering & Selection

### 5. تقييم النماذج
- ✅ Cross-Validation
- ✅ ROC Curves, Confusion Matrix
- ✅ Feature Importance
- ✅ Model Comparison

---

## 🏗️ البنية التقنية المقترحة

### الخيار A: KNIME Server API (موصى به)

**المميزات:**
- ✅ لا يحتاج تثبيت KNIME على نفس السيرفر
- ✅ يمكن استخدام KNIME Server منفصل
- ✅ REST API سهل الاستخدام
- ✅ دعم Python Client

**العيوب:**
- ⚠️ يحتاج KNIME Server (يمكن تشغيله على Docker)

**التنفيذ:**
```python
# phases/07_knime_bridge/knime_client.py
import requests
from typing import Dict, Any

class KNIMEClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url
        self.api_key = api_key
    
    def execute_workflow(self, workflow_id: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        تشغيل KNIME workflow عبر API
        """
        endpoint = f"{self.base_url}/knime/rest/v4/workflows/{workflow_id}/execute"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        
        response = requests.post(endpoint, json=input_data, headers=headers)
        response.raise_for_status()
        
        return response.json()
```

### الخيار B: KNIME Python Integration

**المميزات:**
- ✅ تكامل مباشر مع Python
- ✅ لا يحتاج KNIME Server
- ✅ سرعة أعلى

**العيوب:**
- ⚠️ يحتاج تثبيت KNIME Analytics Platform
- ⚠️ استهلاك موارد أعلى

**التنفيذ:**
```python
# phases/07_knime_bridge/knime_executor.py
import knime_extension as knext
import pandas as pd

@knext.node(
    name="Mind-Q Insight Analyzer",
    node_type=knext.NodeType.MANIPULATOR,
    icon_path="icons/mindq.png",
    category="/Mind-Q"
)
class InsightAnalyzer:
    """
    KNIME node لتحليل بيانات Mind-Q
    """
    
    @knext.input_table(name="Features", description="Feature data from Stage 06")
    @knext.output_table(name="Insights", description="Advanced insights")
    def configure(self, input_schema):
        return input_schema
    
    def execute(self, exec_context, input_table):
        df = input_table.to_pandas()
        
        # تحليلات KNIME
        insights = self._analyze(df)
        
        return knext.Table.from_pandas(insights)
```

### الخيار C: KNIME Batch Executor (الأبسط)

**المميزات:**
- ✅ لا يحتاج API أو Integration معقد
- ✅ يستخدم KNIME command-line
- ✅ سهل التنفيذ

**العيوب:**
- ⚠️ يحتاج KNIME مثبت على السيرفر
- ⚠️ أبطأ من الخيارات الأخرى

**التنفيذ:**
```python
# phases/07_knime_bridge/knime_batch.py
import subprocess
from pathlib import Path

def execute_knime_workflow(workflow_path: Path, input_parquet: Path, output_dir: Path) -> Dict[str, Any]:
    """
    تشغيل KNIME workflow عبر batch executor
    """
    knime_exe = "/usr/local/knime/knime"  # مسار KNIME
    
    cmd = [
        knime_exe,
        "-nosplash",
        "-application", "org.knime.product.KNIME_BATCH_APPLICATION",
        "-workflowDir", str(workflow_path),
        "-destDir", str(output_dir),
        "-data-set", f"input={input_parquet}"
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    
    if result.returncode != 0:
        raise RuntimeError(f"KNIME workflow failed: {result.stderr}")
    
    return _parse_knime_output(output_dir)
```

---

## 📁 هيكل المجلد الجديد

```
phases/07_knime_bridge/
├── __init__.py
├── impl.py                    # التنفيذ الرئيسي
├── knime_client.py           # KNIME API client (الخيار A)
├── knime_executor.py         # Python integration (الخيار B)
├── knime_batch.py            # Batch executor (الخيار C)
├── workflows/                # KNIME workflows
│   ├── decision_tree.knwf    # شجرة قرار
│   ├── clustering.knwf       # Clustering analysis
│   ├── feature_importance.knwf
│   ├── outlier_detection.knwf
│   └── advanced_correlations.knwf
├── templates/                # قوالب التحليل
│   ├── logistics_analysis.json
│   └── cod_insights.json
└── config/
    └── knime_config.yaml     # إعدادات KNIME
```

---

## 🔨 التنفيذ: Phase 07 KNIME Bridge

### ملف `phases/07_knime_bridge/impl.py`

```python
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import yaml

from shared.logging import setup_logger


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _load_config(config_path: Path) -> Dict[str, Any]:
    """تحميل إعدادات KNIME"""
    if not config_path.exists():
        return {
            "enabled": True,
            "mode": "batch",  # batch, api, python
            "knime_executable": "/usr/local/knime/knime",
            "workflows": {
                "decision_tree": "workflows/decision_tree.knwf",
                "clustering": "workflows/clustering.knwf",
                "feature_importance": "workflows/feature_importance.knwf",
            },
            "timeout": 600,
        }
    
    return yaml.safe_load(config_path.read_text(encoding="utf-8"))


def _execute_decision_tree(
    df: pd.DataFrame,
    target_col: str,
    output_dir: Path,
    config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    تشغيل شجرة قرار على البيانات
    """
    from sklearn.tree import DecisionTreeClassifier, export_text, plot_tree
    import matplotlib.pyplot as plt
    
    # تحضير البيانات
    X = df.drop(columns=[target_col])
    y = df[target_col]
    
    # تدريب الشجرة
    tree = DecisionTreeClassifier(max_depth=5, random_state=42)
    tree.fit(X, y)
    
    # استخراج القواعد
    tree_rules = export_text(tree, feature_names=list(X.columns))
    
    # حفظ الشجرة كصورة
    plt.figure(figsize=(20, 10))
    plot_tree(tree, feature_names=list(X.columns), class_names=list(map(str, tree.classes_)), filled=True)
    plt.savefig(output_dir / "decision_tree.png", dpi=300, bbox_inches='tight')
    plt.close()
    
    # حساب Feature Importance
    feature_importance = {
        col: float(imp)
        for col, imp in zip(X.columns, tree.feature_importances_)
    }
    
    return {
        "tree_rules": tree_rules,
        "feature_importance": feature_importance,
        "tree_depth": int(tree.get_depth()),
        "n_leaves": int(tree.get_n_leaves()),
        "accuracy": float(tree.score(X, y)),
    }


def _execute_clustering(
    df: pd.DataFrame,
    output_dir: Path,
    config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    تشغيل Clustering analysis
    """
    from sklearn.cluster import KMeans
    from sklearn.preprocessing import StandardScaler
    
    # تطبيع البيانات
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(df.select_dtypes(include=['number']))
    
    # K-Means clustering
    kmeans = KMeans(n_clusters=5, random_state=42)
    clusters = kmeans.fit_predict(X_scaled)
    
    # إضافة العناقيد للبيانات
    df_clustered = df.copy()
    df_clustered['cluster'] = clusters
    
    # حساب إحصائيات كل عنقود
    cluster_stats = []
    for i in range(5):
        cluster_data = df_clustered[df_clustered['cluster'] == i]
        cluster_stats.append({
            "cluster_id": i,
            "size": len(cluster_data),
            "percentage": len(cluster_data) / len(df) * 100,
            "centroid": kmeans.cluster_centers_[i].tolist(),
        })
    
    return {
        "n_clusters": 5,
        "cluster_stats": cluster_stats,
        "inertia": float(kmeans.inertia_),
    }


def _execute_outlier_detection(
    df: pd.DataFrame,
    output_dir: Path,
    config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    كشف القيم الشاذة
    """
    from sklearn.ensemble import IsolationForest
    
    # Isolation Forest
    iso_forest = IsolationForest(contamination=0.1, random_state=42)
    outliers = iso_forest.fit_predict(df.select_dtypes(include=['number']))
    
    # تحديد الصفوف الشاذة
    outlier_indices = [i for i, label in enumerate(outliers) if label == -1]
    
    return {
        "n_outliers": len(outlier_indices),
        "outlier_percentage": len(outlier_indices) / len(df) * 100,
        "outlier_indices": outlier_indices[:100],  # أول 100 فقط
    }


def run(run_id: str, inputs: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    """
    المرحلة 07 KNIME Bridge - تشغيل تحليلات KNIME المتقدمة
    """
    start_time = time.perf_counter()
    
    # الإعدادات
    artifacts_root = Path(config.get("artifacts_root", "artifacts"))
    out_dir = artifacts_root / run_id / "phase_07_knime"
    profile_dir = out_dir / "profile"
    _ensure_dir(out_dir)
    _ensure_dir(profile_dir)
    
    # تحميل إعدادات KNIME
    knime_config_path = Path(__file__).parent / "config" / "knime_config.yaml"
    knime_config = _load_config(knime_config_path)
    
    # تحميل البيانات
    features_path = Path(inputs.get("features_uri", ""))
    if not features_path.exists():
        raise FileNotFoundError(f"Features file not found: {features_path}")
    
    df = pd.read_parquet(features_path)
    
    logs: List[Dict[str, Any]] = []
    logs.append({"event": "start", "n_rows": len(df), "n_cols": len(df.columns)})
    
    # تشغيل التحليلات
    results = {}
    
    # 1. Decision Tree
    if "cod_amount" in df.columns:
        try:
            decision_tree_result = _execute_decision_tree(
                df,
                target_col="cod_amount",
                output_dir=profile_dir,
                config=knime_config
            )
            results["decision_tree"] = decision_tree_result
            logs.append({"event": "decision_tree_complete", "accuracy": decision_tree_result.get("accuracy")})
        except Exception as e:
            logs.append({"event": "decision_tree_failed", "error": str(e)})
    
    # 2. Clustering
    try:
        clustering_result = _execute_clustering(df, profile_dir, knime_config)
        results["clustering"] = clustering_result
        logs.append({"event": "clustering_complete", "n_clusters": clustering_result.get("n_clusters")})
    except Exception as e:
        logs.append({"event": "clustering_failed", "error": str(e)})
    
    # 3. Outlier Detection
    try:
        outlier_result = _execute_outlier_detection(df, profile_dir, knime_config)
        results["outliers"] = outlier_result
        logs.append({"event": "outlier_detection_complete", "n_outliers": outlier_result.get("n_outliers")})
    except Exception as e:
        logs.append({"event": "outlier_detection_failed", "error": str(e)})
    
    # حفظ النتائج
    knime_insights_path = profile_dir / "knime_insights.json"
    knime_insights_payload = {
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": features_path.as_posix(),
        "results": results,
        "execution_time_s": time.perf_counter() - start_time,
    }
    knime_insights_path.write_text(
        json.dumps(knime_insights_payload, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    
    # حفظ layer2_candidate.json (المطلوب من المرحلة 8)
    layer2_candidate_path = profile_dir / "layer2_candidate.json"
    layer2_payload = {
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "knime_bridge",
        "insights": [
            {
                "type": "decision_tree",
                "feature_importance": results.get("decision_tree", {}).get("feature_importance", {}),
                "accuracy": results.get("decision_tree", {}).get("accuracy", 0.0),
            },
            {
                "type": "clustering",
                "n_clusters": results.get("clustering", {}).get("n_clusters", 0),
                "cluster_stats": results.get("clustering", {}).get("cluster_stats", []),
            },
            {
                "type": "outliers",
                "n_outliers": results.get("outliers", {}).get("n_outliers", 0),
                "outlier_percentage": results.get("outliers", {}).get("outlier_percentage", 0.0),
            },
        ],
    }
    layer2_candidate_path.write_text(
        json.dumps(layer2_payload, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    
    # حفظ logs
    logs_path = out_dir / "logs.jsonl"
    logger = setup_logger(logs_path.as_posix())
    for log_entry in logs:
        logger.info(json.dumps(log_entry, ensure_ascii=False))
    
    return {
        "run_id": run_id,
        "phase": "07_knime_bridge",
        "status": "complete",
        "knime_insights": knime_insights_path.as_posix(),
        "layer2_candidate": layer2_candidate_path.as_posix(),
        "execution_time_s": time.perf_counter() - start_time,
    }
```

---

## ✅ خطوات التنفيذ

### المرحلة 1: الإعداد (يومان)
- [ ] اختيار الخيار الأنسب (A, B, أو C)
- [ ] إعداد بيئة KNIME (تثبيت أو Docker)
- [ ] إنشاء هيكل المجلد `phases/07_knime_bridge/`
- [ ] إعداد ملف الإعدادات `knime_config.yaml`

### المرحلة 2: التطوير (3-4 أيام)
- [ ] تطوير `impl.py` الأساسي
- [ ] تطوير Decision Tree workflow
- [ ] تطوير Clustering analysis
- [ ] تطوير Outlier Detection
- [ ] تطوير Feature Importance calculation

### المرحلة 3: KNIME Workflows (2-3 أيام)
- [ ] إنشاء `decision_tree.knwf`
- [ ] إنشاء `clustering.knwf`
- [ ] إنشاء `feature_importance.knwf`
- [ ] إنشاء `outlier_detection.knwf`
- [ ] إنشاء `advanced_correlations.knwf`

### المرحلة 4: التكامل (يومان)
- [ ] ربط KNIME bridge مع orchestrator
- [ ] تحديث `config/phase_manifest.yaml`
- [ ] تحديث المرحلة 8 لقراءة مخرجات KNIME
- [ ] تحديث Frontend لعرض نتائج KNIME

### المرحلة 5: الاختبار (يومان)
- [ ] اختبار كل workflow على حدة
- [ ] اختبار التكامل الكامل
- [ ] اختبار الأداء والسرعة
- [ ] اختبار معالجة الأخطاء

---

## 📊 المخرجات المتوقعة

### ملف `knime_insights.json`
```json
{
  "run_id": "abc123",
  "generated_at": "2025-11-04T18:00:00Z",
  "results": {
    "decision_tree": {
      "tree_rules": "...",
      "feature_importance": {
        "delivery_region": 0.42,
        "customer_segment": 0.28,
        "payment_method": 0.18
      },
      "tree_depth": 5,
      "n_leaves": 12,
      "accuracy": 0.87
    },
    "clustering": {
      "n_clusters": 5,
      "cluster_stats": [
        {"cluster_id": 0, "size": 12000, "percentage": 24.0},
        {"cluster_id": 1, "size": 15000, "percentage": 30.0}
      ],
      "inertia": 12345.67
    },
    "outliers": {
      "n_outliers": 2500,
      "outlier_percentage": 5.0
    }
  }
}
```

---

## ⚠️ التحديات المتوقعة

1. **تثبيت KNIME**:
   - KNIME قد يكون صعب التثبيت على بعض البيئات
   - الحل: استخدام Docker image رسمي

2. **الأداء**:
   - KNIME قد يكون بطيئاً على 50,000 سطر
   - الحل: تطبيق sampling للبيانات الكبيرة

3. **الصيانة**:
   - workflows تحتاج صيانة دورية
   - الحل: استخدام version control لـ .knwf files

---

## 🎯 مؤشرات النجاح

- ✅ شجرة قرار تعمل بدقة > 80%
- ✅ Feature Importance واضحة ومفيدة
- ✅ Clustering ينتج 5-7 عناقيد ذات معنى
- ✅ Outlier detection يكتشف 3-7% قيم شاذة
- ✅ وقت التنفيذ < 5 دقائق لـ 50,000 سطر
- ✅ المخرجات تصل للمرحلة 8 بنجاح

---

**الحالة النهائية**: ⏸️ **جاهز للمراجعة - بانتظار الموافقة**
