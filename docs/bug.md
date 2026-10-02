Mình xếp theo nguyên tắc: **sai nội dung pháp lý trước, rồi dữ liệu, rồi độ ổn định khi chạy, rồi khả năng triển khai và giám sát**. Các mục sau thường phụ thuộc mục trước, nên làm theo thứ tự này sẽ ít phải làm lại.

## Nhóm 1: Phải sửa trước (sai đáp án pháp lý)

1. **Áp trạng thái sửa đổi một phần vào từng điều (P0-01).** Khi crawler báo `con_hieu_luc_mot_phan`, phải đánh dấu đúng các provision bị sửa (`bi_sua_doi`, `effective_to`, `replaced_by`). Hiện chunk vẫn là `hieu_luc` nên hệ thống trích dẫn nội dung đã cũ. Đây là lỗi nặng nhất.
2. **Bỏ fallback sang mock khi lỗi mạng (P0-02).** Khi không lấy được dữ liệu thật thì báo "chưa xác minh" hoặc giữ nguyên trạng thái cũ, không được dùng dữ liệu mẫu để cập nhật hiệu lực.
3. **Chặn hit có điểm 0 trong BM25/hybrid.** Bạn đã chứng minh `score=0.0` vẫn trả về hit. Cần ngưỡng điểm thống nhất cho dense, BM25 và hybrid, để câu hỏi không liên quan đi vào nhánh từ chối thay vì bị trả lời bằng ngữ cảnh rác. Việc này nhỏ nhưng ảnh hưởng trực tiếp đến độ đúng.
4. **Đồng bộ `MONITORED_LAWS` với watchlist của crawler** (hiện 1 so với 3 văn bản). Nếu không, mục 1 vẫn bỏ sót các văn bản còn lại.

## Nhóm 2: Toàn vẹn dữ liệu (làm ngay sau nhóm 1)

5. **Rebuild corpus và FAISS index sau khi sửa mục 1-2**, rồi kiểm tra số ID của `chunks.jsonl` khớp với index.
6. **Xóa hoặc đổi tên `faiss.npy` cũ (1.326 ID)** để không ai nhầm với index đang dùng.
7. **Thêm manifest cho corpus và index** (hash nguồn, model embedding, số chiều, thời gian build), và sửa `build_corpus()` để cache không bị dùng khi nguồn đã đổi.

## Nhóm 3: Ổn định khi chạy thật

8. **Bọc lời gọi Gemini bằng timeout, retry/backoff có giới hạn** và trả về thông báo lỗi chuẩn khi thất bại. Hiện retry chỉ có trong evaluation, runtime thì không.
9. **Không hiển thị `str(e)` ra UI.** Chỉ hiện thông báo thân thiện, ghi chi tiết lỗi vào log.
10. **Validate JSON trả về từ Gemini** (đúng schema, đúng kiểu) và có nhánh dự phòng an toàn khi sai.
11. **Giới hạn độ dài input** và xử lý input rỗng/bất thường.

## Nhóm 4: Triển khai và vận hành

12. **Pin version trong `requirements.txt`** (hoặc dùng lockfile) để môi trường sạch cài ra đúng như hiện tại.
13. **Thêm logging có cấu trúc** thay cho `print()`, gồm request ID, thời gian retrieval và LLM, lỗi.
14. **Viết Dockerfile (hoặc lệnh khởi động rõ ràng) và health check**, kèm cách giữ dữ liệu/index bền vững.
15. **Chạy lại toàn bộ evaluation trên dev (100 câu) và heldout (30 câu)**, lưu kết quả cùng metadata. Mục này nên làm cuối cùng vì kết quả chỉ có ý nghĩa sau khi các lỗi ở trên đã được sửa.

## Nhóm 5: Làm sau (không chặn hoạt động bình thường)

16. Thêm test cho các tình huống lỗi: Gemini timeout, crawler lỗi, index hỏng, input xấu.
17. Rate limiting và xác thực (chỉ bắt buộc nếu triển khai public).
18. Thread-safety cho `_global_pipeline` và alert cache.
19. Gom CLI, evaluation và webapp về một service dùng chung.
20. Quy trình backup/restore và tự động rebuild index.

## Gợi ý lộ trình

- **Tuần đầu:** mục 1-7. Xong phần này là hệ thống không còn trả lời sai về hiệu lực pháp lý.
- **Tuần hai:** mục 8-14. Xong phần này là chạy ổn định cho người dùng thật.
- **Cuối cùng:** mục 15, rồi các việc nhóm 5 tùy phạm vi triển khai (nội bộ hay public).
    
Nếu chỉ có thời gian làm tối thiểu, hãy làm **mục 1, 2, 3, 8, 9**. Năm mục này loại bỏ gần hết rủi ro trả lời sai và lỗi lộ ra người dùng.