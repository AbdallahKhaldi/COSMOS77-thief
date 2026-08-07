# PRD-1 — Base Logic: board physics, endings, scoring (book ch. 3 · build stage 1)

## Goal

A deterministic, fully-tested game engine that runs a complete pursuit in a **single process with
zero I/O**: board, legal movement, barriers, all three capture families, survival, and the fixed
scoring table. Every later layer (strategy, net, crypto, GUI) consumes this engine; nothing in it
may depend on them.

## Scope

**In:** `engine/board.py` (grid + barrier set from config), `engine/rules.py` (legal-move
generation), `engine/capture.py` (ending detection), `engine/subgame.py` (turn sequencing, step
ceiling, outcome row). All tunables read from `config/game.json` — never constants in code.

**Out:** networking, LLM, scent transmission (the scent *model* lives in vendored `protocol/scent.py`,
PRD-6), GUI, artifacts. The engine never knows an opponent exists as a process.

## Binding rules implemented (App. E numbering · playbook §0–§2)

| Rule | Requirement | Engine behavior |
|---|---|---|
| 13, 14 | Orthogonal moves only; no diagonals | Move set = N/S/E/W/STAY; diagonal or >1-step deltas rejected as illegal |
| 12 | Minimums only raisable | Config loader refuses `board_size<7`, `barriers_max<14`, `max_steps<35` |
| 15, 16 | Barrier placement openly and truthfully declared | The opponent's declarations are ingested verbatim into our barrier set; our audit layer later cross-checks them |
| 46 | Barrier onto the thief's current cell = capture | `capture.py` family 2 |
| 47 | Thief with no legal move = captured (STAY does not rescue a fully-boxed thief) | `capture.py` family 3 |
| 21, 22 | Capture claims truthful only | Engine exposes ground truth so the claim_response is always honest |
| 48 | Fixed scoring: capture 20/5 · survival 10/5 · technical 0/0 | Outcome table derived from config; zeroed rows are sanctions: `tie: false`, `winner_group: null` |
| Playbook §1 | 7×7 default, `(row, col)` top-left 0-indexed, thief [3,3] cop [0,0], quota 14, ceiling 35 | Constructor + validators |

Thief-relevant mechanics owned here: the barrier set grows only from the cop's public
declarations; survival triggers exactly at the `max_steps` ceiling; rule-46/47 detection runs on
**our own** state every turn because those endings are visible only to us.

## Role emphasis (this repo)

The thief engine drives **self-detection and the concession duty**: after every move and every
inbound barrier declaration it must answer "am I captured under rule 46 or boxed in under
rule 47?" — and when the answer is yes, expose the exact final cell so the wire layer can say so
(`claim_response: {"claim": [our cell], "caught": true}`, verdict `settled`). Staying silent turns
a legal capture into the rule-35 contradictory-report shape that zeroes both teams. The mirrored
cop repo exercises the same engine from the placement/claim side.

## Acceptance criteria

- [ ] A scripted 35-step pursuit runs to survival with zero exceptions; a scripted capture ends the
      sub-game the move it happens.
- [ ] Diagonal, >1-step, off-board, and into-barrier moves are rejected; STAY always legal unless
      the mover's cell is irrelevant to legality (STAY never escapes rule 47).
- [ ] Inbound barrier declarations extend the barrier set exactly once each, permanently; a
      declaration landing on our current cell yields rule-46 capture immediately.
- [ ] Rule 47: with every orthogonal neighbor barrier/off-board we are captured even though STAY is
      geometrically possible; with ≥1 open neighbor we are not — verified against brute-force
      reachability for every cell × barrier pattern ≤3 nearby.
- [ ] The engine surfaces the concession payload (final cell + settled verdict) for both rule-46
      and rule-47 endings.
- [ ] Outcome rows byte-match the fixed table incl. the zeroed-sanction shape.
- [ ] Config with a lowered minimum (board 6, quota 13, ceiling 34) is refused at load.
- [ ] Coverage ≥85% on `engine/`; ruff clean; every file ≤150 lines; zero I/O imports in `engine/`.

## Test plan

`tests/engine/test_board.py` (construction, barrier ingestion, config minimums), `test_rules.py`
(exhaustive move-legality matrix over edge/corner/barrier-adjacent cells), `test_capture.py`
(all three families + rule-46-on-our-cell + boxed-corner and boxed-center rule-47 cases +
concession payload shape), `test_subgame.py` (step ceiling, survival at 35, outcome rows). All
tests seeded and deterministic; no network, no clock, no LLM.

## Dependencies / phase mapping

Implements playbook **Phase 2**. Requires only `config/game.json` (constitution defaults, §1).
Consumed by PRD-3 (solver reads engine states), PRD-2 (net drives subgame), PRD-6 (audit replays
physics), PRD-7 (GUI renders local state).
