"""Thief decision layer: max-survival evasion, rule-46 taboo, rule-47 concession (§4.4).

Pure function of (board knowledge, tracker estimate, params) — no I/O, no LLM. On the bare board
the solver's evasion holds the invariant "end every move at distance >= 2 from the cop" forever;
barriers erode it, and then every extra step of capture distance is clock run toward 35.
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


def _landings(board: Board, thief: Coord) -> list[Coord]:
    return [destination(thief, t) for t in legal_move_tokens(board, thief)]


def _pick(
    board: Board, cop: Coord, thief: Coord, params: StrategyParams
) -> Coord:
    """Max-survival landing with the rule-46 taboo: never end adjacent to the cop if avoidable."""
    candidates = [c for c in _landings(board, thief) if c != cop]
    danger = set(board.open_neighbors(cop)) | {cop}
    safe = [c for c in candidates if c not in danger]
    pool = safe if safe else candidates

    def value(cell: Coord) -> tuple[float, int, int, int]:
        r = solver.steps_to_capture(board, cop, cell, thief_to_move=False)
        v = float("inf") if r is None else float(r)
        return (v, len(board.open_neighbors(cell)), -cell[0], -cell[1])

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
    """The thief's turn under a belief map: maximize expected distance, keep escape routes."""
    if is_rule47_boxed(board, thief):
        return ThiefAction("concede", claim_response=concession_payload(thief))
    argmax_cell = max(posterior.items(), key=lambda kv: (kv[1], kv[0]))[0]
    danger = set(board.open_neighbors(argmax_cell)) | {argmax_cell}

    def value(cell: Coord) -> tuple[int, float, int, int, int]:
        dist = bfs_distances(board, cell)
        expected = sum(p * dist.get(c, board.size * 2) for c, p in posterior.items())
        degree = len(board.open_neighbors(cell))
        return (int(cell not in danger), expected, degree, -cell[0], -cell[1])

    best = max(_landings(board, thief), key=value)
    return ThiefAction("move", move_token=token_between(thief, best))
