"""
业务故事面板
============

渲染 Analyzer 输出的业务故事（Markdown 格式）
"""

import streamlit as st


def render_story(story: str, title: str = "📖 业务故事"):
    """渲染业务故事

    Args:
        story: Markdown 格式的故事文本
        title: 面板标题
    """
    if not story:
        st.info("暂无业务故事")
        return

    with st.expander(title, expanded=True):
        st.markdown(story)


def render_summary(summary: str, label: str = "一句话总结"):
    """渲染一句话总结（突出显示）"""
    if not summary:
        return
    st.markdown(
        f"### 💎 {label}\n\n"
        f"> {summary}"
    )


def render_anomalies(anomalies: list):
    """渲染异常告警"""
    if not anomalies:
        st.success("✅ 无异常告警")
        return

    st.markdown(f"### ⚠️ 异常告警 ({len(anomalies)} 个)")

    for a in anomalies:
        level = a.get("level", "info")
        message = a.get("message", "")
        category = a.get("category", "")

        if level == "critical":
            st.error(f"🔴 **[CRITICAL]** {message}")
        elif level == "warning":
            st.warning(f"🟠 **[WARNING]** {message}")
        else:  # info
            st.info(f"🟡 **[INFO]** {message}")


def render_insights(insights: list):
    """渲染关键洞察"""
    if not insights:
        return

    st.markdown(f"### 💡 关键洞察 ({len(insights)} 条)")
    for insight in insights:
        st.markdown(f"- {insight}")
