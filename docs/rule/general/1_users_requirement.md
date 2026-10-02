# 1. USER'S REQUIREMENT (GENERAL)

## Mục đích
Mô tả yêu cầu tổng quát của người dùng và hệ thống cho dự án RAG Pháp luật Sở hữu trí tuệ (SHTT), tập trung vào nhóm quyền tác giả phần mềm.

## Nội dung chi tiết
* **Problem:** Người làm CNTT thường xuyên gặp vướng mắc pháp lý về sở hữu trí tuệ (hợp đồng thuê khoán, mã nguồn phái sinh). Ngôn ngữ luật phân tầng phức tạp, khó tra cứu. Các LLM thông thường gặp tình trạng "ảo giác" (hallucination) nghiêm trọng khi trả lời về pháp luật, tự bịa ra Điều, Khoản không tồn tại.
* **User need:** Cần một hệ thống chatbot nhận câu hỏi pháp lý tự nhiên, trả lời mạch lạc dựa trên luật hiện hành, và BẮT BUỘC cung cấp trích dẫn căn cứ pháp lý rõ ràng (tên văn bản, Điều, Khoản) để người dùng tự kiểm chứng.
* **System objective:** Xây dựng hệ thống Hybrid RAG chuyên biệt. Khắc phục điểm yếu của các công cụ tra cứu từ khóa (thiếu ngữ nghĩa) và LLM thuần (ảo giác).
* **Functional requirements:**
  - Tiền xử lý câu hỏi tự nhiên.
  - Tìm kiếm và trích xuất đoạn văn bản luật (chunk) liên quan nhất.
  - Sinh câu trả lời kèm trích dẫn nội tuyến `[số]`.
  - Nhận biết và từ chối trả lời (Refusal) đối với các câu hỏi nằm ngoài phạm vi hoặc thiếu căn cứ pháp lý (VD: hỏi về sáng chế, nhãn hiệu).
* **Scope & Constraint:**
  - Phạm vi dữ liệu (Corpus): Luật SHTT (VBHN 67), Nghị định 17/2023/NĐ-CP, Nghị định 134/2026/NĐ-CP.
  - Đối tượng: Tập trung sâu vào Bản quyền phần mềm (Chương trình máy tính).
  - Out-of-scope: Các lĩnh vực pháp luật khác, hoặc mảng Sở hữu công nghiệp (Sáng chế, Nhãn hiệu, Kiểu dáng công nghiệp) của Luật SHTT.
