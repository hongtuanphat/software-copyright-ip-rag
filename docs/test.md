Hãy đọc và audit **toàn bộ source code của project này**, không chỉ một vài file riêng lẻ. Mục tiêu là kiểm tra xem code hiện tại có **mâu thuẫn logic, code thừa, code cũ còn sót, duplication, dead code, logic không đồng nhất hoặc thay đổi trước đó chưa được dọn sạch** hay không.

**Quan trọng:** Không tự ý sửa code. Chỉ phân tích và báo cáo vấn đề. Không đề xuất refactor lớn nếu chưa xác định rõ vấn đề thực tế.

Hãy kiểm tra theo các nhóm sau:

### 1. Logic consistency

* Kiểm tra cùng một khái niệm/biến/config nhưng được xử lý khác nhau ở các file/module.
* Tìm các logic mâu thuẫn nhau giữa production, evaluation, API, UI và các script.
* Kiểm tra thứ tự xử lý có hợp lý không: input → preprocessing → retrieval → reranking → generation → citation/refusal → output.
* Tìm trường hợp một module giả định A nhưng module phía trước thực tế trả về B.
* Kiểm tra các giá trị mặc định, threshold, flag, enum, status có bị hiểu khác nhau ở các nơi không.
* Kiểm tra các nhánh `if/else`, fallback, exception handling có làm sai luồng chính không.
* Kiểm tra trường hợp error nhưng code lại tiếp tục xử lý như success.

### 2. Code duplication / logic duplication

Tìm:

* Cùng một logic được implement ở nhiều file.
* Cùng một constant/config nhưng hardcode nhiều nơi.
* Cùng một hàm xử lý nhưng tồn tại nhiều phiên bản.
* Các đoạn code gần như giống nhau nhưng behavior khác nhau.
* Logic đã được chuyển sang module mới nhưng implementation cũ vẫn còn được gọi ở đâu đó.

Với mỗi duplication, xác định:

* Hai đoạn code nằm ở đâu.
* Có thực sự duplicate hay chỉ giống bề ngoài.
* Chúng có thể tạo ra behavior không đồng nhất hay không.

### 3. Dead code / unused code

Tìm:

* Function không còn được gọi.
* Class không còn được sử dụng.
* Import không dùng.
* Constant/config không được sử dụng.
* File/module cũ không còn nằm trong runtime flow.
* Branch/condition không bao giờ xảy ra.
* Fallback cũ đã bị thay thế nhưng vẫn còn code.
* Commented-out code hoặc implementation cũ còn sót.
* Code được giữ lại từ phiên bản trước nhưng không còn phù hợp architecture hiện tại.

Phân biệt rõ:

* **Definitely dead**: chắc chắn không được sử dụng.
* **Potentially dead**: có khả năng được sử dụng nhưng chưa đủ bằng chứng.
* **Active**: đang được sử dụng.

### 4. Old implementation / replacement không sạch

Đặc biệt kiểm tra các trường hợp:

`old implementation → new implementation`

nhưng:

* code cũ vẫn được import;
* một số nơi vẫn gọi implementation cũ;
* config cũ vẫn tồn tại;
* tên biến/hàm cũ vẫn được dùng;
* documentation/comment mô tả behavior cũ;
* có hai pipeline cùng tồn tại;
* một phần code dùng logic mới, phần khác dùng logic cũ.

Hãy truy vết **call graph / dependency flow** để xác định implementation nào thực sự chạy runtime.

### 5. Configuration consistency

Kiểm tra toàn bộ config/constant/threshold:

* Có hardcode cùng một giá trị ở nhiều nơi không?
* Production và evaluation có dùng config khác nhau không?
* Có config được khai báo nhưng bị override ở nơi khác không?
* Có default value khác nhau giữa các module không?
* Có parameter được truyền vào nhưng thực tế không được sử dụng không?
* Có parameter được khai báo nhưng bị hardcode bên trong function không?

Đặc biệt tìm các trường hợp kiểu:

`config.X = 0.35`

nhưng nơi khác lại:

`if score < 0.5`

mà không có lý do rõ ràng.

### 6. Data flow / type / contract mismatch

Theo dõi dữ liệu xuyên suốt hệ thống:

`input → processing → retrieval → ranking → generation → citation/refusal → output`

Kiểm tra:

* field bị đổi tên nhưng nơi sử dụng chưa đổi;
* field có thể là `None` nhưng code giả định luôn có giá trị;
* list/dict/object có format khác nhau giữa producer và consumer;
* function return một cấu trúc nhưng caller xử lý như cấu trúc khác;
* ID format không nhất quán;
* status/error/success được biểu diễn khác nhau;
* `True/False/None` bị hiểu không giống nhau ở các module.

### 7. Evaluation code

Audit riêng toàn bộ evaluation pipeline.

Kiểm tra:

* evaluation có thực sự đánh giá đúng production behavior không;
* metric có đúng với định nghĩa được sử dụng không;
* có metric nào bị tính sai do implementation không;
* có hardcode kết quả/label/flag không;
* có leakage từ test label vào runtime/evaluation không;
* có dùng field chỉ tồn tại vì test dataset để quyết định behavior hay không;
* `refused`, `status`, `gold_ids`, `retrieved_ids`, `citations` có được xử lý nhất quán không;
* error có bị tính như success/refusal không;
* skip/error có làm sai denominator của metric không;
* các baseline có được chạy theo cùng một quy ước hay không.

Đặc biệt phân biệt:

* code phục vụ **runtime**
* code phục vụ **evaluation**
* code chỉ phục vụ **debug/audit**

Không được coi chúng là cùng một flow nếu thực tế khác nhau.

### 8. Runtime flow

Hãy dựng lại flow thực tế của application từ entry point.

Xác định:

1. Entry point là file/function nào.
2. Module nào được gọi tiếp theo.
3. Dữ liệu đi qua những module nào.
4. Module nào thực sự quyết định retrieval/refusal/generation/citation.
5. Các fallback/error path.
6. Những file/function nào KHÔNG nằm trong runtime flow.

Sau đó kiểm tra xem architecture/documentation có khớp với runtime thực tế không.

### 9. Import/dependency problems

Tìm:

* circular import;
* import thừa;
* import module cũ;
* dependency không còn cần;
* module phụ thuộc ngược architecture;
* function import từ module không còn là source of truth;
* cùng một dependency được wrapper nhiều lớp không cần thiết.

### 10. Hidden bugs do code cũ / code thừa

Tập trung tìm những lỗi khó nhìn thấy, ví dụ:

* Có hai implementation cùng tên hoặc cùng mục đích.
* Một implementation mới được tạo nhưng một caller vẫn dùng implementation cũ.
* Function có parameter mới nhưng caller không truyền.
* Config mới tồn tại nhưng code vẫn dùng constant cũ.
* Một field đã đổi tên nhưng chỉ một phần code được cập nhật.
* Exception bị catch quá rộng làm che mất lỗi thật.
* Fallback vô tình biến lỗi thành success.
* Một flag có tên giống nhau nhưng semantics khác nhau.
* Evaluation code có logic khác production mà không được chủ ý.
* Code nhìn như đang được sử dụng nhưng thực tế không bao giờ chạy.
* Code không chạy ở happy path nhưng chạy ở edge case và gây behavior sai.

### 11. Không chỉ tìm lỗi syntax

Không cần tập trung vào lỗi style/formatting nếu chúng không ảnh hưởng behavior.

Ưu tiên phát hiện:

**P0 – Critical**
Có thể làm sai kết quả hoặc phá vỡ runtime.

**P1 – High**
Có thể làm behavior không nhất quán hoặc sai trong một số trường hợp thực tế.

**P2 – Medium**
Code thừa/duplication/dead code có khả năng gây maintenance bug hoặc gây hiểu nhầm.

**P3 – Low**
Cleanup/documentation/minor consistency.

### Output bắt buộc

Trước tiên đưa ra:

**A. Tổng quan architecture/runtime flow hiện tại**

Sau đó lập bảng:

| # | Severity | Category | File | Function/Line | Vấn đề | Bằng chứng | Ảnh hưởng | Có chắc chắn không? |
| - | -------- | -------- | ---- | ------------- | ------ | ---------- | --------- | ------------------- |

Không chỉ nói "có duplication" hoặc "có dead code". Phải chỉ rõ **ở đâu và tại sao xác định như vậy**.

Sau bảng, chia riêng:

### B. Logic conflicts

Liệt kê các logic mâu thuẫn nhau.

### C. Duplicate implementations

Liệt kê các implementation trùng/chồng chéo.

### D. Dead / obsolete code

Liệt kê code chết hoặc code cũ còn sót.

### E. Configuration inconsistencies

Liệt kê config/threshold/default bị lệch.

### F. Data-flow / contract mismatches

Liệt kê producer-consumer mismatch.

### G. Evaluation inconsistencies

Liệt kê những điểm evaluation không khớp production hoặc metric implementation có vấn đề.

### H. Runtime-unused code

Liệt kê những file/function/class không nằm trong runtime flow nhưng vẫn tồn tại.

### I. Recommended cleanup order

Đề xuất thứ tự xử lý theo mức độ ảnh hưởng:

1. Critical logic bug
2. Runtime behavior inconsistency
3. Evaluation correctness issue
4. Obsolete implementation
5. Duplication
6. Dead code
7. Cleanup

**Không tự ý sửa bất kỳ file nào.**

Nếu không chắc một đoạn code là dead code hoặc obsolete, phải ghi rõ **"Potential"** và nêu bằng chứng còn thiếu thay vì kết luận chắc chắn.

Mục tiêu của audit là trả lời chính xác câu hỏi:

> **"Code hiện tại có thực sự chạy đúng một logic thống nhất từ đầu đến cuối không, hay đang tồn tại nhiều phiên bản/logic cũ mới chồng lên nhau khiến behavior không còn nhất quán?"**

Hãy đọc code theo **dependency và runtime flow**, không chỉ đọc từng file độc lập.
