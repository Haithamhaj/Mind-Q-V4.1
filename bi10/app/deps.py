from __future__ import annotations

import logging
import time
from fastapi import Request
from typing import Callable

logger = logging.getLogger("bi10")


async def log_request(request: Request, call_next: Callable):
    start = time.time()
    response = await call_next(request)
    duration_ms = (time.time() - start) * 1000
    logger.info("%s %s -> %s in %.1fms", request.method, request.url.path, response.status_code, duration_ms)
    return response


__all__ = ["log_request"]
