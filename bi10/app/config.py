from __future__ import annotations

import os
from typing import Optional

from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseModel):
    artifacts_root: str = os.getenv("ARTIFACTS_ROOT", "artifacts")
    default_run_id: str = os.getenv("RUN_ID", "fastcoo-latest")
    timezone: str = os.getenv("TZ", "Asia/Riyadh")
    currency: str = os.getenv("CURRENCY", "SAR")
    llm_enabled: bool = True
    kpi_api_key: Optional[str] = os.getenv("KPI_API_KEY")


settings = Settings()

__all__ = ["settings", "Settings"]
