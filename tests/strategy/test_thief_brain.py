"""Thief brain: taboo, concession, survival through the brain, fuzzy evasion (PRD-3)."""

import pytest

from cosmos77_thief.engine.board import Board
from cosmos77_thief.engine.rules import apply_move, destination, legal_move_tokens
from cosmos77_thief.strategy import solver
from cosmos77_thief.strategy.params import StrategyParams
from cosmos77_thief.strategy.thief_brain import answer_claim, decide_exact, decide_fuzzy

PARAMS = StrategyParams()


@pytest.fixture(autouse=True)
def _fresh_cache():
    solver.clear_cache()
    yield
    solver.clear_cache()


def test_boxed_thief_concedes_with_its_own_cell():
    b = Board(7)
    b.add_barrier((0, 1))
    b.add_barrier((1, 0))
    action = decide_exact(b, (0, 0), (5, 5), PARAMS)
    assert action.kind == "concede"
    assert action.claim_response == {"claim": [0, 0], "caught": True}


def test_never_ends_adjacent_to_the_cop_when_avoidable():
    b = Board(7)
    for cop, thief in [((3, 5), (3, 3)), ((0, 2), (2, 2)), ((6, 6), (5, 5))]:
        action = decide_exact(b, thief, cop, PARAMS)
        assert action.kind == "move"
        dest = destination(thief, action.move_token)
        assert dest != cop
        assert dest not in b.open_neighbors(cop)


def test_forced_adjacency_still_moves_legally():
    b = Board(7)
    for cell in [(0, 2), (1, 2), (1, 1), (1, 0)]:
        b.add_barrier(cell)
    action = decide_exact(b, (0, 0), (0, 1), PARAMS)
    assert action.kind == "move"


def _greedy_step(b: Board, cop, thief):
    def rank(token):
        dest = destination(cop, token)
        return (abs(dest[0] - thief[0]) + abs(dest[1] - thief[1]), token)

    return apply_move(b, cop, min(legal_move_tokens(b, cop), key=rank))


def test_survives_35_steps_vs_optimal_cop_through_the_brain():
    b = Board(7)
    cop, thief = (0, 0), (3, 3)
    for step in range(35):
        action = decide_exact(b, thief, cop, PARAMS)
        assert action.kind == "move", f"conceded at step {step}"
        thief = apply_move(b, thief, action.move_token)
        assert thief != cop and thief not in b.open_neighbors(cop), f"capturable at {step}"
        move = solver.best_cop_move(b, cop, thief)
        cop = move[0] if move is not None else _greedy_step(b, cop, thief)
        assert cop != thief, f"captured at step {step}"


def test_in_trap_maximizes_capture_time():
    b = Board(7)
    for col in range(7):
        b.add_barrier((1, col))
    cop, thief = (0, 6), (0, 2)
    action = decide_exact(b, thief, cop, PARAMS)
    dest = destination(thief, action.move_token)
    best_dest, _ = solver.best_thief_move(b, cop, thief)
    v_chosen = solver.steps_to_capture(b, cop, dest, thief_to_move=False)
    v_best = solver.steps_to_capture(b, cop, best_dest, thief_to_move=False)
    assert v_chosen == v_best


def test_fuzzy_flees_the_posterior_mass():
    posterior = {(0, 0): 0.7, (0, 1): 0.3}
    action = decide_fuzzy(Board(7), (2, 2), posterior, PARAMS)
    dest = destination((2, 2), action.move_token)
    assert dest[0] + dest[1] > 2 + 2 - 1


def test_answer_claim_is_always_truthful():
    assert answer_claim((3, 3), (3, 3)) == {"claim": [3, 3], "caught": True}
    assert answer_claim((3, 3), (2, 3)) == {"claim": [2, 3], "caught": False}
