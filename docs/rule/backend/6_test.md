# 6. TEST (BACKEND)

## Mục đích
Kiểm thử chuyên sâu module Backend.

## Các Test Case Cụ thể
1. **Unit Test - `build_index_text()`:**
   - Input: Object `Provision` có Điều 1, Khoản 2, Nội dung "Test".
   - Expected Output: `[Luật SHTT] Điều 1. Khoản 2. Test` (đã qua pyvi tokenize).
2. **Unit Test - RRF Math:**
   - Mock 3 mảng kết quả với ID cố định.
   - Tính toán tay và so khớp với kết quả từ `retriever.py` để chứng minh `k=15` hoạt động chính xác.
3. **Integration Test - Embedder Fallback:**
   - Thay đổi tên mô hình thành chuỗi không tồn tại. Chạy script.
   - Expected: Hệ thống throw Exception và dừng chương trình (Không sử dụng HashingFallback).
4. **Integration Test - Gate Leakage Verification:**
   - Đưa một câu hỏi ngoài lề (Nhóm 5) chưa từng xuất hiện trong tập train/dev.
   - Kiểm tra xem ngưỡng Cosine 0.22 hoặc Distractor có phát huy tác dụng chặn không, thay vì chỉ dựa vào Keyword matching.
