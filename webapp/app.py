"""Điểm khởi chạy ứng dụng Streamlit chính cho sản phẩm RAG nghiên cứu pháp lý."""
from __future__ import annotations

import sys
import time
from pathlib import Path

if __package__ in (None, ""):
    project_root = Path(__file__).resolve().parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

import streamlit as st
import config

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
        "query_timestamps": [],
        "last_query_time": 0.0,
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

    load_css()           # Nạp CSS
    initialize_session() # Khởi tạo state (bỏ qua nếu state đã tồn tại)
    render_sidebar()     # Hiển thị thanh bên (sidebar), không có tác động phụ ngoài hành động nhấn nút

    is_processing = st.session_state.get("is_processing", False)

    # 1. Hướng input từ user (từ chat_input hoặc suggestion button)
    # Giới hạn max_chars ở mức an toàn (khoảng 10 ký tự/từ) để tránh paste nội dung quá khủng
    prompt = st.chat_input("Đặt câu hỏi nghiên cứu pháp lý...", disabled=is_processing, max_chars=15000)
    if "pending_prompt" in st.session_state:
        prompt = st.session_state.pop("pending_prompt")

    # Bắt đầu luồng xử lý câu hỏi mới với bộ điều tiết tần suất (Rate Limiting)
    if prompt and not is_processing:
        now = time.time()
        last_time = st.session_state.get("last_query_time", 0.0)
        time_since_last = now - last_time

        # 1. Kiểm tra Cooldown giữa 2 lần gửi câu hỏi liên tiếp
        cooldown_sec = getattr(config, "RATE_LIMIT_COOLDOWN_SECONDS", 3.0)
        if time_since_last < cooldown_sec:
            remaining = cooldown_sec - time_since_last
            st.warning(f"Vui lòng đợi {remaining:.1f} giây trước khi gửi câu hỏi tiếp theo để tránh vượt hạn mức hệ thống.")
        else:
            word_count = len(prompt.split())
            if word_count > 1500:
                st.error(f"Câu hỏi của bạn quá dài ({word_count} từ). Vui lòng rút gọn nội dung dưới 1500 từ.")
            else:
                # 2. Kiểm tra Rate Limit theo cửa sổ trượt 60 giây (Requests per minute)
                max_rpm = getattr(config, "RATE_LIMIT_MAX_PER_MINUTE", 12)
                raw_timestamps = st.session_state.get("query_timestamps", [])
                valid_timestamps = [ts for ts in raw_timestamps if now - ts < 60.0]
                if len(valid_timestamps) >= max_rpm:
                    st.warning(f"Bạn đã gửi quá giới hạn cho phép ({max_rpm} câu/phút). Vui lòng đợi giây lát để hệ thống điều tiết hạn mức API.")
                else:
                    valid_timestamps.append(now)
                    st.session_state["query_timestamps"] = valid_timestamps
                    st.session_state["last_query_time"] = now
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
