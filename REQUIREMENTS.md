# Mind-Q V4.1 Requirements & Dependencies
## متطلبات وتبعيات نظام Mind-Q V4.1

### 📋 Overview / نظرة عامة

This document details all dependencies and requirements for the Mind-Q V4.1 Logistics Intelligence Pipeline, including the new AI and advanced analytics capabilities discovered during the comprehensive documentation update.

يحدد هذا المستند جميع التبعيات والمتطلبات لخط أنابيب Mind-Q V4.1 للذكاء اللوجستي، بما في ذلك قدرات الذكاء الاصطناعي والتحليلات المتقدمة الجديدة التي تم اكتشافها أثناء التحديث الشامل للتوثيق.

---

## 🔧 Core Dependencies / التبعيات الأساسية

### Data Processing Engine / محرك معالجة البيانات
- **Polars (≥0.20.0)**: High-performance DataFrame library for large-scale data processing
- **Pandas (≥2.0.0)**: Fallback processing engine for compatibility
- **PyArrow (≥14.0.0)**: Columnar data format and processing
- **NumPy (≥1.24.0)**: Numerical computing foundation
- **SciPy (≥1.10.0)**: Scientific computing algorithms

### Machine Learning & Statistics / التعلم الآلي والإحصاء
- **Scikit-learn (≥1.3.0)**: Machine learning algorithms for imputation and analysis
- **Statsmodels (≥0.14.0)**: Statistical modeling for correlation analysis
- **DuckDB (≥0.9.0)**: In-process analytical database for complex queries

### Data Quality & Validation / جودة البيانات والتحقق
- **Pydantic (≥2.0.0)**: Data validation and serialization
- **Great Expectations (≥0.18.0)**: Data quality expectations framework
- **YData Profiling (≥4.0.0)**: Automated data profiling and quality reports

---

## 🤖 AI & LLM Integration / تكامل الذكاء الاصطناعي

### Multi-Provider LLM Support / دعم متعدد المزودين للذكاء الاصطناعي
- **OpenAI (≥1.40.0)**: GPT models for business intelligence generation
- **Anthropic (≥0.25.0)**: Claude models for advanced reasoning
- **Google GenerativeAI (≥0.5.0)**: Gemini models for cost-effective processing
- **Tiktoken (≥0.6.0)**: Token counting and cost optimization

### AI Features Enabled / الميزات المتاحة للذكاء الاصطناعي
- ✅ **Arabic Business Reporting**: Native Arabic executive summaries
- ✅ **Cost Optimization**: Multi-provider cost comparison and selection
- ✅ **Structured Output**: Pydantic validation for AI responses
- ✅ **PII Protection**: Automatic masking in AI prompts

---

## 🌐 Web & API Framework / إطار العمل للويب والـ API

### Backend Services / خدمات الخلفية
- **FastAPI (≥0.115.0)**: Modern Python web framework for APIs
- **Uvicorn (≥0.30.0)**: ASGI server for production deployment
- **HTTPx (≥0.27.0)**: HTTP client for external service integration
- **Requests (≥2.31.0)**: HTTP library for compatibility

### Configuration & Environment / التكوين والبيئة
- **Python-dotenv (≥1.0.0)**: Environment variable management
- **PyYAML (≥6.0.1)**: YAML configuration file processing

---

## 📊 Advanced Analytics Features / ميزات التحليلات المتقدمة

### Statistical Analysis / التحليل الإحصائي
- **Correlation Analysis**: Pearson and Spearman correlation with leakage detection
- **Outlier Detection**: IQR-based outlier identification and handling
- **Time Series Analysis**: Temporal pattern detection and validation
- **Population Stability Index**: PSI monitoring for data drift detection

### Business Intelligence / ذكاء الأعمال
- **Semantic Marts**: Automated business-ready data marts generation
- **KPI Alignment**: Automatic alignment with logistics KPIs
- **Multi-Currency Support**: International logistics operations support
- **Executive Dashboards**: Ready-to-use dashboard components

---

## 🔧 Development & Quality Tools / أدوات التطوير والجودة

### Testing Framework / إطار الاختبار
- **Pytest (≥7.4.0)**: Main testing framework
- **Pytest-asyncio (≥0.21.0)**: Async testing support
- **Pytest-cov (≥4.1.0)**: Code coverage analysis
- **Pytest-mock (≥3.11.0)**: Mocking utilities

### Code Quality / جودة الكود
- **MyPy (≥1.5.0)**: Static type checking
- **Ruff (≥0.0.290)**: Fast Python linter and formatter
- **Black (≥23.7.0)**: Code formatting
- **isort (≥5.12.0)**: Import sorting
- **Pre-commit (≥3.3.0)**: Git hooks for quality assurance

### Security & Performance / الأمان والأداء
- **Bandit (≥1.7.0)**: Security vulnerability scanning
- **Safety (≥2.3.0)**: Dependency vulnerability checking
- **Memory-profiler (≥0.61.0)**: Memory usage profiling
- **Line-profiler (≥4.0.0)**: Performance profiling

---

## 🚀 Installation Guide / دليل التثبيت

### 1. Environment Setup / إعداد البيئة

```bash
# Create virtual environment
python -m venv .venv

# Activate environment (Windows)
.\.venv\Scripts\Activate.ps1

# Activate environment (Linux/Mac)
source .venv/bin/activate
```

### 2. Core Dependencies / التبعيات الأساسية

```bash
# Install core requirements
pip install -r requirements.txt

# Install development dependencies
pip install -r requirements-dev.txt
```

### 3. Alternative: Poetry Installation / التثبيت البديل: Poetry

```bash
# Install Poetry (if not already installed)
curl -sSL https://install.python-poetry.org | python3 -

# Install all dependencies
poetry install

# Install with development dependencies
poetry install --with dev
```

### 4. Environment Configuration / تكوين البيئة

```bash
# Copy environment template
cp .env.example .env

# Edit environment variables
# أضف مفاتيح API الخاصة بك
# OPENAI_API_KEY=sk-your-key-here
# ANTHROPIC_API_KEY=sk-ant-your-key-here
# GOOGLE_API_KEY=your-google-key-here
```

---

## 📈 Performance Requirements / متطلبات الأداء

### System Requirements / متطلبات النظام
- **Python**: 3.11 or higher
- **RAM**: 8GB minimum, 16GB recommended for large datasets
- **Storage**: 50GB free space for artifacts and processing
- **CPU**: Multi-core processor (4+ cores recommended)

### Large Dataset Optimization / تحسين البيانات الكبيرة
- **Polars Streaming**: Enabled for datasets >100K rows
- **Sampling Strategy**: Automatic sampling for >300 features
- **Memory Management**: Lazy evaluation and chunked processing
- **DuckDB Integration**: Complex analytical queries offloaded to DuckDB

---

## 🔐 Security Considerations / اعتبارات الأمان

### API Key Management / إدارة مفاتيح API
- Store API keys in environment variables only
- Never commit API keys to version control
- Use different keys for development and production
- Monitor API usage and costs regularly

### Data Protection / حماية البيانات
- Automatic PII detection and masking
- Phone number and email pattern recognition
- Secure handling of sensitive logistics data
- Audit trails for all data processing operations

---

## 🌍 Regional Features / الميزات الإقليمية

### Arabic Language Support / دعم اللغة العربية
- Native Arabic business reports generation
- Logistics domain terminology in Arabic
- Right-to-left text formatting support
- Cultural context for Middle East logistics

### International Operations / العمليات الدولية
- Multi-currency support (SAR, USD, EUR, etc.)
- Timezone-aware processing
- Regional KPI definitions
- Localized business rules

---

## 📚 Additional Resources / موارد إضافية

### Documentation / التوثيق
- **API Documentation**: Auto-generated with FastAPI
- **Code Documentation**: Comprehensive docstrings and type hints
- **Business Documentation**: Arabic and English business guides

### Support / الدعم
- **Issue Tracking**: GitHub Issues for bug reports and feature requests
- **Development Guides**: Comprehensive developer documentation
- **Best Practices**: Performance and security recommendations

---

*Last Updated: October 15, 2025 - Complete Requirements Audit*
*آخر تحديث: 15 أكتوبر 2025 - مراجعة شاملة للمتطلبات*