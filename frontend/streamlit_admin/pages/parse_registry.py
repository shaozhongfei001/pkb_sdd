from __future__ import annotations

import streamlit as st
from sqlalchemy.exc import SQLAlchemyError

from bootstrap import ensure_paths

ensure_paths()

from streamlit_admin.lib.db import format_db_error
from streamlit_admin.lib.formatters import format_datetime
from streamlit_admin.lib.repositories import get_parse_run_detail, list_parse_runs


def render() -> None:
    st.header("Parse Registry")
    st.caption("只读浏览 kb_parse_run / kb_parse_result / kb_parsed_artifact。")

    if st.session_state.get("init_error"):
        st.error(st.session_state.init_error)
        return

    session_factory = st.session_state.session_factory

    try:
        with session_factory() as session:
            runs = list_parse_runs(session, limit=50)
    except SQLAlchemyError as exc:
        st.error(format_db_error(exc))
        return

    if not runs:
        st.info("暂无 parse run 记录。")
        return

    run_labels = {
        f"{r.run_uid} — {r.parser_name} ({r.status})": r.run_uid for r in runs
    }
    selected = st.selectbox("选择 parse run", options=list(run_labels.keys()))
    run_uid = run_labels[selected]

    try:
        with session_factory() as session:
            run_row, results, artifacts = get_parse_run_detail(session, run_uid)
    except SQLAlchemyError as exc:
        st.error(format_db_error(exc))
        return

    if run_row is None:
        st.warning("未找到所选 run。")
        return

    st.markdown(
        f"- **parser_name**: {run_row.parser_name}\n"
        f"- **parser_adapter_version**: {run_row.parser_adapter_version}\n"
        f"- **parser_family**: {run_row.parser_family}\n"
        f"- **status**: {run_row.status}\n"
        f"- **total_candidates**: {run_row.total_candidates} | "
        f"**parsed**: {run_row.parsed_count} | **failed**: {run_row.failed_count}\n"
        f"- **started_at**: {format_datetime(run_row.started_at)} | "
        f"**finished_at**: {format_datetime(run_row.finished_at)} | "
        f"**created_at**: {format_datetime(run_row.created_at)}"
    )

    st.subheader("Parse Results")
    if results:
        st.dataframe(results, use_container_width=True, hide_index=True)
    else:
        st.info("该 run 无 result 记录。")

    st.subheader("Parsed Artifacts")
    if artifacts:
        st.dataframe(artifacts, use_container_width=True, hide_index=True)
    else:
        st.info("该 run 无 artifact 记录。")


render()
