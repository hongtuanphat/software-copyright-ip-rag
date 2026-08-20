from __future__ import annotations

import html
import time
import uuid

import streamlit as st


def _render_user_msg(content: str) -> None:
    """Render HTML cho tin nhắn của người dùng."""
    safe_content = html.escape(content)
    st.markdown(
        f"""
        <div style="display:flex; justify-content:flex-end; margin-bottom:1.5rem;">
            <div style="background-color: #1e3a8a; color: #ffffff; padding: 1rem 1.5rem; border-radius: 20px; border-bottom-right-radius: 4px; max-width: 80%;">
                {safe_content}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_bot_msg(message: dict) -> None:
    """Render HTML cho tin nhắn của bot (kèm citation)."""
    sources = message.get("sources", [])
    sources_html = ""

    if sources:
        sources_html += "<hr style='margin: 1.5rem 0 1.2rem 0; border: none; border-top: 1px solid rgba(15, 23, 42, 0.1);' />"
        sources_html += "<div style='font-weight: 600; margin-bottom: 1rem; color: #0f172a; text-transform: uppercase; font-size: 0.9rem; letter-spacing: 0.05em;'>CĂN CỨ PHÁP LÝ</div>"

        for i, src in enumerate(sources):
            law_code  = src.get("law_code", "")
            article_no = src.get("article_no", "")
            clause_no  = src.get("clause_no", "")
            raw_status = src.get("status", "hieu_luc")
            quote      = src.get("text", "")

            law_name  = src.get("law_name", "Văn bản hợp nhất số") if "67/VBHN" in law_code else "Văn bản"
            doc_title = f"{law_name} {law_code}".strip() or src.get("title", f"Nguồn {i+1}")

            clause_parts = []
            if clause_no:
                c = str(clause_no)
                clause_parts.append(c if c.lower().startswith(("khoản", "điểm")) else f"Khoản {c}")
            if article_no:
                a = str(article_no)
                clause_parts.append(a if a.lower().startswith("điều") else f"Điều {a}")

            clause_text = ", ".join(clause_parts) or src.get("title", "Chi tiết điều khoản")
            status      = "Còn hiệu lực" if raw_status == "hieu_luc" else "Hết hiệu lực" if raw_status == "het_hieu_luc" else "Còn hiệu lực"
            status_color = "#16a34a" if status == "Còn hiệu lực" else "#dc2626"

            sources_html += f"""
            <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 1rem; margin-bottom: 0.8rem; box-shadow: 0 1px 2px rgba(0,0,0,0.05);">
                <details style="cursor: pointer;">
                    <summary style="display: flex; justify-content: space-between; align-items: center; user-select: none;">
                        <div style="display: flex; align-items: center; flex-wrap: wrap; gap: 12px;">
                            <span style="font-weight: 600; color: #0f172a; font-size: 0.95rem;">[{i+1}] {doc_title}</span>
                            <span style="color: #334155; font-size: 0.9rem;">{clause_text}</span>
                            <span style="display: flex; align-items: center; color: {status_color}; font-weight: 500; font-size: 0.85rem;">
                                <span style="font-size: 1rem; margin-right: 4px;">●</span> {status}
                            </span>
                        </div>
                        <div style="color: #2563eb; font-weight: 500; font-size: 0.85rem; white-space: nowrap; margin-left: 1rem;">
                            Xem điều khoản &gt;
                        </div>
                    </summary>
                    <div style="margin-top: 1rem; padding: 1rem; background-color: #f8fafc; border-left: 3px solid #cbd5e1; border-radius: 4px; color: #475569; font-size: 0.9rem; line-height: 1.6;">
                        "{quote}"
                    </div>
                </details>
            </div>
            """

        sources_html += """
        <div style="margin-top: 1.5rem; font-size: 0.85rem; color: #64748b; font-style: italic; line-height: 1.5;">
            Lưu ý: Câu trả lời được tổng hợp từ cơ sở dữ liệu pháp luật của hệ thống và chỉ mang tính chất tham khảo.
            Đối với các trường hợp cụ thể, nên đối chiếu với văn bản pháp luật hiện hành trước khi đưa ra quyết định.
        </div>
        """

    final_html = (
        "<div style='margin-bottom:1.5rem;'>"
        "<div style='background-color: #f1f5f9; color: #1e293b; padding: 1.2rem; border-radius: 12px; border: 1px solid rgba(15, 23, 42, 0.1);'>"
        f"<div style='line-height: 1.6;'>{message['content']}</div>"
        f"{sources_html}</div></div>"
    )
    st.markdown(final_html.replace("\n", ""), unsafe_allow_html=True)


def render_chat_messages() -> None:
    """Pure render: hiển thị lịch sử chat từ session_state. Không có side effects."""
    for message in st.session_state.get("messages", []):
        if message["role"] == "user":
            _render_user_msg(message["content"])
        else:
            _render_bot_msg(message)


def _get_mock_response(prompt: str) -> tuple[str, list]:
    """Trả về (bot_content, bot_sources) dựa trên prompt. Tách biệt khỏi UI logic."""
    if prompt == "Phần mềm có được bảo hộ quyền tác giả không?":
        return (
            "Có. Chương trình máy tính (phần mềm) được pháp luật Việt Nam bảo hộ dưới hình thức quyền tác giả. "
            "Cơ chế bảo hộ quy định rằng chương trình máy tính được bảo hộ như tác phẩm văn học, bất kể nó được thể hiện "
            "dưới dạng mã nguồn (source code) hay mã máy (object code). Quyền tác giả đối với chương trình máy tính phát "
            "sinh tự động ngay khi phần mềm được sáng tạo và định hình dưới một hình thức vật chất nhất định "
            "(như việc lưu mã nguồn trên ổ cứng), không phụ thuộc vào việc đã công bố hay đăng ký hay chưa.",
            [
                {
                    "provision_id": "67-VBHN-VPQH_Art14_Cl1",
                    "law_code": "67/VBHN-VPQH",
                    "article_no": "14",
                    "clause_no": "1",
                    "title": "Tác phẩm văn học, nghệ thuật và khoa học được bảo hộ quyền tác giả",
                    "text": (
                        "1. Tác phẩm văn học, nghệ thuật và khoa học được bảo hộ bao gồm: "
                        "a) Tác phẩm văn học, khoa học, sách giáo khoa, giáo trình và tác phẩm khác được thể hiện "
                        "dưới dạng chữ viết hoặc ký tự khác; b) Bài giảng, bài phát biểu và bài nói khác; "
                        "c) Tác phẩm báo chí; d) Tác phẩm âm nhạc; đ) Tác phẩm sân khấu; "
                        "e) Tác phẩm điện ảnh và tác phẩm được tạo ra theo phương pháp tương tự; "
                        "g) Tác phẩm mỹ thuật, mỹ thuật ứng dụng; h) Tác phẩm nhiếp ảnh; i) Tác phẩm kiến trúc; "
                        "k) Bản họa đồ, sơ đồ, bản đồ, bản vẽ liên quan đến địa hình, kiến trúc, công trình khoa học; "
                        "l) Tác phẩm văn học, nghệ thuật dân gian; m) Chương trình máy tính, sưu tập dữ liệu."
                    ),
                    "status": "hieu_luc",
                },
                {
                    "provision_id": "67-VBHN-VPQH_Art22_Cl1",
                    "law_code": "67/VBHN-VPQH",
                    "article_no": "22",
                    "clause_no": "1",
                    "title": "Quyền tác giả đối với chương trình máy tính, sưu tập dữ liệu",
                    "text": (
                        "Chương trình máy tính là tập hợp các chỉ dẫn được thể hiện dưới dạng lệnh, mã, lược đồ hoặc dạng khác, "
                        "khi gắn vào một phương tiện, thiết bị được vận hành bằng ngôn ngữ lập trình máy tính thì có khả năng "
                        "làm cho máy tính hoặc thiết bị thực hiện được công việc hoặc đạt được kết quả cụ thể. "
                        "Chương trình máy tính được bảo hộ như tác phẩm văn học, dù được thể hiện dưới dạng mã nguồn hay mã máy. "
                        "Tác giả và chủ sở hữu quyền tác giả đối với chương trình máy tính có quyền thỏa thuận bằng văn bản "
                        "với nhau về việc sửa chữa, nâng cấp chương trình máy tính. Tổ chức, cá nhân có quyền sử dụng hợp pháp "
                        "bản sao chương trình máy tính được làm một bản sao dự phòng để thay thế khi bản sao đó bị xóa, bị hỏng "
                        "hoặc không thể sử dụng nhưng không được chuyển giao cho tổ chức, cá nhân khác."
                    ),
                    "status": "hieu_luc",
                },
            ],
        )

    return (
        "Chưa tìm thấy căn cứ pháp lý phù hợp để trả lời câu hỏi này. "
        "Vì chưa có đủ cơ sở để đảm bảo tính chính xác, hệ thống không thể đưa ra kết luận "
        "nhằm tránh cung cấp thông tin thiếu căn cứ. Trường hợp cần làm rõ, bạn có thể cung cấp "
        "thêm bối cảnh của vấn đề đang được hỏi.",
        [],
    )


def handle_chat_interaction() -> None:
    """
    Event handler duy nhất: lắng nghe input, xử lý, cập nhật state, rerun.
    Không render message trực tiếp — render_chat_messages() là nguồn duy nhất render history.
    """
    # Lấy prompt từ chat_input hoặc pending_prompt (suggestion button)
    # Khi suggestion button được click, chat_input luôn trả về None
    prompt: str | None = st.chat_input("Đặt câu hỏi nghiên cứu pháp lý...")

    if "pending_prompt" in st.session_state:
        prompt = st.session_state.pop("pending_prompt")

    if not prompt:
        return  # Không có input → không có side effect nào xảy ra

    # ── Từ đây chỉ chạy khi thực sự có prompt ────────────────────────────────

    # 1. Cập nhật state với tin nhắn user
    st.session_state["messages"].append({"role": "user", "content": prompt})

    # 2. Xử lý response — time.sleep() chỉ chạy duy nhất tại đây, sau khi có prompt
    with st.spinner("Đang tra cứu dữ liệu pháp luật..."):
        time.sleep(1.5)  # Giả lập delay backend
        bot_content, bot_sources = _get_mock_response(prompt)

    # 3. Cập nhật state với tin nhắn bot
    st.session_state["messages"].append({
        "role": "assistant",
        "content": bot_content,
        "sources": bot_sources,
    })

    # 4. Cập nhật sidebar matters
    matter = st.session_state.get("selected_matter", "Vụ mới")
    if matter == "Vụ mới":
        new_id    = str(uuid.uuid4())
        new_title = prompt[:30] + "..." if len(prompt) > 30 else prompt
        st.session_state["recent_matters"].insert(0, {"id": new_id, "title": new_title})
        st.session_state["selected_matter"] = new_id
        matter = new_id

    st.session_state["chats"][matter] = st.session_state["messages"].copy()

    # 5. Rerun để render_chat_messages() render toàn bộ history từ state
    #    Luôn rerun: sidebar cần cập nhật, và history phải được render từ nguồn duy nhất
    st.rerun()

