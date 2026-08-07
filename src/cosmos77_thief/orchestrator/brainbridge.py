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

    def note_opponent_turn(self, state: TurnState, kit: SideKit, hint: str) -> None:
        """Advance the belief one cop move and fold in liar-weighted hint evidence.

        The factor maps the liar-score onto [0.5, 1.5]: a caught liar's claimed region is
        DISFAVORED, an honest opponent's favored, an uncalibrated one ignored.
        """
        self.belief.diffuse()
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
