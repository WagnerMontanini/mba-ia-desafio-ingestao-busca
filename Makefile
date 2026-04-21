PYTHON ?= python

.PHONY: help install install-dev up down logs ingest chat clean \
        lint lint-fix fmt fmt-check typecheck test \
        precommit-install precommit-run precommit-update

help:
	@echo "Alvos disponíveis:"
	@echo "  install           - instala dependências de runtime (requirements.txt)"
	@echo "  install-dev       - instala runtime + dev (requirements-dev.txt) + pre-commit"
	@echo "  up                - sobe o banco (docker compose up -d)"
	@echo "  down              - derruba o banco"
	@echo "  logs              - mostra logs do postgres"
	@echo "  ingest            - executa a ingestão do PDF"
	@echo "  chat              - abre o chat CLI"
	@echo "  clean             - remove volumes do banco (apaga embeddings)"
	@echo ""
	@echo "Qualidade de código:"
	@echo "  lint              - roda Ruff (apenas checagem)"
	@echo "  lint-fix          - roda Ruff aplicando correções automáticas"
	@echo "  fmt               - formata o código com Ruff format"
	@echo "  fmt-check         - valida formatação sem alterar arquivos"
	@echo "  typecheck         - roda mypy em src/"
	@echo "  test              - roda pytest (se houver testes)"
	@echo ""
	@echo "pre-commit:"
	@echo "  precommit-install - instala os hooks no .git/hooks"
	@echo "  precommit-run     - roda todos os hooks em todos os arquivos"
	@echo "  precommit-update  - atualiza revs dos hooks (autoupdate)"

# ---------------------------------------------------------------------------
# Dependências
# ---------------------------------------------------------------------------
install:
	$(PYTHON) -m pip install -r requirements.txt

install-dev:
	$(PYTHON) -m pip install -r requirements-dev.txt
	$(PYTHON) -m pre_commit install --install-hooks
	$(PYTHON) -m pre_commit install --hook-type commit-msg

# ---------------------------------------------------------------------------
# Infra / execução
# ---------------------------------------------------------------------------
up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f postgres

ingest:
	$(PYTHON) src/ingest.py

chat:
	$(PYTHON) src/chat.py

clean:
	docker compose down -v

# ---------------------------------------------------------------------------
# Qualidade de código
# ---------------------------------------------------------------------------
lint:
	$(PYTHON) -m ruff check src

lint-fix:
	$(PYTHON) -m ruff check src --fix

fmt:
	$(PYTHON) -m ruff format src

fmt-check:
	$(PYTHON) -m ruff format --check src

typecheck:
	$(PYTHON) -m mypy src

test:
	$(PYTHON) -m pytest

# ---------------------------------------------------------------------------
# pre-commit
# ---------------------------------------------------------------------------
precommit-install:
	$(PYTHON) -m pre_commit install --install-hooks
	$(PYTHON) -m pre_commit install --hook-type commit-msg

precommit-run:
	$(PYTHON) -m pre_commit run --all-files

precommit-update:
	$(PYTHON) -m pre_commit autoupdate
