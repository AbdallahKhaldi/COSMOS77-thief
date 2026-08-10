"""The A2 evasion terms: bounded escape room, wired taboo radius, and no more corner-running.

The audit measured a thief that PARKED — one cell for 18 of 33 steps — because its value
function was flat at infinity everywhere and only raw degree discriminated; and a fuzzy thief
that spent 89% of its turns on the board rim because it maximised distance before anything else.
These pin both behaviours directly, not just through the survival sweep.
"""

import pytest

from cosmos77_thief.engine.board import Board
from cosmos77_thief.engine.rules import apply_move, destination
from cosmos77_thief.strategy import solver
from cosmos77_thief.strategy.params import StrategyParams
from cosmos77_thief.strategy.pathing import bfs_distances
from cosmos77_thief.strategy.thief_brain import decide_exact, decide_fuzzy, escape_room

PARAMS = StrategyParams()
RIM = {0, 6}


@pytest.fixture(autouse=True)
def _fresh_cache():
    solver.clear_cache()
    yield
    solver.clear_cache()


def test_escape_room_is_a_bounded_flood_not_the_whole_component():
    b = Board(7)
    assert escape_room(bfs_distances(b, (3, 3)), 0) == 1
    assert escape_room(bfs_distances(b, (3, 3)), 1) == 5
    open_room = escape_room(bfs_distances(b, (3, 3)), 3)
    corner_room = escape_room(bfs_distances(b, (0, 0)), 3)
    assert corner_room < open_room, "a corner must score less room than the middle"


def test_unbounded_component_size_would_be_flat_across_every_landing():
    """Why the horizon exists: every landing shares the thief's component, so the raw
    ``len(reachable_region(...))`` the audit proposed is constant and decides nothing."""
    from cosmos77_thief.strategy.pathing import reachable_region

    b = Board(7)
    b.add_barrier((2, 2))
    sizes = {len(reachable_region(b, c)) for c in [(3, 3), (3, 4), (2, 3), (4, 3), (3, 2)]}
    assert len(sizes) == 1


def test_the_thief_no_longer_parks_when_it_has_room_to_gain():
    """From a cornerish cell with the cop far away, degree ties and the old value STAYED."""
    b = Board(7)
    action = decide_exact(b, (1, 1), (5, 5), PARAMS)
    dest = destination((1, 1), action.move_token)
    assert dest != (1, 1), "thief parked instead of walking into open board"
    assert escape_room(bfs_distances(b, dest), PARAMS.escape_horizon) > escape_room(
        bfs_distances(b, (1, 1)), PARAMS.escape_horizon
    )


def test_the_fuzzy_thief_holds_the_centre_instead_of_running_to_a_corner():
    b = Board(7)
    thief, posterior = (3, 3), {(0, 0): 1.0}
    trail = []
    for _ in range(12):
        action = decide_fuzzy(b, thief, posterior, PARAMS)
        thief = apply_move(b, thief, action.move_token)
        trail.append(thief)
    assert all(c[0] not in RIM and c[1] not in RIM for c in trail), f"ran to the rim: {trail}"


def test_taboo_distance_is_read_not_hardcoded():
    b = Board(7)
    wide = StrategyParams(taboo_distance=2)
    dest = destination((3, 3), decide_exact(b, (3, 3), (3, 6), wide).move_token)
    assert abs(dest[0] - 3) + abs(dest[1] - 6) > 2, "a widened taboo radius was ignored"
    near = destination((3, 3), decide_exact(b, (3, 3), (3, 6), PARAMS).move_token)
    assert abs(near[0] - 3) + abs(near[1] - 6) >= 2
