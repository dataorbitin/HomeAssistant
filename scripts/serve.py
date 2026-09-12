"""Local server entry point, including Psycopg-compatible Windows event loop."""

import asyncio
import os
import sys

import uvicorn

if __name__ == "__main__":
    config = uvicorn.Config(
        "app.main:app", host="0.0.0.0", port=int(os.environ.get("PORT", "8000")), access_log=False
    )
    server = uvicorn.Server(config)
    if sys.platform == "win32":
        with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
            runner.run(server.serve())
    else:
        asyncio.run(server.serve())
