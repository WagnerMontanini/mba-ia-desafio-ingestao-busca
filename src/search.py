"""Busca semântica: recupera contexto do pgVector e responde via LLM."""

from __future__ import annotations

import logging
from collections.abc import Callable

from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate

from settings import TOP_K, build_vector_store, get_llm

logger = logging.getLogger(__name__)

PROMPT_TEMPLATE = """
CONTEXTO:
{contexto}

REGRAS:
- Responda somente com base no CONTEXTO.
- Se a informação não estiver explicitamente no CONTEXTO, responda:
  "Não tenho informações necessárias para responder sua pergunta."
- Nunca invente ou use conhecimento externo.
- Nunca produza opiniões ou interpretações além do que está escrito.

EXEMPLOS DE PERGUNTAS FORA DO CONTEXTO:
Pergunta: "Qual é a capital da França?"
Resposta: "Não tenho informações necessárias para responder sua pergunta."

Pergunta: "Quantos clientes temos em 2024?"
Resposta: "Não tenho informações necessárias para responder sua pergunta."

Pergunta: "Você acha isso bom ou ruim?"
Resposta: "Não tenho informações necessárias para responder sua pergunta."

PERGUNTA DO USUÁRIO:
{pergunta}

RESPONDA A "PERGUNTA DO USUÁRIO"
"""


def _format_context(results: list[tuple[Document, float]]) -> str:
    if not results:
        return ""
    return "\n\n".join(doc.page_content.strip() for doc, _score in results)


def search_prompt() -> Callable[[str], str]:
    """Monta a cadeia de busca e retorna um callable ``ask(pergunta) -> resposta``.

    A cada chamada, a pergunta é vetorizada, os TOP_K trechos mais relevantes
    são recuperados do pgVector e injetados no ``PROMPT_TEMPLATE`` antes do LLM.
    Exceções de inicialização (env ausente, conexão inválida, credenciais)
    são propagadas para o chamador decidir como tratá-las.
    """
    store = build_vector_store()
    prompt = PromptTemplate(
        template=PROMPT_TEMPLATE,
        input_variables=["contexto", "pergunta"],
    )
    llm = get_llm()
    chain = prompt | llm | StrOutputParser()

    logger.debug("Cadeia de busca inicializada (TOP_K=%d).", TOP_K)

    def ask(question: str) -> str:
        pergunta = (question or "").strip()
        if not pergunta:
            return "Não tenho informações necessárias para responder sua pergunta."
        results = store.similarity_search_with_score(pergunta, k=TOP_K)
        contexto = _format_context(results)
        return chain.invoke({"contexto": contexto, "pergunta": pergunta}).strip()

    return ask
