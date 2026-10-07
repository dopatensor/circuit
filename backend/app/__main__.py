"""Run the API: `uv run python -m app` (add --reload for auto-restart on code changes).
PORT sets the port (default 8000)."""

import os
import sys

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8000")),  # hosts like Railway/Render set PORT
        reload="--reload" in sys.argv,
        access_log=False,  # our middleware writes the request log line instead
    )
