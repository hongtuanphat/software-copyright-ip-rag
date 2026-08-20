"""Điểm khởi chạy ứng dụng Streamlit chính cho sản phẩm RAG nghiên cứu pháp lý."""
from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    project_root = Path(__file__).resolve().parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

import streamlit as st

from webapp.components.chat import render_chat_messages, handle_chat_interaction
from webapp.components.sidebar import render_sidebar
from webapp.components.welcome import render_welcome

_GOOGLE_FONTS_HTML = (
    "<link rel='preconnect' href='https://fonts.googleapis.com'>"
    "<link rel='preconnect' href='https://fonts.gstatic.com' crossorigin>"
    "<link href='https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap'"
    " rel='stylesheet'>"
)


def load_css() -> None:
    """Tải font và CSS tùy chỉnh. Chỉ được gọi 1 lần mỗi execution."""
    st.markdown(_GOOGLE_FONTS_HTML, unsafe_allow_html=True)
    css_path = Path(__file__).resolve().parent / "styles" / "main.css"
    if css_path.exists():
        css = css_path.read_text(encoding="utf-8")
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def initialize_session() -> None:
    """Khởi tạo session_state chỉ khi key chưa tồn tại — không ghi đè state hiện có."""
    defaults = {
        "messages": [],
        "recent_matters": [],
        "selected_matter": "Vụ mới",
        "chats": {},
    }
    for key, default in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default


def run_app() -> None:
    icon_path = str(Path(__file__).resolve().parent / "assets" / "icons" / "copyright.svg")
    st.set_page_config(
        page_title="Lexi",
        page_icon=icon_path,
        layout="wide",
        initial_sidebar_state="expanded",
    )

    load_css()           # 1 lần inject CSS + font
    initialize_session() # 1 lần khởi tạo state (no-op nếu state đã có)
    render_sidebar()     # render sidebar, no side effects ngoài button click

    has_messages = bool(st.session_state.get("messages"))
    has_pending  = "pending_prompt" in st.session_state

    if has_messages or has_pending:
        # has_pending=True + messages rỗng: render_chat_messages() không render gì
        # nhưng Welcome KHÔNG hiển thị — tránh flash trước khi handle xử lý prompt
        render_chat_messages()
    else:
        render_welcome()

    # Nơi DUY NHẤT xử lý event, state mutation, delay và rerun
    handle_chat_interaction()

    st.markdown(
        '<div class="disclaimer-footer">Lexi là AI và có thể mắc sai sót. Xin vui lòng kiểm tra lại.</div>',
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    run_app()
