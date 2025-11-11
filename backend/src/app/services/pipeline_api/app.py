"""Legacy shim to maintain backward compatibility; prefer backend.src.app.pipeline_api."""
from backend.src.app.pipeline_api.app import *  # type: ignore[F401,F403]