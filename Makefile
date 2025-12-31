.PHONY: mcp test lint typecheck

mcp:
	uv run ccr mcp --transport sse --port 11111

test:
	uv run pytest

lint:
	uv run ruff check clean_code_reviewer/

typecheck:
	uv run mypy clean_code_reviewer/
