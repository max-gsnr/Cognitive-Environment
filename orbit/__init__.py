"""Orbit: a learner model, a fitness function, and a real-DOM evaluator.

The pieces fit together in one direction:

    telemetry  ->  learner model  ->  fitness  ->  candidate ranking

``rollout`` produces telemetry from a mutated copy of ``games/orbit/index.html``
by playing it in a headless browser, so the search space is the game's source
code rather than a handful of config values.
"""

from __future__ import annotations

__all__ = ["engagement", "fitness", "learner", "policy", "rollout", "telemetry"]
