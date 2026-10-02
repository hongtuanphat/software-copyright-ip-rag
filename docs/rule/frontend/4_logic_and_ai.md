# 4. LOGIC + AI (FRONTEND & DOCS)

## Mục đích
Mô tả logic xử lý giao diện và báo cáo.

## Logic Hiển thị Trích dẫn
1. Nhận `Text_output` từ LLM và danh sách `Hits` từ Retriever.
2. Quét regex `\[(\d+)\]` trên `Text_output` để thu được danh sách `UsedIDs`.
3. Tạo tập hợp (Set) các IDs đã dùng.
4. Lặp qua từng `doc` trong `Hits`:
   - Nếu `doc.id` nằm trong `UsedIDs`: Gọi `st.expander(doc.title).write(doc.content)`.
   - Nếu không: Bỏ qua (ẩn đi).

## Logic Chỉnh sửa Báo cáo (Tone & Manner)
- Các tên gọi RRF ba nhánh đổi thành "Hybrid RRF (k=15)".
- Các con số "hơn 17,14%" đổi thành "chênh lệch +12,86 điểm so với BM25" và "Đây là Article Recall@5, không phải phương pháp tốt nhất đơn lẻ".
- Định nghĩa lại công thức tính Accuracy trong text báo cáo cho đúng toán học. Bỏ hoàn toàn số ảo "63%".
