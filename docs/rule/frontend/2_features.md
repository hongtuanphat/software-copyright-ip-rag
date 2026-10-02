# 2. FEATURES (FRONTEND & DOCS)

## Mục đích
Các tính năng giao diện và tài liệu.

## Tính năng
1. **Giao diện Chat Streamlit:** Trình bày hộp thoại hỏi đáp theo phong cách hội thoại tự nhiên (Conversational UI).
2. **Selective Expander (Trích dẫn có chọn lọc):** UI Parser tự động phân tích câu trả lời của LLM, tìm kiếm các marker `[số]` (Ví dụ: `[1]`, `[3]`), sau đó đối chiếu với mảng `retrieval_hits` để render các hộp mở rộng (expander) chứa nội dung gốc của văn bản pháp luật đó.
3. **Báo cáo chuẩn học thuật:** Tài liệu `BAOCAO.txt` bao gồm bảng biểu số liệu (Bảng 2.3, 2.4, 4.1), phân rã nhóm lỗi, biểu diễn khoảng tin cậy 95% (CI), trích dẫn tài liệu tham khảo theo đúng chuẩn.
