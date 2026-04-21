# Convenções de Código — Stack deste projeto

> Este documento **sobrescreve** qualquer convenção Django herdada de regras do usuário, pois **este projeto é CLI Python, sem Django**. Use `docs/skill/Prompt_Dev.md` como base, ignorando as seções Django-específicas (Admin, ORM, CBV/FBV, gettext obrigatório).

## 1. Estilo

- **PEP 8** com linha até **100 colunas**.
- **Black** + **isort** (perfil black) + **Flake8/Ruff** se configurados.
- Ordem de imports: stdlib → terceiros → locais. Em blocos separados, ordenados alfabeticamente.
- `from __future__ import annotations` no topo de módulos que usam anotações postergadas (já vigente em `settings.py`).

## 2. Tipagem

- **Type hints obrigatórios** em funções e métodos públicos.
- Use `typing.Literal`, `Protocol`, `TypedDict` onde fizer sentido (ex.: `ProviderLiteral` em `settings.py`).
- Retornos explícitos — evite `Any`. Prefira tipos de `langchain_core`:
  - `Embeddings` (de `langchain_core.embeddings`)
  - `BaseChatModel` (de `langchain_core.language_models.chat_models`)
  - `Document` (de `langchain_core.documents`)

## 3. Docstrings

- Estilo **Google** curto (uma linha + seções opcionais).
- Obrigatório em funções públicas (`get_embeddings`, `ingest_pdf`, `search_prompt`, etc.).
- Exemplo:

```python
def chunk_id(source: str, page: int, start_index: int) -> str:
    """Gera ID UUIDv5 determinístico para um chunk.

    Args:
        source: Caminho do PDF de origem.
        page: Página 0-indexada.
        start_index: Offset do chunk dentro da página.

    Returns:
        UUID em formato string, estável entre execuções.
    """
```

## 4. Logging

- **Um logger por módulo**: `logger = logging.getLogger(__name__)`.
- Configuração base no início do script executável:

```python
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
```

- Níveis:
  - `DEBUG`: tamanho de chunks, IDs gerados (amostra), contagens intermediárias.
  - `INFO`: começo/fim de pipeline, total de chunks inseridos, provider em uso.
  - `WARNING`: chunks vazios descartados, env opcional ausente com fallback.
  - `ERROR`: falha em loader/embedding/DB — **sempre re-raise** após logar.
- **Nada de `print()`** em `settings.py`, `ingest.py`, `search.py`. `print()` permitido APENAS no REPL `chat.py` (UX).
- Nunca logue API keys, trechos integrais de PDF privado, ou `DATABASE_URL` com senha.

## 5. i18n / Idioma

- Projeto é **pt-BR-only** (sem `gettext`, sem `.po/.mo`).
- Mensagens e logs em português. Variáveis e nomes de função em inglês é aceitável, mas mensagens ao usuário em pt-BR.
- Ignore a regra "gettext obrigatório" do `Prompt_Dev.md` — ela é Django-específica.

## 6. Erros e validação

- **Fail-fast** em env e config. Já adotado: `_require_env` levanta `RuntimeError` com mensagem acionável.
- Exceções específicas:
  - `RuntimeError` para problemas de configuração/ambiente.
  - `FileNotFoundError` para `PDF_PATH` inválido.
  - `ValueError` para inputs inválidos do usuário (pergunta vazia — embora no REPL só se ignore).
- `try/except` largo (ex.: `except Exception`) só no loop do REPL para não derrubar a sessão, e SEMPRE logue com `logger.exception()`.

## 7. Configuração & Segredos

- **12-Factor**: tudo via env. Nada de constantes em código além das fixas do projeto (`CHUNK_SIZE=1000`, etc.).
- `.env` **nunca** vai para git (já no `.gitignore`).
- `.env.example` é a documentação viva das envs necessárias — mantenha sincronizado.
- Validação dinâmica: credenciais do provider só são exigidas quando o provider é realmente escolhido (já implementado em `validate_provider_credentials`).

## 8. Estrutura de arquivos

```
src/
├── settings.py   # Config + factories (único ponto de criação de clientes)
├── ingest.py     # Pipeline de ingestão (executável)
├── search.py     # PROMPT_TEMPLATE + search_prompt() (biblioteca)
└── chat.py       # REPL (executável)
```

**Regras**:
- `settings.py` não importa de `ingest/search/chat`.
- `search.py` pode importar de `settings.py`.
- `ingest.py` pode importar de `settings.py`.
- `chat.py` importa APENAS de `search.py` (e stdlib).
- Zero importação cruzada entre `ingest.py` e `search.py`.

## 9. Imports locais no CLI

Como `chat.py` faz `from search import search_prompt`, os scripts em `src/` são executados com `src/` no path. Opções válidas:

```powershell
# A partir da raiz do projeto
python src/chat.py
```

Isso funciona porque Python adiciona o diretório do script ao `sys.path`. Não adicione `sys.path.insert` manualmente.

## 10. Dependências

- **Pin exato** no `requirements.txt` (já adotado). Não mudar versões sem motivo e sem testar ingest+search end-to-end.
- Adicionar lib nova: inclua no `requirements.txt` com versão exata, mencione no PR (motivação, tamanho, alternativas).
- Jamais fazer `pip install` em runtime.

## 11. Testes (se/quando adicionar)

Plano atual **não exige testes automatizados**, mas se adicionar:

- **pytest** (sem Django plugin — não é Django).
- Estrutura: `tests/test_settings.py`, `tests/test_ingest.py`, `tests/test_search.py`.
- Para embeddings/LLM: use **fakes** (`langchain_core.embeddings.fake.FakeEmbeddings`, `langchain_community.chat_models.fake.FakeListChatModel`).
- Para PGVector: use container Postgres efêmero ou mock do store. Prefira tests de unidade com fakes sobre testes de integração pesados.

## 12. Commits e branches

Siga o padrão Conventional Commits:

- `feat(ingest): ...`, `feat(search): ...`, `feat(chat): ...`, `feat(settings): ...`
- `fix(...)`, `refactor(...)`, `docs(...)`, `chore(...)`
- Commits **atômicos** — um arquivo completo funcionando por commit, com os testes/validações que couberem.

Branches:
- `feature/ingest-pipeline`, `feature/search-chain`, `feature/chat-repl`, etc.
- Sem commits direto em `main`.

## 13. Segurança rápida

- `DATABASE_URL` não deve aparecer em logs.
- API keys apenas em `.env` (nunca em `README.md` ou commits).
- Revise `document.pdf` antes de commitar — se tem dado sensível, adicione ao `.gitignore` e trabalhe com exemplo placeholder.

## 14. Performance — notas

- Ingest de PDFs grandes: `PyPDFLoader` carrega tudo em memória. Para >100MB considere streaming, mas fora do escopo atual.
- Busca: `k=10` é barato. Não cachear (baixo ganho, alta complexidade).
- Embeddings: OpenAI/Gemini já fazem batching internamente no `add_documents`; não implementar batching manual.

## 15. Observabilidade

- Logs são observability suficiente para este escopo.
- Contagens importantes (chunks inseridos, chunks recuperados) devem sair em nível INFO.
- Se depurar scoring, use `logger.debug("top-%d scores: %s", k, [s for _, s in docs])`.
