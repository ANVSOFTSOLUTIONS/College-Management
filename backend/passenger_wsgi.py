"""Entry point cPanel's "Setup Python App" looks for.

The server expects a WSGI `application` callable; FastAPI is ASGI, so this
bridges the two with a2wsgi. It imports this file directly — it does not run
`uvicorn`.

Two things a2wsgi does not do for us:
- It never sends ASGI lifespan events, so FastAPI's lifespan (which opens the
  MySQL pool) never runs. The pool is opened here instead, on a2wsgi's own
  event loop — the loop every request runs on, which aiomysql's pool is tied to.
- It runs that loop in a background thread. LiteSpeed (and Passenger's smart
  spawning) import this file once and then fork workers, and threads do not
  survive a fork: a worker would wait forever on a loop nobody runs. So the
  bridge is built lazily, per process, on the first request after the fork.
"""

import asyncio
import os
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from a2wsgi import ASGIMiddleware

from app.db.database import connect_to_mysql
from app.main import app as _asgi_app

_bridge: ASGIMiddleware | None = None
_bridge_pid: int | None = None
_bridge_lock = threading.Lock()


def _get_bridge() -> ASGIMiddleware:
    global _bridge, _bridge_pid
    if _bridge is None or _bridge_pid != os.getpid():
        with _bridge_lock:
            if _bridge is None or _bridge_pid != os.getpid():
                bridge = ASGIMiddleware(_asgi_app)
                asyncio.run_coroutine_threadsafe(connect_to_mysql(), bridge.loop).result(timeout=30)
                _bridge, _bridge_pid = bridge, os.getpid()
    return _bridge


def application(environ, start_response):
    return _get_bridge()(environ, start_response)
