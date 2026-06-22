from __future__ import annotations

import streamlit as st
from sqlalchemy.exc import SQLAlchemyError

from bootstrap import ensure_paths

ensure_paths()

from streamlit_admin.lib.db import format_db_error
from streamlit_admin.lib.formatters import format_datetime, truncate_text
from streamlit_admin.lib.repositories import list_evidence


def render() -> None:
    st.header("证据浏览器")
    st.caption("只读浏览 kb_evidence / kb_document_chunk / kb_document。")

    if st.session_state.get("init_error"):
        st.error(st.session_state.init_error)
        return

    session_factory = st.session_state.session_factory

    preset = st.session_state.pop("evidence_uid_filter", "")
    with st.form("evidence_filter"):
        evidence_uid = st.text_input("evidence_uid", value=preset)
        document_uid = st.text_input("document_uid", value="")
        content_uid = st.text_input("content_uid", value="")
        chunk_uid = st.text_input("chunk_uid", value="")
        limit = st.number_input("limit", min_value=1, max_value=200, value=50)
        submitted = st.form_submit_button("查询")

    if not submitted and not preset:
        st.info("输入过滤条件后点击查询，或从 KB 搜索页跳转。")
        return

    try:
        with session_factory() as session:
            rows, total = list_evidence(
                session,
                evidence_uid=evidence_uid or None,
                document_uid=document_uid or None,
                content_uid=content_uid or None,
                chunk_uid=chunk_uid or None,
                limit=int(limit),
            )
    except SQLAlchemyError as exc:
        st.error(format_db_error(exc))
        return

    st.caption(f"共 {total} 条证据，显示 {len(rows)} 条。")

    if not rows:
        st.info("未找到证据记录。")
        return

    for row in rows:
        title = row.document_title or row.evidence_uid
        with st.expander(f"{row.evidence_uid} — {title}", expanded=len(rows) == 1):
            st.markdown(
                f"- **document_uid**: `{row.document_uid}`\n"
                f"- **content_uid**: `{row.content_uid}`\n"
                f"- **chunk_uid**: `{row.chunk_uid or ''}`\n"
                f"- **source_location**: {row.source_location or ''}\n"
                f"- **page_no**: {row.page_no or ''}\n"
                f"- **heading_path**: {row.heading_path or ''}\n"
                f"- **created_at**: {format_datetime(row.created_at)}"
            )
            if row.quote_text:
                st.markdown("**quote_text**")
                st.write(truncate_text(row.quote_text, 500))
            if row.normalized_text:
                st.markdown("**normalized_text**")
                st.write(truncate_text(row.normalized_text, 500))
            if row.chunk_preview:
                st.markdown("**chunk preview**")
                st.write(row.chunk_preview)


render()
