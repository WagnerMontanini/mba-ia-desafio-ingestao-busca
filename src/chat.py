"""CLI de chat para perguntas sobre o conteúdo ingerido."""

from __future__ import annotations

import logging
import os

from cli_utils import prompt_provider
from search import search_prompt
from settings import set_provider

logger = logging.getLogger(__name__)

_EXIT_COMMANDS = {"exit", "sair", "quit", "q"}
_FALLBACK = "Não tenho informações necessárias para responder sua pergunta."


def _configure_logging() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )


def main() -> None:
    _configure_logging()

    try:
        provider = prompt_provider()
    except KeyboardInterrupt:
        print("\nSeleção cancelada. Até logo!")
        return
    set_provider(provider)
    print(f"Provedor selecionado: {provider}\n")

    try:
        ask = search_prompt()
    except Exception as exc:
        logger.exception("Falha ao inicializar a busca: %s", exc)
        print(f"Não foi possível iniciar o chat: {exc}")
        return

    print("Chat iniciado. Digite sua pergunta ou 'sair' para encerrar.\n")

    while True:
        try:
            question = input("PERGUNTA: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nEncerrando chat. Até logo!")
            return

        if not question:
            continue

        if question.lower() in _EXIT_COMMANDS:
            print("Encerrando chat. Até logo!")
            return

        try:
            answer = ask(question)
        except Exception as exc:
            logger.exception("Erro ao responder pergunta: %s", exc)
            print(f"RESPOSTA: {_FALLBACK}")
            print(f"[erro interno] {exc}\n")
            continue

        print(f"RESPOSTA: {answer}\n")


if __name__ == "__main__":
    main()
