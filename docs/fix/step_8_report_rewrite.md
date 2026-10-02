# BƯỚC 8: VIẾT LẠI BÁO CÁO (BAOCAO.TXT) DỰA TRÊN SỐ LIỆU MỚI

## 1. Mục tiêu
Chuẩn hóa lại văn phong và số liệu trong tài liệu Báo cáo, biến nó thành một văn bản khoa học trung thực và có độ tin cậy cao.

## 2. Vấn đề hiện tại (Theo bug.txt)
- Dùng từ ngữ phóng đại: "chính xác tuyệt đối", "cực kỳ tối ưu", "giải quyết triệt để". Coi việc chia chunk Điều/Khoản là "tính mới" (trong khi nó rất phổ biến).
- Viết "hơn 17.14% so với phương pháp tốt nhất đơn lẻ", gây hiểu lầm là tăng System Accuracy, thực chất chỉ là trừ 2 số Recall.
- Còn sót các ghi chú nháp trong quá trình làm báo cáo ("Lưu ý khi soạn câu gold"). Thiếu tài liệu tham khảo cho BM25, FAISS, Sentence-BERT, RRF.
- Lặp text ở Hình 3.2. Ví dụ Nhóm 4 chưa rõ ràng.
- Dữ liệu dùng cho evaluation chưa được kiểm tra tính rò rỉ, có thể dẫn đến kết quả evaluation không chính xác.

## 3. Kế hoạch hành động chi tiết
- **Quét và Thay thế Text (Văn phong học thuật):**
  - Loại bỏ hoàn toàn các trạng từ/tính từ khẳng định quá mức. Thay bằng: "cải thiện", "tối ưu hóa", "đạt hiệu suất cao trong điều kiện thực nghiệm".
  - Mô tả đóng góp thực tế: "Áp dụng và tối ưu RAG tiếng Việt cho mảng SHTT", thay vì khẳng định là "tính mới kỹ thuật".
- **Sửa bảng biểu và số liệu:**
  - Trích xuất 100% số liệu từ output JSON của Bước 6.
  - Viết lại câu "+17.14%" thành: "Về mặt định vị Điều luật (Article Recall@5), phương pháp Hybrid đạt XX%, cao hơn YY điểm phần trăm so với nhánh BM25 đơn lẻ".
- **Bổ sung Reference & Dọn dẹp:**
  - Ghi đầy đủ tác giả cho các kỹ thuật: Robertson & Zaragoza (BM25), Johnson et al. (FAISS), Reimers & Gurevych (Sentence-BERT), Cormack et al. (RRF).
  - Xóa mọi lời ghi chú (Draft notes). Chọn ví dụ khác cho Hình 3.2 để thể hiện rõ khả năng Soft Refusal.
- **Kiểm tra và Tái cấu trúc Evaluation Dataset:**
  - Thực hiện `run_refusal_metrix.py` để trích xuất các câu bị đánh chặn. 
  - So sánh danh sách câu bị đánh chặn với tập câu hỏi dùng để sinh "Câu trả lời Vàng" (Ground Truth).
  - Di chuyển các câu bị đánh chặn ra khỏi tập test nếu phát hiện sự trùng lặp (Data Leakage). Nếu không thể di chuyển, cần ghi chú rõ ràng trong báo cáo về "Training-serving skew".

## 4. Nghiệm thu
- Mở `BAOCAO.txt`. Đọc kiểm tra toàn bộ. Dò lại Bảng B.1, B.2 với số trên code. Không còn từ ngữ over-claim. Tài liệu tham khảo đầy đủ. -> PASS (HOÀN TẤT DỰ ÁN).
