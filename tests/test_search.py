"""Search machinery: archive, parent sampling, novelty rejection, operator bandit.

The expensive resource here is agent sessions, so these tests are mostly about not
wasting them: duplicates get rejected before evaluation, a losing operator stops
being chosen, and a single lucky candidate does not capture the whole population.
"""

from __future__ import annotations

import random

from orbit import operators
from orbit.archive import Archive, Candidate, fitness_curve, similarity
from orbit.bandit import Bandit
from orbit.fitness import Score

SEED_SOURCE = "function nextItem() { return choose(skill, difficulty, 12); }\n" * 20


def candidate(**kwargs: object) -> Candidate:
    base = dict(id="c", generation=1, island=0, fitness=1.0)
    base.update(kwargs)
    return Candidate(**base)  # type: ignore[arg-type]


# --- novelty ------------------------------------------------------------


def test_identical_source_is_not_novel() -> None:
    archive = Archive()
    assert not archive.is_novel(SEED_SOURCE, against=[SEED_SOURCE])


def test_whitespace_only_change_is_not_novel() -> None:
    archive = Archive()
    reformatted = SEED_SOURCE.replace(" { ", "\n{\n")
    assert not archive.is_novel(reformatted, against=[SEED_SOURCE])


def test_real_edit_is_novel() -> None:
    archive = Archive()
    added = "\nfunction interleave(history) { return shuffleTiers(history); }\n"
    edited = SEED_SOURCE + added * 5
    assert archive.is_novel(edited, against=[SEED_SOURCE])


def test_similarity_is_symmetric_and_bounded() -> None:
    other = SEED_SOURCE.replace("12", "18")
    assert 0.0 <= similarity(SEED_SOURCE, other) <= 1.0
    assert similarity(SEED_SOURCE, other) == similarity(other, SEED_SOURCE)


# --- archive ------------------------------------------------------------


def test_failed_candidates_are_kept_but_never_selected() -> None:
    archive = Archive()
    archive.add(candidate(id="ok", fitness=0.5))
    archive.add(candidate(id="broken", fitness=99.0, gate_failures=["countdown timer"]))
    assert archive.best() is not None
    assert archive.best().id == "ok"
    assert len(archive.candidates) == 2


def test_parent_sampling_explores_but_favours_fitness() -> None:
    archive = Archive(temperature=0.35)
    archive.add(candidate(id="strong", fitness=2.0))
    archive.add(candidate(id="weak", fitness=1.0))
    rng = random.Random(0)
    picks = [archive.sample_parent(0, rng).id for _ in range(300)]
    strong = picks.count("strong")
    assert strong > 200, "should exploit"
    assert strong < 300, "but not exclusively"


def test_empty_island_falls_back_to_the_whole_archive() -> None:
    archive = Archive(islands=2)
    archive.add(candidate(id="only", island=0, fitness=1.0))
    assert archive.sample_parent(1, random.Random(0)).id == "only"


def test_lineage_is_root_to_leaf() -> None:
    archive = Archive()
    archive.add(candidate(id="gen0", generation=0))
    archive.add(candidate(id="gen1", parent_id="gen0"))
    archive.add(candidate(id="gen2", generation=2, parent_id="gen1"))
    assert [c.id for c in archive.lineage("gen2")] == ["gen0", "gen1", "gen2"]


def test_fitness_curve_is_monotone_best_so_far() -> None:
    candidates = [
        candidate(id="a", generation=0, fitness=1.0),
        candidate(id="b", generation=1, fitness=0.4),
        candidate(id="c", generation=2, fitness=1.6),
    ]
    curve = fitness_curve(candidates)
    assert curve == sorted(curve)
    assert curve[-1] == 1.6


def test_archive_round_trips_through_json(tmp_path) -> None:
    archive = Archive(islands=3)
    archive.add(candidate(id="x", session_id="devin-abc", metrics={"total": 1.0}))
    path = tmp_path / "archive.json"
    archive.save(path)
    restored = Archive.load(path)
    assert restored.islands == 3
    assert restored.candidates[0].session_id == "devin-abc"


# --- bandit -------------------------------------------------------------


def names() -> list[str]:
    return [operator.name for operator in operators.OPERATORS]


def test_untried_operators_are_tried_before_repeats() -> None:
    bandit = Bandit.over(names())
    first = bandit.select(k=1)[0]
    bandit.update(first, parent_fitness=1.0, candidate_fitness=2.0)
    assert bandit.select(k=1)[0] != first


def test_a_winning_operator_is_re_selected_once_all_are_tried() -> None:
    bandit = Bandit.over(["a", "b"])
    for _ in range(3):
        bandit.update("a", parent_fitness=1.0, candidate_fitness=2.0)
        bandit.update("b", parent_fitness=1.0, candidate_fitness=0.2)
    assert bandit.select(k=1)[0] == "a"


def test_reward_is_bounded_so_one_outlier_cannot_pin_an_arm() -> None:
    bandit = Bandit.over(["a"])
    reward = bandit.update("a", parent_fitness=0.0, candidate_fitness=1000.0)
    assert 0.0 <= reward <= 1.0


def test_priors_break_ties_between_untried_operators() -> None:
    bandit = Bandit.over(["a", "b"], priors={"a": 0.1, "b": 0.9})
    assert bandit.select(k=1)[0] == "b"


def test_reprior_keeps_observed_history() -> None:
    bandit = Bandit.over(["a", "b"])
    bandit.update("a", parent_fitness=1.0, candidate_fitness=2.0)
    bandit.reprior({"a": 0.0, "b": 1.0})
    assert bandit.arms["a"].pulls == 1


def test_bandit_round_trips_through_json(tmp_path) -> None:
    bandit = Bandit.over(names())
    bandit.update(names()[0], parent_fitness=1.0, candidate_fitness=1.5)
    path = tmp_path / "bandit.json"
    bandit.save(path)
    assert Bandit.load(path).arms[names()[0]].pulls == 1


# --- operators ----------------------------------------------------------


def score(**kwargs: float) -> Score:
    base = dict(
        total=1.0,
        mastery_gain_per_min=0.5,
        engaged_fraction=1.0,
        abandonment_rate=0.0,
        extraneous_load=0.1,
        success_rate=0.85,
        difficulty_penalty=0.0,
        n_attempts=20,
    )
    base.update(kwargs)
    return Score(**base)  # type: ignore[arg-type]


def test_every_operator_prompt_states_the_contract_and_the_evidence() -> None:
    from tests.test_fitness import SWEET_SPOT

    brief = operators.brief(SWEET_SPOT, score())
    for operator in operators.OPERATORS:
        prompt = operator.prompt(game_path="games/orbit/index.html", brief=brief)
        assert "drainEvents()" in prompt
        assert "No countdown timers" in prompt
        assert "success rate: 86%" in prompt or "success rate:" in prompt
        assert operator.name in prompt
        assert "orbit.cli evaluate" in prompt


def test_brief_reports_only_measured_quantities() -> None:
    from tests.test_fitness import SWEET_SPOT

    brief = operators.brief(SWEET_SPOT, score(success_rate=0.85))
    assert "success rate: 85%" in brief
    assert "confidence" not in brief.lower()
    assert "adhd" not in brief.lower()


def test_indications_point_at_the_relevant_operator() -> None:
    from tests.test_fitness import BRUTAL, TRIVIAL

    easy = operators.indications(TRIVIAL, score(success_rate=1.0, difficulty_penalty=0.18))
    hard = operators.indications(BRUTAL, score(success_rate=0.35, difficulty_penalty=0.59))
    assert hard["calibrate_difficulty"] > easy["calibrate_difficulty"]
    assert set(easy) == {operator.name for operator in operators.OPERATORS}
