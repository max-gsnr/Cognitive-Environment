"""Mutation operators — the pedagogical moves an agent is allowed to try.

In an LLM-driven evolutionary search the model *is* the mutation operator
(AlphaEvolve, arXiv:2506.13131; ShinkaEvolve, ICLR 2026). Left unconstrained it
mutates whatever it happens to notice, which wastes samples — and here a sample
is a whole Devin session, so waste is measured in ACUs.

So each operator is a named, research-grounded intervention with its own prompt.
The bandit in :mod:`orbit.bandit` learns which ones actually raise fitness for
*this* learner, which is the interesting result: the system discovers which
pedagogical lever matters for a particular child rather than being told.

Citations are to work verified against primary sources; each operator's
``rationale`` is what the agent is told, and it is also what a judge sees in the
provenance record next to the diff.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .fitness import Score
from .telemetry import Trace


@dataclass(frozen=True)
class Operator:
    name: str
    rationale: str
    instruction: str
    #: Log signature that makes this operator worth trying. Purely a prior for
    #: the bandit — it never hard-gates the choice, because the point of the
    #: search is to find levers a human would not have picked.
    indicated_by: str = ""

    def prompt(self, *, game_path: str, brief: str) -> str:
        return MUTATION_PROMPT.format(
            game_path=game_path,
            operator=self.name,
            rationale=self.rationale.strip(),
            instruction=self.instruction.strip(),
            brief=brief.strip(),
        )


#: The task Devin receives. It deliberately does not describe the game's
#: internals: the agent reads the file. What it does pin down is the contract,
#: the safety rules and how the work will be judged, because those are the
#: things a mutation must not silently break.
MUTATION_PROMPT = """\
You are one candidate in an evolutionary search over an educational game's source
code. Your job: apply ONE pedagogical change to `{game_path}` and nothing else.

## Evidence from the child's most recent session

{brief}

## Your assigned mutation operator: {operator}

{rationale}

Concretely: {instruction}

## Hard constraints (a candidate that breaks one is discarded unscored)

1. `window.orbit` must keep exposing `observe()`, `drainEvents()` and `isOver()`
   with unchanged semantics. An automated harness plays your candidate in a real
   browser through those three functions only.
2. `observe()` must keep returning `problem`, `cursor`, `number_line_max`,
   `awaiting_input` and `hint_visible`, and the page must keep the `#land` and
   `#hint` controls working by keyboard and mouse.
3. No countdown timers, no lives, no score loss, no animation faster than 3 Hz,
   no red-flash punishment for a wrong answer.
4. Single file, no new dependencies, no network calls, no build step.
5. Do not change the difficulty ladder's *labels* or the emitted event names —
   the harness and the learner model are keyed on them.

## How you will be scored

`python -m orbit.cli evaluate {game_path} --seeds 1,2,3` runs the simulated
cohort in headless Chromium and prints gate results plus a fitness score that
rewards difficulty-weighted mastery gain and engagement and penalises drift away
from an ~85% success rate. Run it before you finish; if the gates fail, fix the
candidate rather than reporting a failure.

Report, in your final message: the one-line description of what you changed, the
JSON block printed by the evaluator, and one sentence on the mechanism you
expect to move the score.
"""


OPERATORS: tuple[Operator, ...] = (
    Operator(
        name="calibrate_difficulty",
        rationale=(
            "Learning rate peaks near an ~85% success rate for this class of "
            "two-choice-ish tasks (Wilson et al., Nat. Commun. 2019, "
            "doi:10.1038/s41467-019-12552-4). The observed success rate is off "
            "target, so the item selection is mis-calibrated for this learner."
        ),
        instruction=(
            "change how the next item's difficulty is chosen — the ladder "
            "thresholds, the window it averages over, or the mix of tiers it "
            "samples from — so the achieved success rate moves toward 85%"
        ),
        indicated_by="success rate far from 0.85",
    ),
    Operator(
        name="reduce_extraneous_load",
        rationale=(
            "Working memory is the binding constraint; effort spent on the "
            "interface is effort not spent on the arithmetic (Sweller, "
            "Cognitive Architecture and Instructional Design, "
            "doi:10.1023/A:1022193728205)."
        ),
        instruction=(
            "remove or simplify something the learner must hold in mind or "
            "hunt for: redundant on-screen text, split attention between the "
            "problem and the number line, decoration that competes with the "
            "item, or an input path that takes more steps than it needs"
        ),
        indicated_by="high extraneous-load fraction or long latencies",
    ),
    Operator(
        name="strengthen_scaffold",
        rationale=(
            "A wrong answer should buy an explanation, not a penalty. Worked "
            "decomposition on error keeps the item within reach without "
            "removing the difficulty that produces learning."
        ),
        instruction=(
            "improve what happens after a wrong answer — decompose the item, "
            "show the operation concretely on the number line, or fade the "
            "support as the learner succeeds — without adding time pressure"
        ),
        indicated_by="long wrong-answer streaks",
    ),
    Operator(
        name="change_representation",
        rationale=(
            "The same arithmetic can be posed symbolically, as grouped objects, "
            "or as movement along a line; which representation a learner can "
            "act on is an empirical question about that learner, not a "
            "preference."
        ),
        instruction=(
            "change how items are presented (symbolic / dot groups / pure "
            "number-line motion), or make the representation adapt to the "
            "learner's recent accuracy on that skill"
        ),
        indicated_by="hint dependence concentrated in one skill",
    ),
    Operator(
        name="interleave_and_space",
        rationale=(
            "Blocked practice inflates in-session performance and depresses "
            "retention; interleaving and spacing are desirable difficulties "
            "(Bjork & Bjork, 2011)."
        ),
        instruction=(
            "interleave skills instead of blocking them, and re-surface a skill "
            "some items after it was last practised rather than immediately"
        ),
        indicated_by="mastery gain flat despite high success rate",
    ),
    Operator(
        name="reduce_gaming_affordance",
        rationale=(
            "Systematic fast guessing and hint-farming are the software being "
            "exploited rather than used (Baker, gaming-the-system work). The fix "
            "is to change the affordance, not to punish the child."
        ),
        instruction=(
            "make guessing less rewarding and thinking more so — e.g. require "
            "the answer to be committed deliberately, make the hint teach "
            "rather than reveal, or make repeated rapid wrong answers trigger "
            "instruction instead of a retry"
        ),
        indicated_by="high fast-guess or hint rate",
    ),
    Operator(
        name="re_engage_after_idle",
        rationale=(
            "Off-task time is measurable from logs alone (Baker, CHI 2007) and "
            "is lost learning time; the recovery has to be inviting rather than "
            "alarming for a learner with executive-function load."
        ),
        instruction=(
            "add a non-punitive way back in after an idle gap — a quieter item, "
            "a gentle prompt, a resumable state — with no countdown and no "
            "penalty for having paused"
        ),
        indicated_by="off-task ticks or abandonment",
    ),
)

BY_NAME = {operator.name: operator for operator in OPERATORS}


def brief(trace: Trace, score: Score) -> str:
    """The evidence block handed to the agent: what this child actually did.

    Everything here is measured. No invented confidence numbers, no diagnosis —
    the agent gets the same statistics the fitness function gets.
    """
    from . import engagement as engagement_module

    signals = engagement_module.measure(trace)
    attempts = trace.attempts
    per_skill: dict[str, list[bool]] = {}
    for attempt in attempts:
        per_skill.setdefault(attempt.skill, []).append(attempt.correct)

    lines = [
        f"- items attempted: {len(attempts)} over {trace.duration_ms / 1000:.0f}s"
        f" ({'abandoned' if trace.abandoned else 'completed'})",
        f"- success rate: {score.success_rate:.0%} (target ~85%)",
        f"- difficulty-weighted mastery gain: {score.mastery_gain_per_min:.3f}/min",
        f"- engaged fraction: {signals.engaged_fraction:.0%},"
        f" off-task gaps: {signals.off_task_ticks}",
        f"- median latency: {signals.median_latency_ms:.0f}ms,"
        f" fast wrong answers: {signals.fast_guess_rate:.0%}",
        f"- hint rate: {signals.hint_rate:.0%},"
        f" longest wrong streak: {signals.max_wrong_streak}",
        f"- current fitness: {score.total:.3f}",
    ]
    for skill, outcomes in per_skill.items():
        correct = sum(outcomes)
        lines.append(f"- {skill}: {correct}/{len(outcomes)} correct")
    return "\n".join(lines)


def indications(trace: Trace, score: Score) -> dict[str, float]:
    """Prior weight per operator from the trace, in [0, 1]. Never a hard filter."""
    from . import engagement as engagement_module

    signals = engagement_module.measure(trace)
    return {
        "calibrate_difficulty": min(1.0, score.difficulty_penalty),
        "reduce_extraneous_load": min(1.0, score.extraneous_load),
        "strengthen_scaffold": min(1.0, signals.max_wrong_streak / 5.0),
        "change_representation": min(1.0, signals.hint_rate),
        "interleave_and_space": (
            1.0 if score.success_rate > 0.9 and score.mastery_gain_per_min < 0.5 else 0.2
        ),
        "reduce_gaming_affordance": signals.gaming_proxy,
        "re_engage_after_idle": (
            1.0 if trace.abandoned else min(1.0, 1.0 - signals.engaged_fraction)
        ),
    }


def choose(names: Sequence[str]) -> list[Operator]:
    return [BY_NAME[name] for name in names]
