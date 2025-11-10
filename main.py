#!/usr/bin/env python3
"""
Mind-Q V4 FastAPI Application Entry Point
"""
import sys
from pathlib import Path

# Add the backend directory to Python path
backend_dir = Path(__file__).parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

# Import the FastAPI app for uvicorn to access without reaching into backend internals
from src.app.services.pipeline_api import app

if __name__ == "__main__":
    import uvicorn
    import sys
    # Allow port override from command line
    port = 9000
    if len(sys.argv) > 1 and sys.argv[1].startswith('--port='):
        port = int(sys.argv[1].split('=')[1])
    # Use reload=False to avoid the import string requirement
    uvicorn.run(app, host="0.0.0.0", port=port, reload=False)
