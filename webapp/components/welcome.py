from __future__ import annotations

import streamlit as st


def render_welcome() -> None:
    """Render màn hình chào mừng khi không có context chat."""
    st.markdown(
        """
        <div style="display: flex; flex-direction: column; align-items: flex-start; justify-content: center; padding: 10vh 1rem 2rem 1rem;">
            <h1 style="font-size: 3rem; font-weight: 700; color: #0f172a;">LEXI</h1>
            <h5>Trợ lý AI hỗ trợ tra cứu Quyền tác giả đối với chương trình máy tính</h5>
        </div>
        """,
        unsafe_allow_html=True,
    )

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

