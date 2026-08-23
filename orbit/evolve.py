"""The evolution loop: parallel Devin sessions as mutation operators.

One generation:

1. Sample a parent per island from the archive (softmax over fitness).
2. Refresh the bandit's priors from the child's newest trace, then let it pick
   which operator each session should apply.
3. Fan out one Devin session per (parent, operator), in parallel, each with the
   measured evidence, the parent's artifacts, and the contract it must preserve.
   Every session pushes a branch.
4. Pull each branch's candidate file, reject near-duplicates before paying to
   evaluate them, run the gates, play it in headless Chromium, score it.
5. Insert into the archive, credit the bandit, and write a provenance record
   linking session -> prompt -> diff -> gate result -> fitness.

Devin is not decorative here: the mutation is arbitrary source-code editing, and
the harness never reads the source it evaluates. If the agent rewrites the render
loop, the input handling or the scaffolding, the candidate is still playable and
still scored.
"""

from __future__ import annotations

import json
import random
import subprocess
import uuid
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from . import gates, operators
from .archive import Archive, Candidate
from .bandit import Bandit
from .devin import DevinClient, Session
from .fitness import Score, Weights, score_candidate
from .operators import Operator
from .policy import COHORT, LearnerProfile
from .rollout import ContractError, RolloutResult, evaluate_candidate_sync
from .telemetry import Trace

GAME_PATH = "games/orbit/index.html"


@dataclass
class MutationTask:
    generation: int
    island: int
    parent: Candidate
    operator: Operator
    prompt: str
    branch: str


@dataclass
class MutationOutcome:
    """What a mutation attempt produced, before we know whether it is any good."""

    task: MutationTask
    source: str
    session_id: str | None = None
    session_url: str = ""
    summary: str = ""
    mechanism: str = ""
    acus: float = 0.0
    failure: str = ""


class Mutator(Protocol):
    def mutate(self, task: MutationTask) -> MutationOutcome: ...


def _run(args: Sequence[str], cwd: Path) -> str:
    result = subprocess.run(
        list(args), cwd=str(cwd), capture_output=True, text=True, check=False
    )
    if result.returncode:
        raise RuntimeError(f"{' '.join(args)}: {result.stderr.strip()[:300]}")
    return result.stdout


class DevinMutator:
    """Spawns a real Devin session and reads the candidate off the branch it pushed."""

    def __init__(
        self,
        client: DevinClient,
        *,
        repo: str,
        repo_dir: str | Path = ".",
        game_path: str = GAME_PATH,
        base_branch: str = "main",
        max_acu_limit: int = 12,
        wait_kwargs: dict[str, object] | None = None,
    ) -> None:
        self.client = client
        self.repo = repo
        self.repo_dir = Path(repo_dir)
        self.game_path = game_path
        self.base_branch = base_branch
        self.max_acu_limit = max_acu_limit
        self.wait_kwargs = wait_kwargs or {}

    def _instructions(self, task: MutationTask) -> str:
        parent = (
            f"- Parent candidate: `{task.parent.id}`"
            f" (fitness {task.parent.fitness:.3f}).\n"
        )
        return (
            f"{task.prompt}\n\n## Mechanics\n\n"
            f"- Repository `{self.repo}`, file `{self.game_path}`.\n"
            f"- Branch off `{self.base_branch}`.\n"
            f"{parent}"
            f"- Commit and push to the branch `{task.branch}` exactly. Do not open a PR.\n"
            "- Then return the structured output: summary, branch, mechanism,"
            " gates_passed, self_reported_fitness.\n"
        )

    def mutate(self, task: MutationTask) -> MutationOutcome:
        session = self.client.create_session(
            self._instructions(task),
            title=f"Orbit gen{task.generation}: {task.operator.name}",
            repos=[self.repo],
            tags=["orbit", f"gen{task.generation}", task.operator.name],
            max_acu_limit=self.max_acu_limit,
        )
        finished: Session = self.client.wait(session.session_id, **self.wait_kwargs)  # type: ignore[arg-type]
        output = finished.structured_output or {}
        branch = str(output.get("branch") or task.branch)
        try:
            source = self.fetch(branch)
        except RuntimeError as error:
            return MutationOutcome(
                task=task,
                source="",
                session_id=finished.session_id,
                session_url=finished.url,
                acus=finished.acus_consumed,
                failure=f"could not read candidate from {branch}: {error}",
            )
        return MutationOutcome(
            task=task,
            source=source,
            session_id=finished.session_id,
            session_url=finished.url,
            summary=str(output.get("summary") or ""),
            mechanism=str(output.get("mechanism") or ""),
            acus=finished.acus_consumed,
        )

    def fetch(self, branch: str) -> str:
        _run(["git", "fetch", "--quiet", "origin", branch], self.repo_dir)
        return _run(["git", "show", f"FETCH_HEAD:{self.game_path}"], self.repo_dir)


@dataclass
class Generation:
    index: int
    candidates: list[Candidate] = field(default_factory=list)
    acus: float = 0.0


@dataclass
class EvolutionRun:
    """Orchestrates generations and owns the provenance record."""

    seed_path: Path
    workdir: Path
    mutator: Mutator
    archive: Archive
    bandit: Bandit
    trace: Trace
    weights: Weights = field(default_factory=Weights)
    profiles: Sequence[LearnerProfile] = COHORT
    seeds: Sequence[int] = (1, 2, 3)
    rng: random.Random = field(default_factory=lambda: random.Random(7))
    generations: list[Generation] = field(default_factory=list)
    evaluator: Callable[..., list[RolloutResult]] = evaluate_candidate_sync

    # --- evaluation -----------------------------------------------------

    def evaluate(self, path: Path) -> tuple[Score, list[str], list[str], list[Trace]]:
        try:
            results = self.evaluator(path, profiles=self.profiles, seeds=self.seeds)
        except ContractError as error:
            empty = Trace.from_events([])
            return score_candidate([empty], self.weights), [str(error)], [], [empty]
        failures = gates.evaluate(path, results).failures
        console = [error for result in results for error in result.console_errors]
        traces = [result.trace for result in results]
        return score_candidate(traces, self.weights), failures, console, traces

    def seed(self) -> Candidate:
        """Evaluate the unmutated game once: generation 0 and the baseline to beat."""
        score, failures, console, _ = self.evaluate(self.seed_path)
        candidate = self.archive.add(
            Candidate(
                id="gen0-seed",
                generation=0,
                island=0,
                fitness=score.total,
                path=str(self.seed_path),
                metrics=score.as_dict(),
                gate_failures=failures,
                console_errors=console,
                summary="unmutated baseline",
            )
        )
        # Islands share the baseline so every island starts from something viable.
        for island in range(1, self.archive.islands):
            self.archive.add(
                Candidate(
                    **{**asdict(candidate), "id": f"gen0-seed-i{island}", "island": island}
                )
            )
        self.generations.append(Generation(index=0, candidates=[candidate]))
        return candidate

    # --- one generation -------------------------------------------------

    def plan(self, index: int) -> list[MutationTask]:
        best = self.archive.best()
        baseline = (
            Score(**best.metrics) if best and best.metrics else score_candidate([self.trace])
        )
        self.bandit.reprior(operators.indications(self.trace, baseline))
        brief = operators.brief(self.trace, baseline)

        tasks: list[MutationTask] = []
        chosen = self.bandit.select(k=self.archive.islands)
        for island, name in enumerate(chosen):
            parent = self.archive.sample_parent(island, self.rng)
            if parent is None:
                continue
            operator = operators.BY_NAME[name]
            artifacts = parent.artifacts()
            evidence = brief if not artifacts else f"{brief}\n\nPrevious attempt:\n{artifacts}"
            tasks.append(
                MutationTask(
                    generation=index,
                    island=island,
                    parent=parent,
                    operator=operator,
                    prompt=operator.prompt(game_path=GAME_PATH, brief=evidence),
                    branch=f"orbit/gen{index}-{name}-{uuid.uuid4().hex[:6]}",
                )
            )
        return tasks

    def run_generation(self, index: int) -> Generation:
        tasks = self.plan(index)
        generation = Generation(index=index)
        if not tasks:
            self.generations.append(generation)
            return generation

        with ThreadPoolExecutor(max_workers=len(tasks)) as pool:
            outcomes = list(pool.map(self.mutator.mutate, tasks))

        for outcome in outcomes:
            generation.acus += outcome.acus
            candidate = self.admit(outcome)
            if candidate is not None:
                generation.candidates.append(candidate)
        self.generations.append(generation)
        return generation

    def admit(self, outcome: MutationOutcome) -> Candidate | None:
        """Gate, evaluate and file one mutation attempt."""
        task = outcome.task
        candidate_id = f"gen{task.generation}-{task.operator.name}-{task.island}"
        base = dict(
            id=candidate_id,
            generation=task.generation,
            island=task.island,
            parent_id=task.parent.id,
            operator=task.operator.name,
            session_id=outcome.session_id,
            summary=outcome.summary,
        )

        if outcome.failure or not outcome.source:
            return self.archive.add(
                Candidate(
                    **base,
                    fitness=float("-inf"),
                    gate_failures=[outcome.failure or "no candidate produced"],
                )
            )

        if not self.archive.is_novel(outcome.source):
            # Rejected before evaluation: this is the ACU saving, so it is recorded.
            return self.archive.add(
                Candidate(
                    **base,
                    fitness=float("-inf"),
                    gate_failures=["duplicate of an already-evaluated candidate"],
                )
            )

        path = self.workdir / f"{candidate_id}.html"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(outcome.source, encoding="utf-8")

        score, failures, console, _ = self.evaluate(path)
        candidate = self.archive.add(
            Candidate(
                **base,
                fitness=score.total if not failures else float("-inf"),
                path=str(path),
                metrics=score.as_dict(),
                gate_failures=failures,
                console_errors=console,
                diff_stat=outcome.mechanism,
            )
        )
        self.bandit.update(
            task.operator.name,
            parent_fitness=task.parent.fitness,
            candidate_fitness=candidate.fitness if candidate.viable else -1.0,
        )
        return candidate

    def run(self, generations: int = 2) -> Candidate | None:
        if not self.archive.candidates:
            self.seed()
        for index in range(1, generations + 1):
            self.run_generation(index)
        return self.archive.best()

    # --- provenance -----------------------------------------------------

    def provenance(self) -> dict[str, object]:
        best = self.archive.best()
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "seed_candidate": str(self.seed_path),
            "generations": [
                {
                    "index": generation.index,
                    "acus": round(generation.acus, 2),
                    "candidates": [candidate.id for candidate in generation.candidates],
                }
                for generation in self.generations
            ],
            "operators": self.bandit.as_dict(),
            "promoted": best.id if best else None,
            "promoted_fitness": best.fitness if best else None,
            "lineage": [
                {
                    "id": candidate.id,
                    "operator": candidate.operator,
                    "session": candidate.session_id,
                    "fitness": candidate.fitness,
                    "summary": candidate.summary,
                }
                for candidate in (self.archive.lineage(best.id) if best else [])
            ],
            "archive": self.archive.as_dict(),
        }

    def write_provenance(self, path: str | Path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self.provenance(), indent=2), encoding="utf-8")
        return target
