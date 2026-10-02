# BƯỚC 1: CHỐT KIẾN TRÚC THEO CODE THỰC TẾ

## 1. Mục tiêu
Thống nhất một bản mô tả kiến trúc duy nhất, làm nguồn sự thật (Source of Truth) để đối chiếu và sửa đổi toàn bộ mã nguồn cũng như báo cáo.

## 2. Vấn đề hiện tại (Theo bug.txt)
- Kiến trúc được mô tả không thống nhất trong tài liệu (lúc thì 2 nhánh, lúc thì 3 nhánh).
- Báo cáo và code dùng tên gọi không thống nhất cho RRF ba nhánh, trong khi các nhánh có trọng số bằng nhau.
- Refusal Gate được mô tả bằng 3-4 kiểu khác nhau ở các phần khác nhau trong báo cáo.
- Sử dụng các cách diễn đạt về cơ chế điều chỉnh trọng số gây hiểu lầm về khả năng thực tế và tối ưu hóa.
- Tài liệu rò rỉ dữ liệu từ tập đánh giá (ground truth) sang phần mô tả hệ thống.

## 3. Kế hoạch hành động chi tiết
- **Thống nhất kiến trúc Hybrid Retrieval:**
  - Đúng 3 nhánh: Dense (FAISS), Sparse (BM25), Entity (Regex bắt số Điều/Khoản).
  - Thuật toán dung hợp: **RRF với k = 15**. Các nhánh có trọng số 1:1:1 (ngang nhau).
  - Dùng thống nhất tên gọi "Hybrid RRF (k=15)" trong code và tài liệu.
- **Thống nhất kiến trúc Refusal Gate:**
  - Gồm 3 tầng bảo vệ: (1) Danh sách từ khóa ngoài phạm vi, (2) Ngưỡng ngữ nghĩa Cosine Similarity < 0.22, (3) Tỷ lệ tài liệu nhiễu (Distractor Ratio) tối đa 0.6.

## 4. Nghiệm thu
- Quét toàn bộ code và tài liệu để bảo đảm không còn tên gọi cũ của cơ chế RRF.
