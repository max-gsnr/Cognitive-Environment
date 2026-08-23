"""``python -m orbit.cli evaluate games/orbit/index.html`` — score one candidate.

This is the command a Devin mutation session runs on its own candidate before
reporting back, so the agent sees the same numbers the orchestrator will use.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from . import gates, operators
from .archive import Archive, fitness_curve
from .bandit import Bandit
from .devin import DevinClient
from .evolve import GAME_PATH, DevinMutator, EvolutionRun
from .fitness import Weights, score_candidate
from .learner import LearnerModel, bootstrap_brier, calibration_bins
from .policy import COHORT
from .rollout import ContractError, evaluate_candidate_sync
from .telemetry import Trace


def _report(
    path: str, seeds: tuple[int, ...], record: Path | None = None
) -> dict[str, object]:
    started = time.perf_counter()
    try:
        results = evaluate_candidate_sync(path, seeds=seeds)
    except ContractError as error:
        return {"candidate": str(path), "gates": {"passed": False, "failures": [str(error)]}}

    traces = [result.trace for result in results]
    if record is not None:
        # A session log in the same shape the game emits, so an evolution run can
        # be seeded from a rollout when no child has played yet.
        record.parent.mkdir(parents=True, exist_ok=True)
        record.write_text(json.dumps(results[0].events, indent=2), encoding="utf-8")
    gate = gates.evaluate(path, results)
    score = score_candidate(traces, Weights())
    return {
        "candidate": str(path),
        "rollouts": len(results),
        "profiles": [profile.name for profile in COHORT],
        "wall_seconds": round(time.perf_counter() - started, 2),
        "seconds_per_rollout": round((time.perf_counter() - started) / len(results), 2),
        "gates": {"passed": gate.passed, "failures": gate.failures},
        "fitness": score.as_dict(),
        "learner_model": _calibration(traces),
    }


def _calibration(traces: list[Trace]) -> dict[str, object]:
    attempts = [attempt for trace in traces for attempt in trace.attempts]
    model = LearnerModel.fit(attempts)
    predictions = model.predict_sequence(attempts)
    outcomes = [attempt.correct for attempt in attempts]
    point, low, high = bootstrap_brier(predictions, outcomes)
    return {
        "n_attempts": len(attempts),
        "brier": round(point, 4),
        "brier_ci95": [round(low, 4), round(high, 4)],
        "calibration": calibration_bins(predictions, outcomes),
        "note": "illustrative fit; not a psychometric claim at this sample size",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="orbit")
    sub = parser.add_subparsers(dest="command", required=True)

    evaluate = sub.add_parser("evaluate", help="rollout, gate and score a candidate")
    evaluate.add_argument(
        "candidate",
        help="path to a candidate file, or the URL it is deployed at",
    )
    evaluate.add_argument("--seeds", default="1,2,3", help="comma-separated rollout seeds")
    evaluate.add_argument("--out", type=Path, help="also write the report here")
    evaluate.add_argument(
        "--record", type=Path, help="write the first rollout's raw event log here"
    )

    evolve = sub.add_parser(
        "evolve", help="fan out Devin sessions that mutate the game, then score them"
    )
    evolve.add_argument("--repo", required=True, help="owner/name the sessions work in")
    evolve.add_argument("--trace", type=Path, required=True, help="the child's session log")
    evolve.add_argument("--seed-game", type=Path, default=Path(GAME_PATH))
    evolve.add_argument(
        "--base-branch",
        default="main",
        help="branch the mutation sessions start from; the game must exist there",
    )
    evolve.add_argument("--generations", type=int, default=2)
    evolve.add_argument("--islands", type=int, default=2)
    evolve.add_argument("--max-acu", type=int, default=12, help="cap per Devin session")
    evolve.add_argument("--workdir", type=Path, default=Path(".orbit/candidates"))
    evolve.add_argument("--out", type=Path, default=Path(".orbit/provenance.json"))
    evolve.add_argument("--seeds", default="1,2,3")

    args = parser.parse_args(argv)
    if args.command == "evaluate":
        seeds = tuple(int(part) for part in args.seeds.split(",") if part.strip())
        report = _report(args.candidate, seeds, args.record)
        json.dump(report, sys.stdout, indent=2)
        sys.stdout.write("\n")
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        return 0 if report["gates"]["passed"] else 1  # type: ignore[index]
    if args.command == "evolve":
        return _evolve(args)
    return 2


def _evolve(args: argparse.Namespace) -> int:
    trace = Trace.from_events(json.loads(args.trace.read_text(encoding="utf-8")))
    client = DevinClient()
    if not client.configured:
        sys.stderr.write(
            "DEVIN_API_KEY is required (plus DEVIN_ORG_ID to use the v3 endpoints):"
            " the mutation operator is a real Devin session and is never mocked.\n"
        )
        return 3

    run = EvolutionRun(
        seed_path=args.seed_game,
        workdir=args.workdir,
        mutator=DevinMutator(
            client,
            repo=args.repo,
            game_path=str(args.seed_game),
            base_branch=args.base_branch,
            max_acu_limit=args.max_acu,
        ),
        archive=Archive(islands=args.islands),
        bandit=Bandit.over([operator.name for operator in operators.OPERATORS]),
        trace=trace,
        seeds=tuple(int(part) for part in args.seeds.split(",") if part.strip()),
    )
    best = run.run(generations=args.generations)
    path = run.write_provenance(args.out)

    json.dump(
        {
            "promoted": best.id if best else None,
            "fitness": best.fitness if best else None,
            "fitness_curve": fitness_curve(run.archive.candidates),
            "acus": round(sum(g.acus for g in run.generations), 2),
            "provenance": str(path),
        },
        sys.stdout,
        indent=2,
    )
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
