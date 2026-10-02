# 5. IMPLEMENTATION (FRONTEND & DOCS)

## Mục đích
Đối chiếu UI và Báo cáo với thực trạng.

## Cấu trúc File
- `webapp/app.py`: Code giao diện.
- `docs/BAOCAO.txt`: File báo cáo toàn văn.
- `docs/bug.txt`, `docs/step.txt`: Log ghi chú sửa lỗi.

## Discrepancies & Issues (Theo bug.txt)
**DISCREPANCY 1:**
- *Intended:* Báo cáo trung thực, khách quan với các từ vựng hàn lâm, có trích dẫn nguồn đầy đủ (BM25, FAISS, Sentence-BERT, RRF).
- *Actual:* Báo cáo có giọng điệu phóng đại (over-claim). Mục 4.4.5 đánh giá latency "cực kỳ tối ưu" nhưng có ca trễ 35 giây do API retry chứ không phải do Reranking (hệ thống không hề có reranker).
- *Issue:* Mất độ tin cậy của tài liệu nghiên cứu. Thiếu tài liệu tham khảo cho BM25 (Robertson & Zaragoza), FAISS (Johnson et al.), Sentence-BERT (Reimers & Gurevych), RRF (Cormack et al.).
- *Fix Required:* Chỉnh sửa `BAOCAO.txt`. Bỏ các từ "giải quyết triệt để", "chính xác tuyệt đối". Báo cáo Median và p95 latency tách biệt. Xóa tất cả các ghi chú nội bộ (VD: "Lưu ý khi soạn câu trả lời gold").

**DISCREPANCY 2:**
- *Intended:* UI hiển thị minh bạch. Ví dụ nhóm 4 (Điều 59) nếu không được bảo hộ dưới danh nghĩa sáng chế thì phải trả lời rõ ràng.
- *Actual:* Hình 3.2 và ví dụ Nhóm 4 trả lời chưa rõ ràng. Cột nhãn bị lặp "Nghị định 17/2023/NĐ-CP 17/2023/NĐ-CP".
- *Fix Required:* Sửa nhãn lặp. Chọn lại ví dụ Nhóm 4 minh họa rõ ràng cơ chế Soft Refusal.
