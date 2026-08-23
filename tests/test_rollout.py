"""The rollout loop, driven against a fake page.

Real-browser behaviour is verified by running `orbit evaluate`; what is pinned
here is the bookkeeping the loop is responsible for, which a real page cannot
show: that a learner giving up leaves an abandonment event in the trace. The
game only ever finishes on time, so without this the abandonment penalty and the
"everyone quit" gate would be silently inert during an evolution run.
"""

from __future__ import annotations

import asyncio
from typing import Any

from orbit import rollout
from orbit.policy import COHORT, Decision
from orbit.rollout import rollout_page
from orbit.telemetry import LEVEL_ABANDONED

OBSERVATION: dict[str, Any] = {
    "problem": {"a": 7, "b": 6, "op": "+", "difficulty": 2},
    "awaiting_input": True,
    "cursor": 0,
    "number_line_max": 20,
    "elapsed_ms": 41_000,
}


class FakeClock:
    async def install(self) -> None: ...

    async def run_for(self, _ms: int) -> None: ...


class FakeKeyboard:
    async def press(self, _key: str) -> None: ...


class FakePage:
    """Answers the handful of evaluate() calls the loop makes."""

    def __init__(self, drained: list[dict[str, Any]] | None = None) -> None:
        self.clock = FakeClock()
        self.keyboard = FakeKeyboard()
        self.drained = drained if drained is not None else []
        self.clicks: list[str] = []

    def on(self, _event: str, _handler: Any) -> None: ...

    def set_default_timeout(self, _ms: int) -> None: ...

    async def goto(self, _url: str) -> None: ...

    async def click(self, selector: str) -> None:
        self.clicks.append(selector)

    async def evaluate(self, script: str) -> Any:
        if script.startswith("typeof"):
            return True
        if "isOver" in script:
            return False
        if "drainEvents" in script:
            drained, self.drained = self.drained, []
            return drained
        return dict(OBSERVATION)


class Quitter:
    def __init__(self, *_args: Any, **_kwargs: Any) -> None: ...

    def act(self, _observation: dict[str, Any]) -> Decision:
        return Decision(value=0, think_ms=500, quit=True)


def run(page: FakePage) -> rollout.RolloutResult:
    return asyncio.run(rollout_page(page, "http://x/game.html", COHORT[0], seed=1))


def test_a_learner_giving_up_is_recorded_as_abandonment(monkeypatch: Any) -> None:
    monkeypatch.setattr(rollout, "SimulatedLearner", Quitter)
    page = FakePage()

    result = run(page)

    assert result.trace.abandoned
    (event,) = [e for e in result.events if e["type"] == LEVEL_ABANDONED]
    assert event["t_ms"] == OBSERVATION["elapsed_ms"]
    assert page.clicks == []  # it walked away without answering


def test_a_candidate_that_reports_its_own_abandonment_is_not_double_counted(
    monkeypatch: Any,
) -> None:
    monkeypatch.setattr(rollout, "SimulatedLearner", Quitter)
    page = FakePage(drained=[{"type": LEVEL_ABANDONED, "t_ms": 12_000}])

    result = run(page)

    events = [e for e in result.events if e["type"] == LEVEL_ABANDONED]
    assert [e["t_ms"] for e in events] == [12_000]
