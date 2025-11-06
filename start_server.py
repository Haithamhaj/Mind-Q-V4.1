#!/usr/bin/env python3
import sys
import os
from pathlib import Path

# Add backend directory to Python path (where src/ is located)
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

# Set working directory to backend
backend_dir = Path(__file__).parent
os.chdir(backend_dir)

if __name__ == "__main__":
    import uvicorn
    # Import after path setup
    from backend.src.app.services.pipeline_api.app import app

    uvicorn.run(app, host="0.0.0.0", port=9000, reload=False)