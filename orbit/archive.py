"""The population: an archive of evaluated candidates, on islands.

Three ideas from the current literature, chosen because they attack the specific
constraint here — each sample costs an agent session:

* **Archive + island model** (AlphaEvolve; OpenEvolve): keep every evaluated
  program, partitioned into islands that evolve separately, so the search does
  not collapse onto one lineage after a single lucky candidate.
* **Parent sampling that balances exploration and exploitation**
  (ShinkaEvolve, ICLR 2026): sample the parent from a softmax over fitness
  within an island rather than always taking the best.
* **Novelty rejection sampling** (ShinkaEvolve): before spending a session,
  reject a candidate whose code is near-identical to something already
  evaluated. Cheap here — token-shingle Jaccard on the source — and it directly
  saves ACUs.

Also kept: the artifact side-channel (OpenEvolve) — a rejected candidate's gate
failures and console errors are stored so the next prompt can carry them.
"""

from __future__ import annotations

import json
import math
import random
import re
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path

TOKEN = re.compile(r"[A-Za-z_][A-Za-z_0-9]*|\d+|[^\sA-Za-z_0-9]")
SHINGLE = 5
#: Above this Jaccard similarity two candidates are the same idea.
NOVELTY_THRESHOLD = 0.92


def shingles(source: str) -> frozenset[tuple[str, ...]]:
    tokens = TOKEN.findall(source)
    if len(tokens) <= SHINGLE:
        return frozenset({tuple(tokens)})
    return frozenset(
        tuple(tokens[index : index + SHINGLE])
        for index in range(len(tokens) - SHINGLE + 1)
    )


def similarity(left: str, right: str) -> float:
    a, b = shingles(left), shingles(right)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


@dataclass
class Candidate:
    """One evaluated program plus everything needed to justify it later."""

    id: str
    generation: int
    island: int
    fitness: float
    parent_id: str | None = None
    operator: str | None = None
    #: Devin session that wrote it, or None for the seed candidate.
    session_id: str | None = None
    path: str = ""
    metrics: dict[str, float] = field(default_factory=dict)
    gate_failures: list[str] = field(default_factory=list)
    console_errors: list[str] = field(default_factory=list)
    summary: str = ""
    diff_stat: str = ""

    @property
    def viable(self) -> bool:
        return not self.gate_failures

    def artifacts(self) -> str:
        """The side-channel text a follow-up prompt should carry."""
        parts = []
        if self.gate_failures:
            parts.append("gate failures: " + "; ".join(self.gate_failures))
        if self.console_errors:
            parts.append("javascript errors: " + "; ".join(self.console_errors[:3]))
        return "\n".join(parts)


@dataclass
class Archive:
    islands: int = 2
    candidates: list[Candidate] = field(default_factory=list)
    temperature: float = 0.35
    novelty_threshold: float = NOVELTY_THRESHOLD

    def add(self, candidate: Candidate) -> Candidate:
        self.candidates.append(candidate)
        return candidate

    def viable(self, island: int | None = None) -> list[Candidate]:
        return [
            candidate
            for candidate in self.candidates
            if candidate.viable and (island is None or candidate.island == island)
        ]

    def best(self, island: int | None = None) -> Candidate | None:
        pool = self.viable(island)
        return max(pool, key=lambda candidate: candidate.fitness) if pool else None

    def sample_parent(self, island: int, rng: random.Random) -> Candidate | None:
        """Softmax-over-fitness parent choice: exploit, but not exclusively.

        Falls back to the whole archive when an island is empty, which is what
        migration amounts to at this population size.
        """
        pool = self.viable(island) or self.viable()
        if not pool:
            return None
        top = max(candidate.fitness for candidate in pool)
        # Fitness here is an arbitrary weighted sum, so an absolute temperature
        # would mean something different for every objective. Normalising by the
        # pool's own spread makes `temperature` scale-free: it is the softmax
        # width in units of "best minus worst candidate".
        spread = top - min(candidate.fitness for candidate in pool)
        scale = max(spread, 1e-9) * max(self.temperature, 1e-6)
        weights = [math.exp((candidate.fitness - top) / scale) for candidate in pool]
        return rng.choices(pool, weights=weights, k=1)[0]

    def is_novel(self, source: str, *, against: Iterable[str] | None = None) -> bool:
        """False when this source duplicates something already evaluated."""
        sources = against
        if sources is None:
            sources = [
                Path(candidate.path).read_text(encoding="utf-8")
                for candidate in self.candidates
                if candidate.path and Path(candidate.path).exists()
            ]
        return all(similarity(source, other) < self.novelty_threshold for other in sources)

    def lineage(self, candidate_id: str) -> list[Candidate]:
        """Root-to-candidate chain — the provenance a teacher actually reads."""
        by_id = {candidate.id: candidate for candidate in self.candidates}
        chain: list[Candidate] = []
        current = by_id.get(candidate_id)
        while current is not None:
            chain.append(current)
            current = by_id.get(current.parent_id) if current.parent_id else None
        return list(reversed(chain))

    def frontier(self) -> list[Candidate]:
        """Best viable candidate per island — the next generation's parents."""
        return [
            best
            for best in (self.best(island) for island in range(self.islands))
            if best is not None
        ]

    def as_dict(self) -> dict[str, object]:
        return {
            "islands": self.islands,
            "temperature": self.temperature,
            "candidates": [asdict(candidate) for candidate in self.candidates],
        }

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.as_dict(), indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> Archive:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(
            islands=int(raw.get("islands", 2)),
            temperature=float(raw.get("temperature", 0.35)),
            candidates=[Candidate(**entry) for entry in raw.get("candidates", [])],
        )


def fitness_curve(candidates: Sequence[Candidate]) -> list[float]:
    """Best-so-far fitness by generation — the line that goes up in the demo."""
    curve: list[float] = []
    best = float("-inf")
    for generation in sorted({candidate.generation for candidate in candidates}):
        for candidate in candidates:
            if candidate.generation == generation and candidate.viable:
                best = max(best, candidate.fitness)
        curve.append(best)
    return curve
