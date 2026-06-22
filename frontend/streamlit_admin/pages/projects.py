from __future__ import annotations

import streamlit as st
from sqlalchemy.exc import SQLAlchemyError

from bootstrap import ensure_paths

ensure_paths()

from streamlit_admin.lib.db import format_db_error
from streamlit_admin.lib.repositories import (
    list_curated_assets,
    list_project_documents,
    list_projects,
    read_curated_markdown,
)
from streamlit_admin.lib.safe_paths import PathTraversalError


def render() -> None:
    st.header("项目与 Curated 资产")
    st.caption("只读浏览 kb_project / kb_curated_asset，Markdown 从 curated_root 渲染。")

    if st.session_state.get("init_error"):
        st.error(st.session_state.init_error)
        return

    config = st.session_state.config
    session_factory = st.session_state.session_factory

    try:
        with session_factory() as session:
            projects = list_projects(session)
    except SQLAlchemyError as exc:
        st.error(format_db_error(exc))
        return

    if not projects:
        st.info("暂无项目记录。")
        return

    project_options = {f"{p.project_code} — {p.project_name}": p for p in projects}
    selected_label = st.selectbox("选择项目", options=list(project_options.keys()))
    project = project_options[selected_label]

    st.markdown(
        f"**project_uid**: `{project.project_uid}` | "
        f"**文档数**: {project.document_count} | **状态**: {project.status}"
    )

    try:
        with session_factory() as session:
            docs = list_project_documents(session, project.project_uid)
            assets = list_curated_assets(session, project.project_uid)
    except SQLAlchemyError as exc:
        st.error(format_db_error(exc))
        return

    if docs:
        st.subheader("项目文档映射")
        st.dataframe(docs, use_container_width=True, hide_index=True)

    st.subheader("Curated 资产")
    if not assets:
        st.info("该项目暂无 curated 资产。")
        return

    asset_labels = {
        f"{a.asset_type}: {a.asset_title or a.curated_uid}": a for a in assets
    }
    asset_label = st.selectbox("选择资产", options=list(asset_labels.keys()))
    asset = asset_labels[asset_label]

    st.markdown(
        f"- **curated_uid**: `{asset.curated_uid}`\n"
        f"- **asset_type**: {asset.asset_type}\n"
        f"- **curated_path**: `{asset.curated_path}`"
    )

    try:
        body = read_curated_markdown(config, asset.curated_path)
        st.markdown("---")
        st.markdown(body)
    except PathTraversalError as exc:
        st.warning(f"路径安全检查失败：{exc}")
    except FileNotFoundError:
        st.warning(
            f"文件不存在：{config.storage.curated_root / asset.curated_path}"
        )
    except OSError as exc:
        st.warning(f"无法读取 curated 文件：{exc}")


render()
