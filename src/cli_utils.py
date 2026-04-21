"""Utilitários de interação CLI (prompts de seleção).

Este módulo é o único lugar (além de ``chat.py``) onde ``print()`` e
``input()`` são permitidos: aqui tratamos UX do usuário, não logs de
pipeline.
"""

from __future__ import annotations

import os
from typing import Literal

ProviderLiteral = Literal["openai", "gemini"]

_VALID_PROVIDERS: tuple[ProviderLiteral, ...] = ("openai", "gemini")
_ALIASES: dict[str, ProviderLiteral] = {
    "1": "openai",
    "openai": "openai",
    "o": "openai",
    "2": "gemini",
    "gemini": "gemini",
    "g": "gemini",
}


def _env_default() -> ProviderLiteral | None:
    raw = (os.getenv("PROVIDER") or "").strip().lower()
    return raw if raw in _VALID_PROVIDERS else None  # type: ignore[return-value]


def prompt_provider(default: ProviderLiteral | None = None) -> ProviderLiteral:
    """Pergunta interativamente qual provedor de IA utilizar.

    Usa ``default`` ou ``PROVIDER`` do ambiente como pré-seleção quando o
    usuário apenas pressiona Enter. Levanta ``KeyboardInterrupt`` se o
    usuário cancelar (Ctrl+C) — o chamador decide como tratar.
    """
    resolved_default: ProviderLiteral = default or _env_default() or "openai"

    print("Selecione o provedor de IA:")
    for idx, name in enumerate(_VALID_PROVIDERS, start=1):
        marker = " (default)" if name == resolved_default else ""
        label = "OpenAI" if name == "openai" else "Gemini"
        print(f"  [{idx}] {label}{marker}")

    default_key = "1" if resolved_default == "openai" else "2"

    while True:
        try:
            raw = input(f"Opção [{default_key}]: ").strip().lower()
        except EOFError:
            return resolved_default
        if not raw:
            return resolved_default
        chosen = _ALIASES.get(raw)
        if chosen is not None:
            return chosen
        print("Opção inválida. Digite 1/openai ou 2/gemini.")
