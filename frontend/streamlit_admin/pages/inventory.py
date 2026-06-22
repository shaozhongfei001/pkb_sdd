from __future__ import annotations

import streamlit as st
from sqlalchemy.exc import SQLAlchemyError

from bootstrap import ensure_paths

ensure_paths()

from streamlit_admin.lib.db import format_db_error
from streamlit_admin.lib.repositories import (
    file_ext_summary,
    inventory_counts,
    list_file_instances,
    list_vault_objects_metadata,
    vault_status_summary,
)


def render() -> None:
    st.header("Inventory Snapshot")
    st.caption("只读浏览 kb_file_instance / kb_file_content / vault 元数据。")

    if st.session_state.get("init_error"):
        st.error(st.session_state.init_error)
        return

    session_factory = st.session_state.session_factory

    try:
        with session_factory() as session:
            counts = inventory_counts(session)
            vault_status = vault_status_summary(session)
            ext_summary = file_ext_summary(session)
            instances, total = list_file_instances(session, limit=50)
            vault_rows = list_vault_objects_metadata(session, limit=20)
    except SQLAlchemyError as exc:
        st.error(format_db_error(exc))
        return

    col1, col2, col3 = st.columns(3)
    col1.metric("file_instance", counts["file_instance_count"])
    col2.metric("file_content", counts["file_content_count"])
    col3.metric("vault_object", counts["vault_object_count"])

    st.subheader("Vault Status 摘要")
    if vault_status:
        st.dataframe(
            [{"vault_status": s, "count": c} for s, c in vault_status],
            use_container_width=True,
            hide_index=True,
        )

    st.subheader("File Extension 摘要")
    if ext_summary:
        st.dataframe(
            [{"file_ext": ext or "(none)", "count": c} for ext, c in ext_summary],
            use_container_width=True,
            hide_index=True,
        )

    st.subheader(f"File Instances（共 {total} 条，显示前 50 条）")
    if instances:
        st.dataframe(instances, use_container_width=True, hide_index=True)
    else:
        st.info("暂无 file instance 记录。")

    st.subheader("Vault Objects 元数据（最近 20 条）")
    if vault_rows:
        st.dataframe(vault_rows, use_container_width=True, hide_index=True)
    else:
        st.info("暂无 vault object 记录。")


render()
