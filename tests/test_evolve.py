"""The evolution loop, with the agent and the browser both stubbed.

What matters here is the control flow around the expensive parts: a broken
candidate is rejected rather than promoted, a duplicate never reaches the
evaluator, the bandit is credited from real fitness deltas, and the provenance
record can answer "why does this version of the game exist?".
"""

from __future__ import annotations

import json
from pathlib import Path

from orbit import operators
from orbit.archive import Archive
from orbit.bandit import Bandit
from orbit.evolve import EvolutionRun, MutationOutcome, MutationTask
from orbit.policy import COHORT
from orbit.rollout import RolloutResult
from orbit.telemetry import Trace
from tests.test_fitness import BRUTAL, SWEET_SPOT, TRIVIAL, synthetic_trace

CONTRACT_JS = "window.orbit={observe(){},drainEvents(){},isOver(){}}"
SEED_HTML = f"<html><script>{CONTRACT_JS}</script></html>"


class StubBrowser:
    """Returns pre-set traces per candidate path instead of playing a page."""

    def __init__(self, default: Trace, by_name: dict[str, Trace] | None = None) -> None:
        self.default = default
        self.by_name = by_name or {}
        self.evaluated: list[str] = []

    def __call__(self, path, **kwargs) -> list[RolloutResult]:
        name = Path(path).name
        self.evaluated.append(name)
        trace = next(
            (trace for key, trace in self.by_name.items() if key in name), self.default
        )
        return [RolloutResult(trace=trace, profile=COHORT[0].name)]


class ScriptedMutator:
    """Stands in for Devin: yields prepared sources, records the prompts it got."""

    def __init__(self, *sources: str) -> None:
        self.sources = list(sources)
        self.tasks: list[MutationTask] = []

    def mutate(self, task: MutationTask) -> MutationOutcome:
        self.tasks.append(task)
        source = self.sources.pop(0) if self.sources else SEED_HTML
        return MutationOutcome(
            task=task,
            source=source,
            session_id=f"devin-{task.operator.name}",
            session_url="https://app.devin.ai/sessions/x",
            summary=f"applied {task.operator.name}",
            acus=3.0,
        )


def variant(marker: str) -> str:
    """A source that is genuinely different, so novelty rejection lets it through."""
    body = "".join(f"function step{marker}{i}(a,b){{return a+b+{i};}}\n" for i in range(40))
    return SEED_HTML.replace("</html>", f"<script>{body}</script></html>")


def make_run(tmp_path: Path, mutator, browser, *, islands: int = 1) -> EvolutionRun:
    seed = tmp_path / "seed.html"
    seed.write_text(SEED_HTML, encoding="utf-8")
    return EvolutionRun(
        seed_path=seed,
        workdir=tmp_path / "candidates",
        mutator=mutator,
        archive=Archive(islands=islands),
        bandit=Bandit.over([operator.name for operator in operators.OPERATORS]),
        trace=TRIVIAL,
        seeds=(1,),
        evaluator=browser,
    )


def test_seed_generation_establishes_the_baseline(tmp_path: Path) -> None:
    run = make_run(tmp_path, ScriptedMutator(), StubBrowser(TRIVIAL))
    seed = run.seed()
    assert seed.generation == 0
    assert seed.fitness == run.archive.best().fitness


def test_a_better_candidate_is_promoted_over_the_baseline(tmp_path: Path) -> None:
    browser = StubBrowser(TRIVIAL, {"gen1": SWEET_SPOT})
    run = make_run(tmp_path, ScriptedMutator(variant("A")), browser)
    run.run(generations=1)
    best = run.archive.best()
    assert best.generation == 1
    assert best.fitness > run.archive.candidates[0].fitness


def test_a_worse_candidate_does_not_displace_the_baseline(tmp_path: Path) -> None:
    browser = StubBrowser(SWEET_SPOT, {"gen1": BRUTAL})
    run = make_run(tmp_path, ScriptedMutator(variant("B")), browser)
    run.run(generations=1)
    assert run.archive.best().generation == 0


def test_a_candidate_that_breaks_the_contract_is_rejected(tmp_path: Path) -> None:
    broken = "<html><script>/* orbit contract removed */</script></html>" + "x" * 500
    run = make_run(tmp_path, ScriptedMutator(broken), StubBrowser(SWEET_SPOT))
    run.run(generations=1)
    rejected = [c for c in run.archive.candidates if c.generation == 1]
    assert rejected and not rejected[0].viable
    assert any("contract" in failure for failure in rejected[0].gate_failures)


def test_a_countdown_timer_is_rejected_however_good_the_score(tmp_path: Path) -> None:
    cheating = variant("C").replace("</html>", "<script>let timeLeft=30;</script></html>")
    run = make_run(tmp_path, ScriptedMutator(cheating), StubBrowser(SWEET_SPOT))
    run.run(generations=1)
    failures = [c.gate_failures for c in run.archive.candidates if c.generation == 1]
    assert failures and "countdown timer detected" in failures[0]


def test_a_duplicate_candidate_is_rejected_before_it_is_evaluated(tmp_path: Path) -> None:
    browser = StubBrowser(SWEET_SPOT)
    run = make_run(tmp_path, ScriptedMutator(SEED_HTML), browser)
    run.run(generations=1)
    assert browser.evaluated == ["seed.html"], "duplicate must not reach the browser"
    duplicate = [c for c in run.archive.candidates if c.generation == 1][0]
    assert "duplicate" in duplicate.gate_failures[0]


def test_a_session_that_pushed_nothing_is_recorded_not_crashed(tmp_path: Path) -> None:
    class Failing:
        def mutate(self, task: MutationTask) -> MutationOutcome:
            return MutationOutcome(task=task, source="", failure="branch not found")

    run = make_run(tmp_path, Failing(), StubBrowser(SWEET_SPOT))
    run.run(generations=1)
    assert run.archive.best().generation == 0
    assert any("branch not found" in c.gate_failures[0] for c in run.archive.candidates[1:])


def test_prompts_carry_the_measured_evidence(tmp_path: Path) -> None:
    mutator = ScriptedMutator(variant("D"))
    run = make_run(tmp_path, mutator, StubBrowser(TRIVIAL))
    run.run(generations=1)
    prompt = mutator.tasks[0].prompt
    assert "success rate:" in prompt
    assert "items attempted:" in prompt


def test_artifacts_from_a_failed_parent_are_fed_back(tmp_path: Path) -> None:
    run = make_run(tmp_path, ScriptedMutator(), StubBrowser(SWEET_SPOT))
    seed = run.seed()
    seed.console_errors.append("cursor is not defined")
    tasks = run.plan(1)
    assert tasks and "cursor is not defined" in tasks[0].prompt


def test_islands_run_different_operators_in_one_generation(tmp_path: Path) -> None:
    mutator = ScriptedMutator(variant("E"), variant("F"))
    run = make_run(tmp_path, mutator, StubBrowser(SWEET_SPOT), islands=2)
    run.run(generations=1)
    chosen = {task.operator.name for task in mutator.tasks}
    assert len(chosen) == 2


def test_bandit_is_credited_from_the_measured_delta(tmp_path: Path) -> None:
    browser = StubBrowser(TRIVIAL, {"gen1": SWEET_SPOT})
    run = make_run(tmp_path, ScriptedMutator(variant("G")), browser)
    run.run(generations=1)
    pulled = [arm for arm in run.bandit.arms.values() if arm.pulls]
    assert len(pulled) == 1
    assert pulled[0].reward > 0.5, "a fitness improvement must be rewarded"


def test_provenance_answers_why_this_version_exists(tmp_path: Path) -> None:
    browser = StubBrowser(TRIVIAL, {"gen1": SWEET_SPOT})
    run = make_run(tmp_path, ScriptedMutator(variant("H")), browser)
    run.run(generations=1)
    path = run.write_provenance(tmp_path / "provenance.json")
    record = json.loads(path.read_text(encoding="utf-8"))

    assert record["promoted"] == run.archive.best().id
    lineage = record["lineage"]
    assert lineage[0]["id"].startswith("gen0")
    assert lineage[-1]["session"].startswith("devin-")
    assert record["generations"][1]["acus"] == 3.0
    assert record["operators"]["arms"]


def test_acus_are_totalled_per_generation(tmp_path: Path) -> None:
    run = make_run(
        tmp_path,
        ScriptedMutator(variant("I"), variant("J")),
        StubBrowser(SWEET_SPOT),
        islands=2,
    )
    run.run(generations=1)
    assert run.generations[1].acus == 6.0


def test_two_generations_chain_parent_to_child(tmp_path: Path) -> None:
    improving = synthetic_trace(n=30, success_rate=0.85, difficulty=4)
    browser = StubBrowser(TRIVIAL, {"gen1": SWEET_SPOT, "gen2": improving})
    run = make_run(tmp_path, ScriptedMutator(variant("K"), variant("L")), browser)
    run.run(generations=2)
    best = run.archive.best()
    assert best.generation == 2
    assert [c.generation for c in run.archive.lineage(best.id)] == [0, 1, 2]
