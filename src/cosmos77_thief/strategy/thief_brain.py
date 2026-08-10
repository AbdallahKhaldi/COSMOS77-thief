"""Thief decision layer: max-survival evasion, rule-46 taboo, rule-47 concession (§4.4).

Pure function of (board knowledge, tracker estimate, params) — no I/O, no LLM. On the bare board
the solver's evasion holds the invariant "end every move at distance >= 2 from the cop" forever;
barriers erode it, and then every extra step of capture distance is clock run toward 35.

Under barriers the solver value is infinite for essentially every candidate, so it cannot rank
them: what does is ESCAPE ROOM — the cells reachable within a bounded horizon. The UNBOUNDED
component size cannot, because every landing is one step from the thief and therefore lies in the
thief's own component; that term is identically flat and decides nothing (measured).
"""

from __future__ import annotations

from dataclasses import dataclass

from ..engine.board import Board, Coord
from ..engine.capture import concession_payload, is_rule47_boxed
from ..engine.rules import destination, legal_move_tokens, token_between
from . import jitter, solver
from .params import StrategyParams
from .pathing import bfs_distances


@dataclass(frozen=True)
class ThiefAction:
    """One thief turn: a move, or the obligatory concession when rule 46/47 already ended it."""

    kind: str
    move_token: str | None = None
    claim_response: dict[str, object] | None = None


def answer_claim(thief: Coord, claimed: Coord) -> dict[str, object]:
    """The truthful answer to a cop capture claim (rules 21-22): echo the cell, admit iff there."""
    return {"claim": [claimed[0], claimed[1]], "caught": thief == claimed}


def escape_room(distances: dict[Coord, int], horizon: int) -> int:
    """Cells reachable within *horizon* moves — the room a landing actually buys."""
    return sum(1 for d in distances.values() if d <= horizon)


def taboo_cells(board: Board, cop: Coord, radius: int) -> set[Coord]:
    """The rule-46 no-land zone: every cell within *radius* steps of the cop (params-driven)."""
    return {cell for cell, d in bfs_distances(board, cop).items() if d <= radius}


def _landings(board: Board, thief: Coord) -> list[Coord]:
    return [destination(thief, t) for t in legal_move_tokens(board, thief)]


def _pick(
    board: Board, cop: Coord, thief: Coord, params: StrategyParams
) -> Coord:
    """Max-survival landing under the rule-46 taboo: never end inside the radius if avoidable."""
    candidates = [c for c in _landings(board, thief) if c != cop]
    danger = taboo_cells(board, cop, params.taboo_distance)
    safe = [c for c in candidates if c not in danger]
    pool = safe if safe else candidates

    def value(cell: Coord) -> tuple[float, int, int, int, int]:
        r = solver.steps_to_capture(board, cop, cell, thief_to_move=False)
        v = float("inf") if r is None else float(r)
        room = escape_room(bfs_distances(board, cell), params.escape_horizon)
        return (v, room, len(board.open_neighbors(cell)), -cell[0], -cell[1])

    return jitter.pick_max(pool, key=lambda c: value(c)[:2], legacy=value)


def decide_exact(
    board: Board, thief: Coord, cop: Coord, params: StrategyParams
) -> ThiefAction:
    """The thief's turn against an exactly-tracked cop."""
    if is_rule47_boxed(board, thief):
        return ThiefAction("concede", claim_response=concession_payload(thief))
    return ThiefAction("move", move_token=token_between(thief, _pick(board, cop, thief, params)))


def decide_fuzzy(
    board: Board, thief: Coord, posterior: dict[Coord, float], params: StrategyParams
) -> ThiefAction:
    """The thief's turn under a belief map: keep ROOM and the centre, then maximize distance.

    Distance-maximisation alone walks straight into a corner — the cheapest place on the board
    for a cop to convert with barrier surgery — so room and centrality both outrank it (§4.4.2,
    "central corridors early"). Measured over 48 starts: rim occupancy 0.89 -> 0.02.
    """
    if is_rule47_boxed(board, thief):
        return ThiefAction("concede", claim_response=concession_payload(thief))
    argmax_cell = max(posterior.items(), key=lambda kv: (kv[1], kv[0]))[0]
    danger = taboo_cells(board, argmax_cell, params.taboo_distance)
    mid = (board.size - 1) / 2

    def value(cell: Coord) -> tuple[int, int, float, float, int, int, int]:
        dist = bfs_distances(board, cell)
        expected = sum(p * dist.get(c, board.size * 2) for c, p in posterior.items())
        central = -(abs(cell[0] - mid) + abs(cell[1] - mid))
        room = escape_room(dist, params.escape_horizon)
        degree = len(board.open_neighbors(cell))
        return (int(cell not in danger), room, central, expected, degree, -cell[0], -cell[1])

    best = jitter.pick_max(_landings(board, thief), key=lambda c: value(c)[:3], legacy=value)
    return ThiefAction("move", move_token=token_between(thief, best))
