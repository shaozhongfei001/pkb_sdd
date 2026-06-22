from __future__ import annotations

import json

import streamlit as st

from bootstrap import ensure_paths

ensure_paths()

from streamlit_admin.lib.repositories import (
    list_quality_reports,
    read_quality_report_json,
    read_quality_report_markdown,
    summarize_quality_report,
)
from streamlit_admin.lib.safe_paths import PathTraversalError


def render() -> None:
    st.header("质量报告")
    st.caption("只读浏览 reports_root 下的 008/009 报告文件。")

    if st.session_state.get("init_error"):
        st.error(st.session_state.init_error)
        return

    config = st.session_state.config
    reports_root = config.storage.reports_root

    reports = list_quality_reports(reports_root)
    if not reports:
        st.info(f"reports_root 下未找到质量报告：{reports_root}")
        return

    labels = {f"{r.name} ({r.kind})": r for r in reports}
    selected_label = st.selectbox("选择报告文件", options=list(labels.keys()))
    report = labels[selected_label]

    st.caption(f"路径: {report.path} | mtime: {report.mtime:.0f}")

    try:
        if report.kind == "summary_md":
            body = read_quality_report_markdown(reports_root, report.name)
            st.markdown(body)
        elif report.kind in ("quality_report_json", "summary_json"):
            data = read_quality_report_json(reports_root, report.name)
            summary = summarize_quality_report(data)
            st.markdown(
                f"- **report_type**: {summary.get('report_type') or report.kind}\n"
                f"- **generated_at**: {summary.get('generated_at') or ''}\n"
                f"- **issue_count**: {summary.get('issue_count', 0)}"
            )
            if summary.get("issue_codes"):
                st.markdown("**issue code 摘要**")
                st.json(summary["issue_codes"])
            with st.expander("JSON 原文"):
                st.json(data)
        else:
            st.warning(f"未知报告类型：{report.kind}")
    except PathTraversalError as exc:
        st.error(f"路径安全检查失败：{exc}")
    except json.JSONDecodeError as exc:
        st.error(f"JSON 解析失败 ({report.name})：{exc}")
    except OSError as exc:
        st.error(f"无法读取报告文件：{exc}")


render()
