#!/usr/bin/env python3
import atexit
import os
import signal
import sys
import warnings
from pathlib import Path
from types import FrameType

# Suppress noisy warnings from optional dependencies
warnings.filterwarnings("ignore", message="Could not infer format")
warnings.filterwarnings("ignore", message="Calling `map_elements` without specifying `return_dtype`")

# Ensure the repository root is discoverable on PYTHONPATH
repo_root = Path(__file__).resolve().parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

# Keep the process working directory anchored at the repo root
os.chdir(repo_root)

# Modest thread caps keep the stable profile predictable
os.environ["PYTHONUNBUFFERED"] = "1"
os.environ["OMP_NUM_THREADS"] = "2"
os.environ["MKL_NUM_THREADS"] = "2"
os.environ["POLARS_MAX_THREADS"] = "2"

def cleanup_handler(signum: int | None = None, frame: FrameType | None = None) -> None:
    print("Server cleanup initiated...")


def register_cleanup() -> None:
    signal.signal(signal.SIGINT, cleanup_handler)
    signal.signal(signal.SIGTERM, cleanup_handler)
    atexit.register(cleanup_handler)

if __name__ == "__main__":
    register_cleanup()
    
    print("Starting Mind-Q Backend (stable mode)...")
    print("Memory optimized for stability")
    print("Auto-restart protection enabled")
    print("========================================")
    
    try:
        import uvicorn
        # Import after path setup
        from backend.src.app.services.pipeline_api.app import app

        # Run the server with the conservative stable defaults
        uvicorn.run(
            app, 
            host="0.0.0.0", 
            port=9000, 
            reload=False,
            log_level="warning",
            timeout_keep_alive=120,
            limit_concurrency=5,
            limit_max_requests=500,
            access_log=False,
            use_colors=False
        )
    except KeyboardInterrupt:
        print("Server stopped by user")
    except Exception as e:
        print(f"Server error: {e}")
        print("Server will restart automatically...")
    finally:
        cleanup_handler()