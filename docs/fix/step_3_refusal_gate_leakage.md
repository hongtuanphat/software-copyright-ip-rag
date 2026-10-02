# BƯỚC 3: GỠ RÒ RỈ DỮ LIỆU Ở REFUSAL GATE (DATA LEAKAGE)

## 1. Mục tiêu
Làm sạch Cổng từ chối, đảm bảo hệ thống chặn câu hỏi ngoài phạm vi dựa trên năng lực ngữ nghĩa thực sự thay vì "học thuộc" tập test.

## 2. Vấn đề hiện tại (Theo bug.txt)
- File `OUT_OF_SCOPE_KEYWORDS` chứa các cụm chép y hệt nguyên văn câu hỏi trong test set (ví dụ: "mẫu biểu số mấy", "thư bảo lãnh ngân hàng", "phạt tiền hình sự tối đa"). 
- Hậu quả: 23/30 câu cần từ chối bị chặn đúng 100% bằng keyword, các tầng ngữ nghĩa (Cosine) gần như không đóng góp gì.

## 3. Kế hoạch hành động chi tiết
- **Dọn dẹp `OUT_OF_SCOPE_KEYWORDS`:**
  - Xóa toàn bộ các câu dài, cụm từ cụ thể chép từ tập test.
  - Chỉ giữ lại các danh từ/cụm danh từ mang tính chỉ định lĩnh vực (VD: "nhãn hiệu", "sáng chế", "kiểu dáng công nghiệp", "luật hình sự", "thuế").
- **Tạo tập dữ liệu Held-out Mù:**
  - Soạn thêm khoảng 30 đến 50 câu hỏi cho Nhóm 4 (Gần chủ đề, sai văn bản) và Nhóm 5c (Giả định sai, cần suy luận).
  - Không cho phép hệ thống "nhìn thấy" 30 câu hỏi này khi dev/tune rules.
- **Nâng cấp cơ chế phân loại (Optional nhưng Khuyến nghị):**
  - Chuyển cơ chế bắt keyword thành sử dụng Zero-shot Classification LLM Prompt nhẹ (nhằm phân định ý định câu hỏi) cho các nhóm khó như Nhóm 4, 5c.

## 4. Nghiệm thu
- Xóa các keyword rác. Chạy lại test trên Nhóm 5 cũ (đã xóa keyword). Cổng từ chối phải vẫn hoạt động hiệu quả nhờ Cosine Threshold < 0.22 -> PASS.
- Đưa tập 30 câu Held-out vào kiểm tra. Báo cáo Tỷ lệ Từ chối đúng (TRR) thực chất.
