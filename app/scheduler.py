"""Background loops that keep the reinvention pipeline moving on its own.

Two loops live inside the API process so a bare `uvicorn app.main:app` is a
fully autonomous system:

- `poll_loop` finalizes in-flight Devin sessions: every game left in
  `generating`/`iterating` is polled and, once finished, gated and set live
  without anyone watching a frontend. Without it, successors would stay
  in flight forever and block the next reinvention.
- `daily_loop` is the safety-net clock: at DAILY_RUN_HOUR_UTC it reinvents
  every live game that has no successor in flight, so a game a child stopped
  playing still keeps evolving. Cron can hit POST /games/daily-run instead
  and leave DAILY_RUN_HOUR_UTC unset. The primary trigger is per play
  session: the game shell POSTs /games/{id}/session-complete when a session
  ends.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Game
from app.routers.games import _poll, daily_run

logger = logging.getLogger("orbit.scheduler")

POLL_INTERVAL_SECONDS = 120


def seconds_until(hour: int, now: datetime) -> float:
    """Seconds from `now` to the next occurrence of `hour`:00 UTC."""
    target = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


async def poll_loop(interval: float = POLL_INTERVAL_SECONDS) -> None:
    """Drive every in-flight Devin session to completion."""
    while True:
        await asyncio.sleep(interval)
        try:
            with SessionLocal() as session:
                in_flight = session.scalars(
                    select(Game).where(
                        Game.status.in_(["generating", "iterating"]),
                        Game.devin_session_id.is_not(None),
                    )
                ).all()
                for game in in_flight:
                    action = (
                        "iteration_completed"
                        if game.status == "iterating"
                        else "generation_completed"
                    )
                    before = game.status
                    try:
                        state = await _poll(session, game.id, action=action)
                        if state["status"] != before:
                            logger.info(
                                "poll: game %s -> %s", game.id, state["status"]
                            )
                    except Exception:
                        session.rollback()
                        logger.exception("poll failed for game %s", game.id)
        except Exception:
            logger.exception("poll loop pass failed; retrying next interval")


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
