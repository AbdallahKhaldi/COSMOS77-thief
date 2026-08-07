"""The single facade for thief-agent operations (§0.14: all logic behind one SDK class)."""


class SDK:
    """Facade over the engine, strategy, net, crypto, hints, report and orchestrator layers.

    Later phases attach the real subsystems here; nothing outside this class wires them together.
    """
