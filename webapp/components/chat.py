from __future__ import annotations

import uuid

import streamlit as st


def _render_user_msg(content: str) -> None:
    """Render tin nhắn của người dùng."""
    with st.chat_message("user"):
        st.write(content)


import re

def _render_bot_content(content: str, sources: list[dict]) -> None:
    """Render nội dung câu trả lời bot bên trong một st.chat_message("assistant") context."""
    
    used_indices = []
    if sources:
        for i in range(len(sources)):
            if f"[{i+1}]" in content:
                used_indices.append(i)
                
    old_to_new = {old_i + 1: new_idx for new_idx, old_i in enumerate(used_indices, 1)}
    
    def replace_tag(match):
        old_num = int(match.group(1))
        if old_num in old_to_new:
            return f"[{old_to_new[old_num]}]"
        return match.group(0)

    display_content = re.sub(r'\[(\d+)\]', replace_tag, content) if sources else content
    st.write(display_content)
    
    if used_indices:
        st.divider()
        st.caption("**CĂN CỨ PHÁP LÝ**")
        for new_idx, old_i in enumerate(used_indices, 1):
            src = sources[old_i]
            law_code   = src.get("law_code", "")
            article_no = src.get("article_no", "")
            clause_no  = src.get("clause_no", "")
            raw_status = src.get("status", "hieu_luc")
            
            # Sửa lỗi không xuống dòng: thay 1 dấu \n bằng 2 dấu \n để Markdown tách paragraph
            quote = src.get("text", "").replace("\n", "\n\n")
            
            law_name  = src.get("law_name", "Văn bản")
            doc_title = f"{law_name} {law_code}".strip() if law_code else src.get("title", f"Nguồn {old_i+1}")
            
            clause_parts = []
            if clause_no:
                c = str(clause_no)
                clause_parts.append(c if c.lower().startswith(("khoản", "điểm")) else f"Khoản {c}")
            if article_no:
                a = str(article_no)
                clause_parts.append(a if a.lower().startswith("điều") else f"Điều {a}")
                
            clause_text  = ", ".join(clause_parts) or src.get("title", "Chi tiết điều khoản")
            status       = "Còn hiệu lực" if raw_status == "hieu_luc" else "Hết hiệu lực" if raw_status == "het_hieu_luc" else "Còn hiệu lực"
            
            with st.expander(f"[{new_idx}] {doc_title} - {clause_text} ({status})"):
                st.markdown(quote)
                
        st.caption("*Lưu ý: Câu trả lời được tổng hợp từ cơ sở dữ liệu pháp luật của hệ thống và chỉ mang tính chất tham khảo. Đối với các trường hợp cụ thể, nên đối chiếu với văn bản pháp luật hiện hành trước khi đưa ra quyết định.*")


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

