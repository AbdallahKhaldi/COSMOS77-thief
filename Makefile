# COSMOS77-thief — gates and process hygiene (playbook Phase 0).
# Port default mirrors the future config/peer.toml; override: make kill THIEF_PORT=9001
THIEF_PORT ?= 8802

.PHONY: sync test lint smoke kill

sync:
	uv sync

test:
	uv run pytest

lint:
	uv run ruff check .

# Two-process gate: this repo's peer + ../COSMOS77-cop's peer over real localhost HTTP,
# full handshake + one committed turn each (no in-play reveal — nonces stay secret).
smoke:
	uv run python scripts/smoke.py

# Orphaned peers keep playing sub-games for you ("killing a shell does not kill what it
# spawned" — playbook §7.17). Free our port between attempts.
kill:
	-@lsof -ti tcp:$(THIEF_PORT) | xargs kill 2>/dev/null; true
	@echo "kill: freed tcp:$(THIEF_PORT)"
