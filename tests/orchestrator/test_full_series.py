"""Full in-memory series: our SeriesDriver (thief) vs a scripted greedy-pursuit cop.

Two gateways cross-wired through in-memory clients (zero sockets). The stub cop chases the
tracked thief and claims truthfully on co-location; our thief brain must hold the provable
35-step survival floor through the WHOLE stack (loop, wire, audits, settlement).
"""

import json
import threading
import types
from pathlib import Path

from cosmos77_thief.crypto.nonce import new_nonce
from cosmos77_thief.crypto.step0 import build_step0
from cosmos77_thief.engine.config import from_dict
from cosmos77_thief.engine.rules import destination, legal_move_tokens
from cosmos77_thief.net.server import (
    KIND_AUDIT,
    KIND_CONTROL,
    KIND_NEGOTIATE,
    KIND_TURN,
    PeerInbox,
)
from cosmos77_thief.orchestrator.gateway import Gateway
from cosmos77_thief.orchestrator.peerconf import PeerConfig
from cosmos77_thief.orchestrator.series import SeriesDriver, window_groups
from cosmos77_thief.orchestrator.turnloop import play_sub_game
from cosmos77_thief.orchestrator.turnstate import SideKit, fresh_state
from cosmos77_thief.protocol.sealing import commit
from cosmos77_thief.report.artifacts import ArtifactWriter
from cosmos77_thief.report.compare import compare_results
from cosmos77_thief.report.finish import finish_series

REPO = Path(__file__).resolve().parents[2]
KIND = {
    "negotiate": KIND_NEGOTIATE,
    "receive_turn": KIND_TURN,
    "receive_control": KIND_CONTROL,
    "submit_audit": KIND_AUDIT,
}


class InMemoryClient:
    def __init__(self, target: PeerInbox):
        self.target = target

    def call(self, tool, args, *, deadline_s):
        self.target.push(KIND[tool], args.get("message") or args.get("payload"))
        return {"ok": True}

    def close(self):
        return None


class GreedyCopBridge:
    def decide(self, state, kit):
        cell, confidence = kit.tracker.estimate()
        target = cell if confidence == "exact" and cell is not None else (3, 3)

        def dist(token):
            dest = destination(state.my_pos, token)
            return (abs(dest[0] - target[0]) + abs(dest[1] - target[1]), token)

        token = min(legal_move_tokens(state.board, state.my_pos), key=dist)
        dest = destination(state.my_pos, token)
        claim = dest if dest == target else None
        return types.SimpleNamespace(
            kind="move", move_token=token, barrier_cell=None, capture_claim=claim
        )


def game_cfg():
    raw = json.loads((REPO / "config" / "game.json").read_text(encoding="utf-8"))
    return from_dict(raw), raw


def sealed_step0(window, gid):
    payload = build_step0(
        sub_game_number=window,
        group_name=gid,
        model="template",
        code_version="c" * 40,
        num_games_declared=None,
        spec={"os": "test"},
    )
    nonce = new_nonce()
    return {"payload": payload, "nonce": nonce, "commit": commit(payload, nonce)}


def stub_cop_series(cfg, peer_cfg, inbox, client, windows, gid_a, gid_b):
    for window in range(1, windows + 1):
        police_gid, thief_gid = window_groups(window, gid_a, gid_b)
        gateway = Gateway(
            game_cfg=cfg,
            peer_cfg=peer_cfg,
            role="police",
            group_id=police_gid,
            group_name=police_gid,
            sub_game_number=window,
            opponent_group_id=thief_gid,
            client=client,
            inbox=inbox,
        )
        state = fresh_state(cfg, "police")
        kit = SideKit.fresh(cfg, "police", seed=3000 + window)
        play_sub_game(gateway, state, kit, GreedyCopBridge(), sealed_step0(window, police_gid))


def test_two_window_series_our_thief_survives_with_clean_audits(tmp_path):
    cfg, raw = game_cfg()
    fast = {"turn_timeout_s": 15.0, "watchdog_s": 30.0, "handshake_budget_s": 15.0}
    gid_a, gid_b = "cosmos77", "cosmos77-mirror"
    driver = SeriesDriver(
        game_cfg=cfg,
        peer_cfg=PeerConfig(**fast),
        gid_a=gid_a,
        gid_b=gid_b,
        out_dir=tmp_path / "ours",
        code_version="a" * 40,
        hardware={"os": "test"},
    )
    writer = ArtifactWriter(
        tmp_path / "ours", gid=driver.gid, uid="uid-x", github={}, counted=False, reason="friendly"
    )
    driver.writer = writer
    stub_inbox = PeerInbox()
    driver.client = InMemoryClient(stub_inbox)
    stub_client = InMemoryClient(driver.inbox)
    thread = threading.Thread(
        target=stub_cop_series,
        args=(cfg, PeerConfig(**fast), stub_inbox, stub_client, 2, gid_a, gid_b),
        daemon=True,
    )
    thread.start()
    first = driver.play_window(1)
    second = driver.play_window(2)
    thread.join(timeout=60)
    for report in (first, second):
        assert report.result == "survival", (report.result, report.reason)
        assert report.steps == 35
        assert report.settlement is not None and report.settlement.settled
        assert report.settlement.log_verified and not report.settlement.tampered
        assert report.my_audit is not None and report.my_audit.clean
    summary = finish_series(
        driver,
        writer,
        raw_cfg=raw,
        my_gid=gid_a,
        my_identity={"group_name": gid_a, "members": [], "repos": {}, "mcp_servers": {}},
        peer_identity=driver.peer_identity,
        expected_windows=2,
    )
    assert summary["settled"]
    result = json.loads(
        (tmp_path / "ours" / f"result_{driver.gid}.json").read_text(encoding="utf-8")
    )
    assert compare_results(result, result) == []
    for row in result["sub_games"]:
        assert sorted(row["score"].values()) == [5, 10]
    # Rule 49: the peer's gid maps to the repos THEY declared in their greeting — never
    # invented for them. The stub greets with this repo's identity constants.
    from cosmos77_thief.orchestrator.identity import TEAM_REPOS

    assert result["links"]["github"] == {"cosmos77": dict(TEAM_REPOS)}


def test_seed_github_never_claims_our_repos_for_a_real_opponent():
    from cosmos77_thief.commands_play import seed_github
    from cosmos77_thief.orchestrator.identity import TEAM_REPOS

    assert seed_github("cosmos77", "rival", selfplay=False) == {"cosmos77": dict(TEAM_REPOS)}
    both = seed_github("cosmos77", "cosmos77-mirror", selfplay=True)
    assert set(both) == {"cosmos77", "cosmos77-mirror"}
