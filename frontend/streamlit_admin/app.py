"""013 Streamlit Admin — read-only operator console."""

from __future__ import annotations

import sys
from pathlib import Path

# Fix paths before any backend `app.*` imports (app.py must not shadow backend/app).
_backend = Path(__file__).resolve().parents[2] / "backend"
if str(_backend) not in sys.path:
    sys.path.insert(0, str(_backend))
_admin_dir = str(Path(__file__).resolve().parent)
if sys.path[:1] == [_admin_dir]:
    sys.path.pop(0)
    sys.path.append(_admin_dir)

import os

import streamlit as st

from bootstrap import ensure_paths

ensure_paths()

from streamlit_admin.lib.db import create_db_resources


@st.cache_resource
def get_cached_db_resources(config_path: str | None) -> tuple:
    path = None
    if config_path:
        path = Path(config_path)
    return create_db_resources(path)


def main() -> None:
    st.set_page_config(
        page_title="PKB Streamlit Admin",
        page_icon="📚",
        layout="wide",
    )

    if "resources_ready" not in st.session_state:
        try:
            cfg_override = os.environ.get("PKB_CONFIG", "").strip() or None
            config, _engine, session_factory = get_cached_db_resources(cfg_override)
            st.session_state.config = config
            st.session_state.session_factory = session_factory
            st.session_state.resources_ready = True
        except Exception as exc:
            st.session_state.init_error = str(exc)
            st.session_state.resources_ready = False

    st.title("Personal KB — 只读管理台")
    if st.session_state.get("resources_ready") and st.session_state.get("config"):
        pipeline = st.session_state.config.pipeline_version
        st.caption(f"pipeline_version: {pipeline} | 只读模式 — 不触发 parser / pipeline CLI")

    if st.session_state.get("init_error"):
        st.error(st.session_state.init_error)

    pages = [
        st.Page("pages/search.py", title="KB 搜索", icon="🔍", default=True),
        st.Page("pages/evidence.py", title="证据浏览器", icon="📎"),
        st.Page("pages/projects.py", title="项目与 Curated", icon="📁"),
        st.Page("pages/parse_registry.py", title="Parse Registry", icon="⚙️"),
        st.Page("pages/quality_reports.py", title="质量报告", icon="📊"),
        st.Page("pages/inventory.py", title="Inventory Snapshot", icon="🗂️"),
    ]
    pg = st.navigation(pages)
    pg.run()


if __name__ == "__main__":
    main()
else:
    main()
