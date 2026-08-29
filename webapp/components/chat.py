from __future__ import annotations

import uuid

import streamlit as st


def _render_user_msg(content: str) -> None:
    """Render tin nhắn của người dùng."""
    with st.chat_message("user"):
        st.write(content)


def _build_sources_html(sources: list[dict]) -> str:
    """Xây dựng HTML cho phần Căn cứ pháp lý. Trả về chuỗi rỗng nếu không có sources."""
    if not sources:
        return ""

    parts: list[str] = []
    parts.append("<hr style='margin: 1.5rem 0 1.2rem 0; border: none; border-top: 1px solid rgba(15, 23, 42, 0.1);' />")
    parts.append("<div style='font-weight: 600; margin-bottom: 1rem; color: #0f172a; text-transform: uppercase; font-size: 0.9rem; letter-spacing: 0.05em;'>CĂN CỨ PHÁP LÝ</div>")

    for i, src in enumerate(sources):
        law_code   = src.get("law_code", "")
        article_no = src.get("article_no", "")
        clause_no  = src.get("clause_no", "")
        raw_status = src.get("status", "hieu_luc")
        quote      = src.get("text", "").replace("\n", "<br>")

        law_name  = src.get("law_name", "Văn bản")
        doc_title = f"{law_name} {law_code}".strip() if law_code else src.get("title", f"Nguồn {i+1}")

        clause_parts = []
        if clause_no:
            c = str(clause_no)
            clause_parts.append(c if c.lower().startswith(("khoản", "điểm")) else f"Khoản {c}")
        if article_no:
            a = str(article_no)
            clause_parts.append(a if a.lower().startswith("điều") else f"Điều {a}")

        clause_text  = ", ".join(clause_parts) or src.get("title", "Chi tiết điều khoản")
        status       = "Còn hiệu lực" if raw_status == "hieu_luc" else "Hết hiệu lực" if raw_status == "het_hieu_luc" else "Còn hiệu lực"
        status_color = "#16a34a" if status == "Còn hiệu lực" else "#dc2626"

        parts.append(f"""<div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 1rem; margin-bottom: 0.8rem; box-shadow: 0 1px 2px rgba(0,0,0,0.05);"><details style="cursor: pointer;"><summary style="display: flex; justify-content: space-between; align-items: center; user-select: none;"><div style="display: flex; align-items: center; flex-wrap: wrap; gap: 12px;"><span style="font-weight: 600; color: #0f172a; font-size: 0.95rem;">[{i+1}] {doc_title}</span><span style="color: #334155; font-size: 0.9rem;">{clause_text}</span><span style="display: flex; align-items: center; color: {status_color}; font-weight: 500; font-size: 0.85rem;"><span style="font-size: 1rem; margin-right: 4px;">●</span> {status}</span></div><div style="color: #2563eb; font-weight: 500; font-size: 0.85rem; white-space: nowrap; margin-left: 1rem;">Xem điều khoản &gt;</div></summary><div style="margin-top: 1rem; padding: 1rem; background-color: #f8fafc; border-left: 3px solid #cbd5e1; border-radius: 4px; color: #475569; font-size: 0.9rem; line-height: 1.6;">"{quote}"</div></details></div>""")

    parts.append("""<div style="margin-top: 1.5rem; font-size: 0.85rem; color: #64748b; font-style: italic; line-height: 1.5;">Lưu ý: Câu trả lời được tổng hợp từ cơ sở dữ liệu pháp luật của hệ thống và chỉ mang tính chất tham khảo. Đối với các trường hợp cụ thể, nên đối chiếu với văn bản pháp luật hiện hành trước khi đưa ra quyết định.</div>""")

    return "".join(parts)


def _render_bot_content(content: str, sources: list[dict]) -> None:
    """Render nội dung câu trả lời bot bên trong một st.chat_message("assistant") context."""
    st.write(content)
    sources_html = _build_sources_html(sources)
    if sources_html:
        st.markdown(sources_html, unsafe_allow_html=True)


def _render_bot_msg(message: dict) -> None:
    """Render một tin nhắn bot từ history (dùng trong render_chat_messages)."""
    with st.chat_message("assistant"):
        _render_bot_content(message["content"], message.get("sources", []))


# API

def render_chat_messages() -> None:
    """Pure render: hiển thị lịch sử chat từ session_state. Không có side effects."""
    for message in st.session_state.get("messages", []):
        if message["role"] == "user":
            _render_user_msg(message["content"])
        else:
            _render_bot_msg(message)


def handle_chat_interaction(prompt: str) -> None:
    """
    Render user message ngay lập tức, gọi RAG và render
    kết quả inline trong cùng lượt execution.

    st.rerun() chỉ được gọi sau khi toàn bộ lượt xử lý hoàn tất, để sidebar
    cập nhật recent_matters — không phải để render messages.
    """

    # 1. Lưu user message vào state
    st.session_state["messages"].append({"role": "user", "content": prompt})

    # 2. Render user message ngay — user thấy câu hỏi trước khi RAG chạy
    _render_user_msg(prompt)

    # 3. Gọi RAG và render assistant response ngay bên dưới câu hỏi
    with st.chat_message("assistant"):
        with st.spinner("Đang tra cứu cơ sở dữ liệu pháp luật..."):
            try:
                from pipeline import answer_rag
                res           = answer_rag(prompt)
                bot_content   = res.get("answer", "")
                bot_sources   = res.get("citations", [])
                active_alerts = res.get("active_alerts", [])

                if active_alerts:
                    alert_msgs  = [f"[Cảnh báo hiệu lực văn bản] {a.get('message', '')}" for a in active_alerts]
                    bot_content = "\n\n".join(alert_msgs) + "\n\n---\n\n" + bot_content
            except Exception as e:
                bot_content = f"Lỗi kết nối Backend RAG: {e}"
                bot_sources = []

        _render_bot_content(bot_content, bot_sources)

    # 4. Lưu assistant message vào state (sau khi đã render xong)
    st.session_state["messages"].append({
        "role": "assistant",
        "content": bot_content,
        "sources": bot_sources,
    })

    # 5. Cập nhật sidebar matters
    matter = st.session_state.get("selected_matter", "Vụ mới")
    if matter == "Vụ mới":
        new_id    = str(uuid.uuid4())
        new_title = prompt[:30] + "..." if len(prompt) > 30 else prompt
        st.session_state["recent_matters"].insert(0, {"id": new_id, "title": new_title})
        st.session_state["selected_matter"] = new_id
        matter = new_id

    st.session_state["chats"][matter] = st.session_state["messages"].copy()

