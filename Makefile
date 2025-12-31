.PHONY: start-mcp stop-mcp test lint typecheck

start-mcp:
	uv run ccr mcp --transport sse --port 11111

stop:
	@lsof -ti:11111 | xargs kill -9 2>/dev/null || echo "No MCP server running on port 11111"

test:
	uv run pytest

lint:
	uv run ruff check clean_code_reviewer/

typecheck:
	uv run mypy clean_code_reviewer/
