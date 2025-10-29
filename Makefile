.PHONY: install reinstall uninstall build install-local setup-kb

build:
	poetry build

install:
	@command -v pipx >/dev/null 2>&1 || (echo "pipx is required. Install with: python3 -m pip install --user pipx && python3 -m pipx ensurepath" && exit 1)
	pipx install --force .

reinstall:
	@command -v pipx >/dev/null 2>&1 || (echo "pipx is required. Install with: python3 -m pip install --user pipx && python3 -m pipx ensurepath" && exit 1)
	pipx install --force .

uninstall:
	@command -v pipx >/dev/null 2>&1 || (echo "pipx is required." && exit 1)
	pipx uninstall solcoder || true

# Developer convenience: editable install in current venv
install-local:
	pip install -e .

setup-kb:
	poetry run pip install -e "third_party/solana-rag/LightRAG[api]"
	poetry run python scripts/setup_kb.py
