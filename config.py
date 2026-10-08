"""config.py

Tập hợp tất cả các thông số cấu hình và đường dẫn dùng chung trong toàn bộ hệ thống RAG.
Giúp dễ dàng tùy chỉnh mô hình, ngưỡng lọc và đường dẫn lưu trữ tại một nơi duy nhất.
"""
from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

# Tự động nạp các biến môi trường từ file .env nếu có
BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR
load_dotenv(BASE_DIR / ".env")

# Cấu hình các đường dẫn thư mục dữ liệu
DATA_DIR = BASE_DIR / "data"
DATA_RAW_DIR = DATA_DIR / "raw"
DATA_PROCESSED_DIR = DATA_DIR / "processed"

# Đường dẫn các file đầu ra đã qua xử lý (chunks, testset, vector index, alerts)
CHUNKS_PATH = DATA_PROCESSED_DIR / "chunks.jsonl"
ALERTS_PATH = DATA_PROCESSED_DIR / "alerts.jsonl"
FAISS_INDEX_PATH = DATA_PROCESSED_DIR / "faiss.index"

# ==========================================
# 2. LLM & GENERATION CONFIG
# ==========================================
EMBEDDING_MODEL_NAME = "bkai-foundation-models/vietnamese-bi-encoder"
GEMINI_MODEL_NAME = "gemini-3.5-flash-lite"
GEMINI_TEMPERATURE = 0.0  # Để 0 để mô hình trả lời ổn định, bám sát từng điều luật
GEMINI_MAX_TOKENS = 4096
GEMINI_MAX_ATTEMPTS = 3
GEMINI_RETRY_BASE_SECONDS = 1.0

# Phân loại chủ đề trong phạm vi và chủ đề gây nhiễu (distractor)
LAW_CODE = "67/VBHN-VPQH"

# Tham số truy hồi văn bản
TOP_K = 10
MAX_SEQ_LENGTH = 256
EMBEDDING_DIM = 768
RETRIEVAL_MODE = "hybrid"      # Chế độ truy hồi mặc định: "hybrid", "dense", hoặc "bm25"
RRF_K = 15                     # Hằng số chuẩn cho thuật toán Reciprocal Rank Fusion (tối ưu độ dốc điểm cho top đầu)
CANDIDATE_POOL_SIZE = 100       # Số lượng ứng viên lấy từ mỗi nhánh trước khi hợp nhất RRF

# Ngưỡng lọc và cổng từ chối (Refusal Gate)
MIN_SCORE_TIN_CAY = 0.22      # Điểm tương đồng ngữ nghĩa tối thiểu (Cosine Similarity) để xem kết quả là đáng tin
MAX_DISTRACTOR_RATIO = 0.6    # Tỷ lệ tối đa các đoạn distractor trong top-k
BM25_MIN_SCORE = 0.0          # BM25 chỉ cung cấp evidence khi có điểm dương

# Cơ chế phân loại ý định câu hỏi và kiểm soát từ chối mềm (Soft Refusal)
ENABLE_LLM_INTENT_CLASSIFIER = True  # Sử dụng mô hình ngôn ngữ để hiểu ngữ cảnh và chỉ dẫn pháp lý khi từ chối

EFFECTIVE_STATUS_VALID = "hieu_luc"
PARTIALLY_AMENDED_ARTICLES = {
    "17/2023/ND-CP": {
        "1", "5", "8", "22", "23", "25", "29", "38", "39", "40",
        "41", "43", "71", "84", "87", "88", "98", "99", "110",
    },
}

LEGAL_SYNONYMS = {
  "doi_tuong": {
    "phần mềm":            ["chương trình máy tính"],
    "ứng dụng":            ["chương trình máy tính"],
    "app":                 ["chương trình máy tính"],
    "software":            ["chương trình máy tính"],
    "source code":         ["mã nguồn", "chương trình máy tính"],
    "code":                ["mã nguồn"],
    "file chạy":           ["mã máy"],
    "database":            ["sưu tập dữ liệu"],
    "cơ sở dữ liệu":       ["sưu tập dữ liệu"],
    "bộ dữ liệu":          ["sưu tập dữ liệu"],
    "ngôn ngữ lập trình":  ["chương trình máy tính", "mã nguồn"]
  },
  "chu_the": {
    "bản quyền":           ["quyền tác giả"],
    "lập trình viên":      ["tác giả"],
    "dev":                 ["tác giả"],
    "người viết code":     ["tác giả"],
    "nhóm phát triển":     ["đồng tác giả"],
    "ai sở hữu":           ["chủ sở hữu quyền tác giả"],
    "ai là chủ":           ["chủ sở hữu quyền tác giả"],
    "ai có quyền":         ["chủ sở hữu quyền tác giả", "quyền tài sản"],
    "công ty":             ["tổ chức"],
    "doanh nghiệp":        ["tổ chức"]
  },
  "quan_he_hop_dong": {
    "thuê viết phần mềm":  ["giao kết hợp đồng với tác giả", "chủ sở hữu quyền tác giả"],
    "thuê ngoài":          ["giao kết hợp đồng", "giao nhiệm vụ"],
    "outsource":           ["giao kết hợp đồng", "giao nhiệm vụ"],
    "đặt hàng":            ["giao kết hợp đồng"],
    "gia công phần mềm":   ["giao kết hợp đồng", "chương trình máy tính"],
    "thuê mướn":           ["giao kết hợp đồng"],
    "nhân viên":           ["giao nhiệm vụ", "hợp đồng lao động"],
    "viết trong giờ làm":  ["giao nhiệm vụ"],
    "freelancer":          ["giao kết hợp đồng", "tác giả"],
    "không ghi trong hợp đồng": ["thỏa thuận"]
  },
  "chuyen_giao": {
    "mua đứt":             ["chuyển nhượng quyền tác giả"],
    "bán bản quyền":       ["chuyển nhượng quyền tác giả"],
    "bán source code":     ["chuyển nhượng quyền tác giả", "quyền tài sản"],
    "license":             ["hợp đồng sử dụng quyền tác giả"],
    "giấy phép sử dụng":   ["hợp đồng sử dụng quyền tác giả", "chuyển quyền sử dụng"],
    "cấp phép":            ["hợp đồng sử dụng quyền tác giả"],
    "cho phép dùng":       ["chuyển quyền sử dụng", "quyền tác giả"],
    "mã nguồn mở":         ["hợp đồng sử dụng quyền tác giả", "cấp phép"]
  },
  "khai_thac": {
    "backup":              ["bản sao dự phòng"],
    "bản backup":          ["bản sao dự phòng"],
    "sao lưu":             ["bản sao dự phòng", "sao chép"],
    "copy":                ["sao chép"],
    "cài nhiều máy":       ["sao chép", "quyền sử dụng hợp pháp bản sao"],
    "sửa code":            ["sửa chữa chương trình máy tính", "tác phẩm phái sinh"],
    "chỉnh sửa":           ["sửa chữa", "nâng cấp", "tác phẩm phái sinh"],
    "nâng cấp":            ["sửa chữa", "nâng cấp chương trình máy tính"],
    "vá lỗi":              ["sửa chữa chương trình máy tính"],
    "bảo trì":             ["sửa chữa", "nâng cấp"],
    "phát triển tiếp":     ["tác phẩm phái sinh", "nâng cấp"],
    "cho thuê phần mềm":   ["cho thuê bản sao chương trình máy tính"],
    "phát hành":           ["phân phối", "công bố"],
    "chạy trên cloud":     ["cung cấp dưới dạng dịch vụ", "nền trực tuyến"],
    "saas":                ["cung cấp dưới dạng dịch vụ", "nền tảng trực tuyến"]
  },
  "pham_vi_bao_ho": {
    "thuật toán":          ["ý tưởng", "quy trình", "phương pháp hoạt động", "không được bảo hộ"],
    "ý tưởng":             ["ý tưởng", "khái niệm", "nguyên lý", "đối tượng không được bảo hộ"],
    "giao diện":           ["tác phẩm", "bảo hộ quyền tác giả"],
    "ai đăng ký":          ["đăng ký quyền tác giả", "chủ sở hữu quyền tác giả"],
    "đăng ký bản quyền":   ["đăng ký quyền tác giả", "giấy chứng nhận đăng ký quyền tác giả"],
    "bảo hộ bao lâu":      ["thời hạn bảo hộ quyền tác giả"],
    "hết hạn bản quyền":   ["thời hạn bảo hộ quyền tác giả"]
  },
  "xam_pham": {
    "vi phạm bản quyền":   ["xâm phạm quyền tác giả"],
    "crack":               ["xâm phạm quyền tác giả", "vô hiệu hóa biện pháp công nghệ"],
    "bẻ khóa":             ["vô hiệu hóa biện pháp công nghệ", "xâm phạm quyền tác giả"],
    "phần mềm lậu":        ["xâm phạm quyền tác giả", "sao chép trái phép"],
    "copy code":           ["sao chép", "xâm phạm quyền tác giả"],
    "ăn cắp code":         ["xâm phạm quyền tác giả", "sao chép trái phép"],
    "đạo code":            ["xâm phạm quyền tác giả", "quyền nhân thân"],
    "kiện":                ["biện pháp bảo vệ quyền tác giả", "giải quyết tranh chấp"],
    "bồi thường":          ["bồi thường thiệt hại", "xâm phạm quyền tác giả"],
    "ghi tên":             ["đặt tên tác phẩm", "đứng tên tác giả", "quyền nhân thân"]
  }
}

# Cấu hình module giám sát và cào dữ liệu hiệu lực
VBPL_BASE_URL = "https://congbao.chinhphu.vn"
SOURCE_URL_EXACT = "https://congbao.chinhphu.vn/van-ban/van-ban-hop-nhat-so-67-vbhn-vpqh-469197.htm"
MONITORED_LAWS = [LAW_CODE]
CRAWL_FREQUENCY = "monthly"
CRAWL_DELAY_SECONDS = 3.0
CRAWLER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)
EXPIRY_WARNING_DAYS = 45

# Cấu hình kiểm soát tần suất truy vấn (Rate Limiting) cho giao diện người dùng
RATE_LIMIT_COOLDOWN_SECONDS = 3.0   # Khoảng nghỉ tối thiểu giữa 2 lần gửi câu hỏi liên tiếp
RATE_LIMIT_MAX_PER_MINUTE = 12      # Số câu hỏi tối đa được gửi trong vòng 1 phút

