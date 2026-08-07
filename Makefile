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

# Two-process gate: launch this repo's peer and ../COSMOS77-cop's peer on localhost,
# complete one handshake + one committed turn each, exit 0. Real from Phase 5 (net layer);
# until then it fails honestly instead of lying green.
smoke:
	@echo "smoke: handshake + one committed turn vs ../COSMOS77-cop over localhost."
	@echo "smoke: the net layer lands in Phase 5 — failing honestly until then."
	@exit 2

# Orphaned peers keep playing sub-games for you ("killing a shell does not kill what it
# spawned" — playbook §7.17). Free our port between attempts.
kill:
	-@lsof -ti tcp:$(THIEF_PORT) | xargs kill 2>/dev/null; true
	@echo "kill: freed tcp:$(THIEF_PORT)"
