# 1. USER'S REQUIREMENT (FRONTEND & DOCS)

## Mục đích
Mô tả các yêu cầu đối với Giao diện (UI) và Tài liệu Báo cáo (Docs).

## Yêu cầu chi tiết
* **Minh bạch hóa Trích dẫn (Citation Transparency):** Trên giao diện (Webapp Streamlit), người dùng chỉ được phép nhìn thấy những tài liệu (nguồn) mà LLM THỰC SỰ đã sử dụng để sinh ra câu trả lời. Không hiển thị lan man toàn bộ top 5 văn bản mà Retriever trả về nếu LLM không đả động đến.
* **Khách quan hóa Tài liệu Báo cáo:** Tài liệu dự án (`BAOCAO.txt`) phải phản ánh số liệu thực tế đo đạc được, mang tính hàn lâm, trung lập. Tuyệt đối không dùng các từ ngữ cảm tính ("chính xác tuyệt đối", "giải quyết triệt để", "cực kỳ tối ưu"). Phải đưa đúng trích dẫn tài liệu tham khảo theo quy định.
* **Tính nhất quán (Consistency):** Thiết kế kiến trúc và mô tả trong báo cáo phải trùng khớp 100% với những gì đã code dưới backend (ví dụ số lượng nhánh hybrid, ngưỡng threshold).
