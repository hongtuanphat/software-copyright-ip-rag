Các mục sau thường phụ thuộc mục trước, cần làm theo thứ tự này sẽ ít phải làm lại. Hãy làm **mục 1, 2, 3, 8, 9**. Năm mục này loại bỏ gần hết rủi ro trả lời sai và lỗi lộ ra người dùng.

## Nhóm 1: Phải sửa trước (sai đáp án pháp lý)

1. **Áp trạng thái sửa đổi một phần vào từng điều (P0-01).** Khi crawler báo `con_hieu_luc_mot_phan`, phải đánh dấu đúng các provision bị sửa (`bi_sua_doi`, `effective_to`, `replaced_by`). Hiện chunk vẫn là `hieu_luc` nên hệ thống trích dẫn nội dung đã cũ. Đây là lỗi nặng nhất.
2. **Bỏ fallback sang mock khi lỗi mạng (P0-02).** Khi không lấy được dữ liệu thật thì báo "chưa xác minh" hoặc giữ nguyên trạng thái cũ, không được dùng dữ liệu mẫu để cập nhật hiệu lực.
3. **Chặn hit có điểm 0 trong BM25/hybrid.** Bạn đã chứng minh `score=0.0` vẫn trả về hit. Cần ngưỡng điểm thống nhất cho dense, BM25 và hybrid, để câu hỏi không liên quan đi vào nhánh từ chối thay vì bị trả lời bằng ngữ cảnh rác. Việc này nhỏ nhưng ảnh hưởng trực tiếp đến độ đúng.
4. **Đồng bộ `MONITORED_LAWS` với watchlist của crawler** (hiện 1 so với 3 văn bản). Nếu không, mục 1 vẫn bỏ sót các văn bản còn lại.

## Nhóm 2: Toàn vẹn dữ liệu (làm ngay sau nhóm 1)

5. **Rebuild corpus và FAISS index sau khi sửa mục 1-2**, rồi kiểm tra số ID của `chunks.jsonl` khớp với index.
6. **Kiểm tra tính nhất quán của dữ liệu** trong quá trình cập nhật, đảm bảo không có dữ liệu bị mất hoặc trùng lặp.
7. **Thêm manifest cho corpus và index** (hash nguồn, model embedding, số chiều, thời gian build), và sửa `build_corpus()` để cache không bị dùng khi nguồn đã đổi.

## Nhóm 3: Ổn định khi chạy thật

8. **Bọc lời gọi Gemini bằng timeout, retry/backoff có giới hạn** và trả về thông báo lỗi chuẩn khi thất bại. Hiện retry chỉ có trong evaluation, runtime thì không.
9. **Không hiển thị `str(e)` ra UI.** Chỉ hiện thông báo thân thiện, ghi chi tiết lỗi vào log.
11. **Giới hạn độ dài input** và xử lý input rỗng/bất thường.