#!/usr/bin/env python3
import sys
import os
from pathlib import Path

# Add project root and backend directory to Python path
project_root = Path(__file__).parent
backend_dir = project_root / "backend"
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(backend_dir))

# Set working directory to project root
os.chdir(project_root)

if __name__ == "__main__":
    import uvicorn
    
    # Import the app directly
    from backend.src.app.services.pipeline_api.app import app
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=9000,
        reload=True
    )