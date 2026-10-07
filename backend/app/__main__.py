"""Run the API: `uv run python -m app` (add --reload for auto-restart on code changes)."""

import sys

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload="--reload" in sys.argv,
        access_log=False,  # our middleware writes the request log line instead
    )
