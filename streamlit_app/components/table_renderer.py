"""
表格渲染器
==========

通用表格渲染：把 Analyzer 输出的 tables 数据 → Streamlit 表格
"""

import pandas as pd
import streamlit as st


def render_table(table_data: dict, key: str = None):
    """根据 table_data 渲染表格

    Args:
        table_data: {
            "title": str,
            "headers": list,
            "rows": list[list]
        }
        key: Streamlit 唯一 key
    """
    title = table_data.get("title", "")
    headers = table_data.get("headers", [])
    rows = table_data.get("rows", [])

    if not headers or not rows:
        st.info(f"表格 '{title}' 无数据")
        return

    if title:
        st.subheader(title)

    # 转为 DataFrame
    df = pd.DataFrame(rows, columns=headers)
    st.dataframe(df, use_container_width=True, hide_index=True, key=key)


def render_tables(tables_data: list, key_prefix: str = "table"):
    """批量渲染多个表格"""
    if not tables_data:
        st.info("暂无表格数据")
        return

    for i, table in enumerate(tables_data):
        render_table(table, key=f"{key_prefix}_{i}")
        st.markdown("---")  # 表格间隔


def render_simple_dict_table(
    title: str,
    data: dict,
    key: str = None,
    two_col: bool = True,
):
    """简单字典表格（2 列：键 / 值）"""
    if title:
        st.subheader(title)
    if two_col:
        df = pd.DataFrame(
            [(k, v) for k, v in data.items()],
            columns=["指标", "数值"]
        )
    else:
        df = pd.DataFrame(
            [(k, v) for k, v in data.items()],
            columns=["Key", "Value"]
        )
    st.dataframe(df, use_container_width=True, hide_index=True, key=key)
