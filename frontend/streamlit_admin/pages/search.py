from __future__ import annotations

import streamlit as st
from sqlalchemy.exc import SQLAlchemyError

from bootstrap import ensure_paths

ensure_paths()

from app.schemas.search import SearchProjectNotFoundError, SearchValidationError
from streamlit_admin.lib.db import format_db_error
from streamlit_admin.lib.formatters import search_hit_row
from streamlit_admin.lib.search_client import search_kb


def render() -> None:
    st.header("KB 搜索")
    st.caption("通过 SearchService 只读搜索，支持 scope / project_code / limit / offset。")

    if st.session_state.get("init_error"):
        st.error(st.session_state.init_error)
        return

    config = st.session_state.config
    session_factory = st.session_state.session_factory

    with st.form("search_form"):
        query = st.text_input("查询词", placeholder="输入中文或英文关键词")
        col1, col2 = st.columns(2)
        with col1:
            scope = st.selectbox(
                "范围 (scope)",
                options=["all", "document", "chunk", "evidence", "project", "curated"],
                index=0,
            )
            project_code = st.text_input("项目代码 (可选)", value="")
        with col2:
            content_uid = st.text_input("content_uid (可选)", value="")
            document_uid = st.text_input("document_uid (可选)", value="")
        col3, col4 = st.columns(2)
        with col3:
            limit = st.number_input("limit", min_value=1, max_value=100, value=20)
        with col4:
            offset = st.number_input("offset", min_value=0, value=0)
        submitted = st.form_submit_button("搜索")

    if not submitted:
        preset = st.session_state.pop("search_query_preset", None)
        if preset:
            st.info(f"来自其他页面的预设查询：{preset}")
        return

    if not query.strip():
        st.warning("查询词不能为空。")
        return

    try:
        response = search_kb(
            config,
            query=query,
            scope=scope,
            project_code=project_code or None,
            content_uid=content_uid or None,
            document_uid=document_uid or None,
            limit=int(limit),
            offset=int(offset),
            session_factory=session_factory,
        )
    except SearchValidationError as exc:
        st.warning(str(exc))
        return
    except SearchProjectNotFoundError as exc:
        st.warning(str(exc))
        return
    except SQLAlchemyError as exc:
        st.error(format_db_error(exc))
        return
    except Exception as exc:
        st.error(f"搜索失败：{exc}")
        return

    st.caption(
        f"共 {response.total_count} 条命中，返回 {response.returned_count} 条，"
        f"耗时 {response.duration_ms} ms，scopes={', '.join(response.scopes_executed)}"
    )

    if not response.hits:
        st.info("未找到匹配结果。")
        return

    for idx, hit in enumerate(response.hits):
        row = search_hit_row(hit)
        with st.expander(
            f"[{row['hit_type']}] {row['title']} — score {row['relevance_score']}",
            expanded=idx < 3,
        ):
            st.write(row.get("snippet") or "")
            uid_parts = [
                f"**{k}**: `{v}`"
                for k, v in row.items()
                if k.endswith("_uid") and v
            ]
            if uid_parts:
                st.markdown(" | ".join(uid_parts))
            if hit.evidence_uid:
                if st.button("查看证据详情", key=f"evidence_{hit.evidence_uid}_{idx}"):
                    st.session_state["evidence_uid_filter"] = hit.evidence_uid
                    st.switch_page("pages/evidence.py")


render()
