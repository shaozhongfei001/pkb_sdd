"""Ensure import paths: backend/app package must not be shadowed by app.py."""

from __future__ import annotations

import sys
from pathlib import Path


def ensure_paths() -> Path:
    streamlit_admin = Path(__file__).resolve().parent
    backend = streamlit_admin.parents[1] / "backend"
    frontend = streamlit_admin.parent

    backend_str = str(backend)
    if backend_str in sys.path:
        sys.path.remove(backend_str)
    sys.path.insert(0, backend_str)

    frontend_str = str(frontend)
    if frontend_str not in sys.path:
        sys.path.append(frontend_str)

    admin_str = str(streamlit_admin)
    if sys.path[:1] == [admin_str]:
        sys.path.pop(0)
        if admin_str not in sys.path:
            sys.path.append(admin_str)

    return frontend
