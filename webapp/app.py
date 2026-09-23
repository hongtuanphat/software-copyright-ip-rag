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


def load_css() -> None:
    """Tải CSS tùy chỉnh."""
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
        page_title="IP LawBot",
        page_icon=icon_path,
        layout="wide",
        initial_sidebar_state="expanded",
    )

    load_css()           # 1 lần inject CSS
    initialize_session() # 1 lần khởi tạo state (no-op nếu state đã có)
    render_sidebar()     # render sidebar, no side effects ngoài button click

    is_processing = st.session_state.get("is_processing", False)

    # 1. Hướng input từ user (từ chat_input hoặc suggestion button)
    prompt = st.chat_input("Đặt câu hỏi nghiên cứu pháp lý...", disabled=is_processing)
    if "pending_prompt" in st.session_state:
        prompt = st.session_state.pop("pending_prompt")

    # Bắt đầu luồng xử lý câu hỏi mới
    if prompt and not is_processing:
        st.session_state["processing_prompt"] = prompt
        st.session_state["is_processing"] = True
        st.rerun()

    has_messages = bool(st.session_state.get("messages"))

    # 2. Không render Welcome nếu đang có interaction mới hoặc đang xử lý
    welcome_placeholder = st.empty()
    if not has_messages and not is_processing:
        with welcome_placeholder.container():
            render_welcome()
    else:
        welcome_placeholder.empty()
        if has_messages or is_processing:
            render_chat_messages()

    # 3. Xử lý interaction mới nếu có
    if is_processing and "processing_prompt" in st.session_state:
        p = st.session_state.pop("processing_prompt")
        handle_chat_interaction(p)
        st.session_state["is_processing"] = False
        st.rerun()

    st.markdown(
        '<div class="disclaimer-footer">IP LawBot là AI và có thể mắc sai sót. Xin vui lòng kiểm tra lại.</div>',
        unsafe_allow_html=True,
    )

if __name__ == "__main__":
    run_app()
