"""Grounded AI layer (plan/05-ai-layer.md): context pack, validator, answers, offline cache.

Public entry point: ``engine.ai.answer.ask(question, habitat, context_ids)``.
Works fully offline in deterministic "template" mode; Claude is used only when
``ANTHROPIC_API_KEY`` is set and the ``anthropic`` package is importable.
"""

PROMPT_VERSION = "v1"
