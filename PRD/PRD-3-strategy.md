# PRD-3 — Strategy module: retrograde solver, tracker, thief brain (book ch. 6 · stage 3)

## Goal

Moves that are **provably pure Python** (rule 25 — we bind the recommendation as a hard rule) and
league-winning from the evasion side: the same retrograde solver as the cop repo (exact per
barrier configuration), the same scent-inversion tracker, and a thief brain that converts the
board's provable thief-win property into a guaranteed 35-step survival — plus the honest
concession the rules demand when survival is lost.

## Scope

**In:** `strategy/solver.py` (retrograde value + optimal move for both roles — identical algorithm
to the cop repo), `strategy/tracker.py` (exact + degraded cop-position estimation),
`strategy/thief_brain.py` (max-survival evasion + rule-46 taboo + rule-47 self-check/concession),
`belief/bayes.py` (physics-constrained posterior when no grid is transmitted). Brains are pure
functions of (config, tracker state, engine state).

**Out:** hint generation (PRD-4), any network or LLM call — nothing in `strategy/` may import them.

## Game-theory ground truth (shapes every decision here)

The bare 4-neighbor 7×7 grid is **NOT cop-win for one cop**: C4 is a retract of the grid and
c(C4)=2, so the cop number is ≥2. Playing the solver's evasion, this thief survives 35 steps
against ANY single cop on the bare board — **survival is a provable floor, not a hope**. The
invariant: end every thief move at graph distance ≥2 from the cop. Barriers erode the invariant's
space, so the brain must also maximize capture *time* when the solver's value turns finite —
every extra step is the clock running toward 35.

## Binding rules implemented

| Rule | Requirement | Where |
|---|---|---|
| 25 | LLM never decides movement | `strategy/` has no LLM import; CI greps for it |
| 21, 22 | Truthful claim responses | `claim_response` computed from engine ground truth; a co-location claim naming our true cell is always answered `caught: true` |
| 46 | Barrier-onto-our-cell = capture | the **rule-46 taboo**: never end a move within graph distance 1 of the known cop unless no legal alternative exists (adjacent = capturable by barrier finisher on the cop's turn) |
| 47 | Boxed-in = captured, and it must be SAID | per-turn self-check; on capture the brain emits the concession signal (own final cell, verdict `settled`) — silence is the rule-35 double-zero shape |
| Playbook §4.1 | Tracker: argmax inversion of the cop's transmitted grid = its exact cell; degraded mode = liar-score-weighted Bayesian posterior | `tracker.py` confidence ∈ {exact, fuzzy} |
| Playbook §4.4 | Evasion policy | solver's max-survival move when tracking is exact; prefer high-escape-degree cells (≥2 disjoint escape paths) and central corridors early; run the clock — 35 steps is the whole job |

## Solver requirements

Identical to the cop repo's (vendor-synced technique, not shared state): (cop, thief, mover) per
barrier set, ≤4802 states, retrograde solve <100 ms, memoized per barrier-set hash, **enlarged
capture set** (co-location OR thief adjacent with cop to move = rule-46 finisher). Returns
`steps_to_capture` (∞ while evasion holds), optimal moves for both roles — the thief-optimal move
maximizes capture distance / holds the invariant.

## Acceptance criteria

- [ ] Empty 7×7 board: solver returns ∞ for the cop (thief-win confirmed — the C4-retract check).
- [ ] Solver-evading thief survives 35 steps vs ANY scripted cop (greedy, random, solver-pursuit)
      on the bare board — the provable-floor property test.
- [ ] Rule-46 taboo: across seeded games, the thief never ends adjacent to the known cop when a
      legal alternative exists (violation = test failure).
- [ ] With a hand-built corner trap the solver's value is finite and the brain still maximizes
      capture time (monotone: chosen move's value ≥ every alternative's).
- [ ] Rule-47 self-check fires on exactly the boxed states (cross-checked brute-force) and emits
      the concession payload once, with our true final cell.
- [ ] Tracker exact mode recovers the emitter cell on synthetic grids 100%; degraded posterior
      never puts mass on physics-impossible cells.
- [ ] Solver idempotent under barrier recompute; <100 ms per solve (measured in test).

## Test plan

`tests/strategy/test_solver.py` (empty-board ∞, trap finiteness, rule-46 radius states, timing,
memo idempotence — same suite shape as the cop repo), `test_tracker.py` (synthetic emissions,
two-frame deltas, degraded invariants), `test_thief_brain.py` (35-step survival vs the three
scripted cops, seeded; taboo sweep; boxed-state concession matrix; max-capture-time monotonicity),
`tests/belief/test_bayes.py`. All seeded/deterministic; property sweeps over random barrier sets
≤14.

## Dependencies / phase mapping

Implements playbook **Phase 3**. Depends on PRD-1 (engine states). Feeds PRD-4 (tracker posterior
is the GUI heatmap + hint context) and the series driver (PRD-7).
