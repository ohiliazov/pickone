"""Rating systems: Glicko-1, Elo, EGF — behind one protocol.  [M3]

[INVARIANT] This package imports nothing from `db`, `battles`, `matchmaking`,
or any framework. It is pure functions over a frozen config, which is what makes
it simulatable and 100%-testable. Enforced by import-linter; see pyproject.toml.
"""
