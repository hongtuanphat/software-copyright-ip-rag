from __future__ import annotations

import streamlit as st


def render_sidebar() -> None:
    """Hiển thị thanh điều hướng bên trái cho không gian làm việc nghiên cứu pháp lý."""
    if st.sidebar.button("+ Đoạn chat mới", use_container_width=True, type="primary"):
        st.session_state["messages"] = []
        st.session_state["selected_matter"] = "Vụ mới"

    st.sidebar.caption("**GẦN ĐÂY**")
    matters = st.session_state.get("recent_matters", [])

    for matter in matters:
        if isinstance(matter, dict):
            matter_id = matter["id"]
            matter_title = matter["title"]
        else:
            matter_id = matter
            matter_title = matter
            
        if st.sidebar.button(matter_title, key=f"matter_{matter_id}", use_container_width=True):
            st.session_state["selected_matter"] = matter_id
            st.session_state["messages"] = st.session_state.get("chats", {}).get(matter_id, [])
