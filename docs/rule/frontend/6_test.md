# 6. TEST (FRONTEND & DOCS)

## Mục đích
Kiểm thử UI và soát lỗi báo cáo.

## Các Test Case Cụ thể
1. **UI Selective Citation Test:**
   - Dùng một Query nhóm 2, LLM trả về văn bản có chứa chuỗi `"theo quy định tại [2]"`.
   - Kiểm tra UI: Giao diện chỉ được phép render Expander cho tài liệu có ID là 2, các tài liệu khác trong top 5 phải bị ẩn đi.
2. **Report Consistency Check:**
   - (Ctrl + F) Tìm kiếm các từ: "tuyệt đối", "triệt để", "cực kỳ". Expect: Không tìm thấy.
   - Tìm kiếm tên gọi cũ của RRF. Expect: Không tìm thấy (Phải là RRF_K=15).
   - Kiểm tra xem Bảng B.1 và B.2 trong báo cáo có khớp với kết quả từ file `eval_results.json` mới nhất không. Kiểm tra độ phân giải của Ảnh Logo và phụ lục 100 câu test.
