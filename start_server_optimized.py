#!/usr/bin/env python3
import sys
import os
from pathlib import Path
import warnings

# تجاهل التحذيرات المتعلقة بـ datetime parsing
warnings.filterwarnings("ignore", message="Could not infer format")
warnings.filterwarnings("ignore", message="Calling `map_elements` without specifying `return_dtype`")

# Add repository root to Python path so backend package is available
repo_root = Path(__file__).parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

# Set working directory to backend
backend_dir = Path(__file__).parent
os.chdir(backend_dir)

# تحسين إعدادات الذاكرة للـ Pipeline
os.environ["PYTHONUNBUFFERED"] = "1"
os.environ["OMP_NUM_THREADS"] = "4"
os.environ["MKL_NUM_THREADS"] = "4"

if __name__ == "__main__":
    import uvicorn
    # Import after path setup
    from backend.src.app.services.pipeline_api.app import app
    
    print("🚀 Starting Mind-Q Backend with optimized settings...")
    print("📊 Pipeline processing optimized for large datasets")
    print("🔧 Memory management enabled")
    print("═══════════════════════════════════════")
    
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=9000, 
        reload=False,
        log_level="info",
        timeout_keep_alive=300,  # 5 دقائق timeout
        limit_concurrency=10,    # حد أقصى للطلبات المتزامنة
        limit_max_requests=1000  # حد أقصى للطلبات
    )