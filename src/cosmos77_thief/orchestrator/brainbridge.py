"""Bridge from live tracked knowledge to THIS repo's brain (the thief; pure Python, rule 25)."""

from __future__ import annotations

from ..belief.bayes import BeliefMap
from ..engine.board import Coord
from ..hints.liar_score import direction_matches, hinted_direction
from ..strategy.params import StrategyParams
from ..strategy.thief_brain import ThiefAction, decide_exact, decide_fuzzy
from ..strategy.tracker import EXACT
from .turnstate import SideKit, TurnState

ROLE = "thief"


class BrainBridge:
    """Per-sub-game decision wiring: tracker first, belief fallback, honest concessions."""

    def __init__(self, state: TurnState, params: StrategyParams | None = None) -> None:
        """Seed the belief map at the cop's constitution start cell."""
        self.params = params or StrategyParams()
        self.belief = BeliefMap(state.board, state.cfg.cop_start)
        self.my_last_claim: Coord | None = None

    def note_opponent_turn(self, state: TurnState, kit: SideKit, wire: dict) -> None:
        """Fold one cop turn into the belief map.

        A declared barrier is EXACT evidence, and the strongest channel we have when no scent
        grid is transmitted: rule 15 makes placements public and truthful, and a placement is
        only legal on the cop's own cell or a 4-neighbour — so the cop is certainly inside that
        five-cell set. Placement also replaces movement, so that turn the cop did not move and
        the belief must NOT diffuse. Hints stay soft, weighted by the liar-score onto [0.5, 1.5].
        """
        placed = wire.get("barrier_placed")
        if isinstance(placed, list) and len(placed) == 2:
            cell = (int(placed[0]), int(placed[1]))
            pinned = {cell, *state.board.neighbors4(cell)}
            self.belief.condition_only(pinned)
        else:
            self.belief.diffuse()
        hint = str(wire.get("hint", ""))
        direction = hinted_direction(hint) if hint else None
        if direction is not None:
            grid = state.cfg.grid_size
            cells = {c for c in self.belief.posterior() if direction_matches(direction, c, grid)}
            if cells:
                self.belief.condition_region(cells, 0.5 + kit.liar.weight())

    def decide(self, state: TurnState, kit: SideKit) -> ThiefAction:
        """One thief turn from current knowledge (concede only when the rules demand it)."""
        cell, confidence = kit.tracker.estimate()
        if confidence == EXACT and cell is not None and state.board.in_bounds(cell):
            return decide_exact(state.board, state.my_pos, cell, self.params)
        return decide_fuzzy(state.board, state.my_pos, self.belief.posterior(), self.params)
