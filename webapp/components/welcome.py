from __future__ import annotations

import streamlit as st


def render_welcome() -> None:
    """Render màn hình chào mừng khi không có context chat."""
    st.title("IP LawBot")
    st.subheader("Trợ lý AI hỗ trợ tra cứu Quyền tác giả đối với chương trình máy tính")

    suggestions = [
        "Phần mềm có được bảo hộ quyền tác giả không?",
        "Đăng ký quyền tác giả đối với phần mềm có bắt buộc không?",
        "Thời hạn bảo hộ quyền tác giả đối với phần mềm là bao lâu?",
        "Người sử dụng có được phép tự ý sao chép phần mềm không?",
    ]

    cols = st.columns(4)
    for i, sug in enumerate(suggestions):
        if cols[i].button(sug, use_container_width=True):
            st.session_state["pending_prompt"] = sug
            st.rerun()

