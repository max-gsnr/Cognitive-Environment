# Orbit

Orbit evolves an educational game's **source code** against evidence from one child's play.
Devin sessions are the mutation operator; a headless browser is the fitness evaluator.

```
child plays games/orbit/index.html
        │  window.orbit telemetry (typed attempts)
        ▼
learner model (constrained BKT) + log-based engagement
        │  brief: what is wrong, for this learner, with numbers
        ▼
UCB bandit picks a mutation operator, archive samples a parent per island
        │  one real Devin session per (parent, operator), in parallel
        ▼
each session rewrites the game and pushes a branch
        │  candidate source pulled from that branch
        ▼
novelty check → safety gates → 4 simulated learners × N seeds in Chromium
        │  difficulty-weighted fitness
        ▼
archive + provenance: session → prompt → branch → gate result → fitness → lineage
```

## Why the browser is the evaluator

A Python simulator can only read a config object, which would make the search space five
numbers and Devin decorative. The evaluator here never reads the source it scores: it
navigates the page, presses arrow keys, clicks, and drains telemetry. A candidate may
rewrite mechanics, rendering, input handling or scaffolding and remain evaluable as long as
it keeps three functions:

```js
window.orbit.observe()      // what a player can see right now
window.orbit.drainEvents()  // telemetry since the last drain
window.orbit.isOver()       // session finished
```

Wall-clock cost stays at ~3.5 s per rollout because Playwright's controllable clock
(`page.clock`) advances *game* time through deliberation and cooldowns.

## Fitness, and the failure mode it exists to avoid

The naive objective — mastery gain per minute — is maximised by a game where every item is
trivial and answered instantly, which inverts the pedagogy. So the score is

```
w1 · difficulty-weighted mastery gain per minute   (BKT posterior − fitted prior)
+ w2 · engaged fraction                            (log-based, Baker-style)
− w3 · abandonment
− w4 · extraneous load                             (time not spent deliberating)
− w5 · |success rate − 0.85| / 0.85                (Wilson et al. 2019)
```

`tests/test_fitness.py` is the guard: if a change makes the trivial game beat the
sweet-spot game, the search is broken and no amount of agent time fixes it. Mastery is
divided by a fixed reference session length, so a candidate cannot win by ending early.

## Gates are not part of the score

An optimiser games its objective, so the things that must never happen to a child are
checked separately and are not weighted against anything: animation faster than 3 Hz,
countdown timers, a missing evaluation contract, JavaScript errors, and every simulated
learner abandoning. A gate failure sets fitness to `-inf` regardless of the metrics.

Source scans ignore comments, so a candidate that *documents* the ban is not punished for
naming it.

## Learner model

Constrained BKT: guess and slip are fixed, only `L0` and the transition probability are
fitted, because four free parameters on a handful of observations are not identifiable
(Beck & Chang 2007). Output is a calibration table with `n` per bin and a bootstrap Brier
interval — deliberately not an AUC, which over ~8 binary outcomes is noise.

## Cloud first, local as fallback

Every step runs on a fresh machine — a Devin VM, CI, or a laptop:

```bash
scripts/setup-orbit.sh                      # venv, deps, Chromium, tests

# evaluate a deployed candidate (the cloud path)
python -m orbit.cli evaluate https://host/orbit/index.html --seeds 1,2 --out report.json

# or serve and evaluate locally (the fallback path)
python scripts/serve.py --port 8000 &
python -m orbit.cli evaluate http://127.0.0.1:8000/orbit/index.html
python -m orbit.cli evaluate games/orbit/index.html   # straight off disk
```

`evaluate` exits non-zero when a gate fails, so a Devin mutation session can score its own
candidate before reporting back and sees the same numbers the orchestrator will use.

## Running an evolution

Needs real credentials; there is no mock path, because a mocked mutation operator would
make the whole result meaningless:

```bash
export DEVIN_API_KEY=...        # never committed
export DEVIN_ORG_ID=org-...   # optional; only the v3 endpoints are org-scoped
python -m orbit.cli evaluate games/orbit/index.html --seeds 1 --record child.json
python -m orbit.cli evolve \
  --repo max-gsnr/Cognitive-Environment \
  --base-branch devin/1787500000-orbit-game \
  --trace child.json --generations 1 --islands 2 --max-acu 8
```

Without `DEVIN_API_KEY` the command exits 3 and explains why.

The client tries the org-scoped v3 session endpoints and falls back to v1 when they answer
403 — which is what a user-scoped `apk_user_…` key gets. Both create real sessions; pin one
with `DEVIN_API_VERSION`. One caveat: v1's session payload carries no `acus_consumed`, so on
that path the recorded ACUs are 0 while `--max-acu` still caps every session.

A verified live run (1 generation, 1 island, `--max-acu 8`) went: session
`devin-1605a2d1cab64c00b1d46b748fe93738` edited the game on
`orbit/gen1-strengthen_scaffold-43148a` (persistent worked decomposition on the number line),
the orchestrator fetched that branch, gates passed, and headless Chromium scored it 0.861
against the seed's 0.656 — so it was promoted. (Both numbers come from that one run, under
scoring that predates rollouts recording a learner's quit; absolute values are lower now that
the abandonment penalty actually fires, the comparison is unaffected.)

Output is `.orbit/provenance.json`: per-generation ACUs, every candidate with its operator,
Devin session id, gate failures and metrics, the bandit's posterior over operators, and the
lineage from seed to promoted candidate.

## Mutation operators

Seven named operators, each with a research rationale and a prompt that tells the session
what evidence motivated it (`orbit/operators.py`). The bandit is UCB over these, re-priored
each generation from the child's newest trace, so an operator that is irrelevant to *this*
learner is not spent on. Untried operators are tried before any repeat.

## Module map

| Module | Role |
| --- | --- |
| `orbit/telemetry.py` | typed `Attempt` / `Trace` over the raw event stream |
| `orbit/learner.py` | constrained BKT, calibration, bootstrap Brier |
| `orbit/engagement.py` | log-based engagement and a bounded gaming proxy |
| `orbit/fitness.py` | the objective, plus its anti-trivial guard |
| `orbit/policy.py` | four seeded simulated learners |
| `orbit/rollout.py` | real Chromium play, local file or deployed URL |
| `orbit/gates.py` | model-independent safety and contract checks |
| `orbit/operators.py` | mutation operators and their prompts |
| `orbit/bandit.py` | UCB over operators |
| `orbit/archive.py` | islands, novelty rejection, parent sampling, lineage |
| `orbit/devin.py` | Devin API client, v3 with a v1 fallback (standard library only) |
| `orbit/evolve.py` | the loop and the provenance record |

## Sources

- Wilson et al., *Eighty-Five Percent Rule*, Nat. Commun. 2019 — doi:10.1038/s41467-019-12552-4
- Corbett & Anderson, *Knowledge Tracing*, UMUAI 1995 — doi:10.1007/BF01099821
- Beck & Chang, *Identifiability of student models*, UM 2007
- Baker et al., gaming-the-system and off-task detectors from interaction logs
- Siegler & Ramani linear number board games; 2025 meta-analysis — doi:10.3102/00346543251383552
- Wilson et al., *The Number Race*, 2006 — PMID 16734906
- Calcularis / number-line training — doi:10.3389/fpsyg.2020.01115
- Sweller, cognitive load — doi:10.1023/A:1022193728205
- AlphaEvolve (DeepMind, 2025); ShinkaEvolve (Sakana AI) — LLM-driven program evolution
