"""The daily clock behind the reinvention loop.

Once a day, at DAILY_RUN_HOUR_UTC, every live game gets a Devin session tasked
with shipping a noticeably different game (see prompts.ITERATE_PROMPT). The
loop lives inside the API process so a bare `uvicorn app.main:app` is enough;
cron or an external scheduler can hit POST /games/daily-run instead and leave
DAILY_RUN_HOUR_UTC unset.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from app.db import SessionLocal
from app.routers.games import daily_run

logger = logging.getLogger("orbit.scheduler")


def seconds_until(hour: int, now: datetime) -> float:
    """Seconds from `now` to the next occurrence of `hour`:00 UTC."""
    target = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


async def daily_loop(hour: int) -> None:
    while True:
        await asyncio.sleep(seconds_until(hour, datetime.now(UTC)))
        try:
            with SessionLocal() as session:
                result = await daily_run(session=session)
            logger.info(
                "daily run: %d started, %d skipped",
                len(result["started"]),
                len(result["skipped"]),
            )
        except Exception:
            logger.exception("daily run failed; will retry tomorrow")
