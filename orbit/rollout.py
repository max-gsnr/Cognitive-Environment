"""Play a candidate game in a real headless browser.

This is the part that makes the search space real code instead of five config
values: the evaluator never reads the game's source, it clicks on the page. A
candidate may rewrite mechanics, rendering, scaffolds or DOM structure and it is
still evaluable, as long as it keeps the three-function contract:

    window.orbit.observe()  ->  what a player can see
    window.orbit.drainEvents()
    window.orbit.isOver()

Wall-clock cost is kept low by installing Playwright's controllable clock
(``page.clock``, v1.45+): simulated deliberation advances *game* time by seconds
while costing microseconds of real time.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .policy import COHORT, LearnerProfile, SimulatedLearner
from .telemetry import Trace

CONTRACT = ("observe", "drainEvents", "isOver")


class ContractError(RuntimeError):
    """The candidate broke the evaluation contract; it fails its gate."""


@dataclass
class RolloutResult:
    trace: Trace
    console_errors: list[str] = field(default_factory=list)
    profile: str = "sim"
    #: The raw event stream, kept so a rollout can be replayed or used as the
    #: session log that seeds an evolution run.
    events: list[dict[str, Any]] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return not self.console_errors


async def _await_problem(page: Any, tries: int = 40) -> dict[str, Any] | None:
    """Wait for the next item, advancing the virtual clock through the cooldown."""
    for _ in range(tries):
        observation = await page.evaluate("window.orbit.observe()")
        if observation.get("problem") and observation.get("awaiting_input"):
            return observation
        if await page.evaluate("window.orbit.isOver()"):
            return None
        await page.clock.run_for(250)
    return None


async def rollout_page(
    page: Any,
    url: str,
    profile: LearnerProfile,
    *,
    seed: int = 0,
    max_items: int = 60,
) -> RolloutResult:
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on(
        "console",
        lambda message: errors.append(message.text) if message.type == "error" else None,
    )

    # A candidate that stops responding must fail fast rather than stall a sweep.
    page.set_default_timeout(5000)
    await page.clock.install()
    joiner = "&" if "?" in url else "?"
    await page.goto(f"{url}{joiner}seed={seed}")

    missing = [
        name
        for name in CONTRACT
        if not await page.evaluate(
            f"typeof (window.orbit && window.orbit.{name}) === 'function'"
        )
    ]
    if missing:
        raise ContractError(f"window.orbit is missing {', '.join(missing)}")

    learner = SimulatedLearner(profile, seed=seed)
    events: list[dict[str, Any]] = []

    for _ in range(max_items):
        observation = await _await_problem(page)
        if observation is None:
            break
        decision = learner.act(observation)
        if decision.quit:
            break
        if decision.use_hint:
            await page.click("#hint")
            await page.clock.run_for(600)
            observation = await page.evaluate("window.orbit.observe()")

        await page.clock.run_for(decision.think_ms)
        # The session can end while the learner deliberates — a slow learner
        # simply gets fewer items, which is signal, not an error.
        after = await page.evaluate("window.orbit.observe()")
        if not after.get("awaiting_input") or after.get("problem") is None:
            break

        await _move_to(page, after, decision.value)
        await page.click("#land")
        await page.clock.run_for(200)
        events += await page.evaluate("window.orbit.drainEvents()")

    events += await page.evaluate("window.orbit.drainEvents()")
    return RolloutResult(
        trace=Trace.from_events(events, seed=seed),
        console_errors=errors,
        profile=profile.name,
        events=events,
    )


async def _move_to(page: Any, observation: dict[str, Any], value: int) -> None:
    """Drive the rocket with real key presses, exactly as a player would."""
    cursor = int(observation.get("cursor", 0))
    limit = int(observation.get("number_line_max", 20))
    target = max(0, min(limit, value))
    key = "ArrowRight" if target > cursor else "ArrowLeft"
    for _ in range(abs(target - cursor)):
        await page.keyboard.press(key)


def target_url(candidate: str | Path) -> str:
    """Accept a local file or a deployed URL.

    The demo runs in the cloud (a Devin session's VM, a deployed build), so the
    harness must be able to play a candidate it cannot see on disk; a local file
    is the fallback path, not the only one.
    """
    text = str(candidate)
    if text.startswith(("http://", "https://", "file://")):
        return text
    return Path(text).resolve().as_uri()


async def evaluate_candidate(
    game_path: str | Path,
    *,
    profiles: Sequence[LearnerProfile] = COHORT,
    seeds: Sequence[int] = (1, 2, 3, 4, 5, 6),
    headless: bool = True,
) -> list[RolloutResult]:
    """Run the cohort × seeds grid against one candidate, local file or URL."""
    from playwright.async_api import async_playwright  # imported lazily: optional dep

    url = target_url(game_path)
    results: list[RolloutResult] = []
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=headless)
        context = await browser.new_context(viewport={"width": 960, "height": 600})
        for profile in profiles:
            for seed in seeds:
                page = await context.new_page()
                try:
                    results.append(await rollout_page(page, url, profile, seed=seed))
                finally:
                    await page.close()
        await browser.close()
    return results


def evaluate_candidate_sync(game_path: str | Path, **kwargs: Any) -> list[RolloutResult]:
    return asyncio.run(evaluate_candidate(game_path, **kwargs))
