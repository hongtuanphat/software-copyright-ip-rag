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

# Đường dẫn file dữ liệu thô và file metadata hiệu lực văn bản
RAW_LAW_FILE = DATA_RAW_DIR / "67-VBHN-VPQH.txt"
METADATA_FILE = DATA_RAW_DIR / "vbhn_metadata.json"

# Đường dẫn các file đầu ra đã qua xử lý (chunks, testset, vector index, alerts)
CHUNKS_PATH = DATA_PROCESSED_DIR / "chunks.jsonl"
TESTSET_PATH = DATA_PROCESSED_DIR / "testset.jsonl"
ALERTS_PATH = DATA_PROCESSED_DIR / "alerts.jsonl"
FAISS_INDEX_PATH = DATA_PROCESSED_DIR / "faiss.index"


# Cấu hình mô hình nhúng văn bản và mô hình ngôn ngữ lớn
EMBEDDING_MODEL_NAME = "bkai-foundation-models/vietnamese-bi-encoder"
LLM_PROVIDER = "gemini"
GEMINI_MODEL_NAME = "gemini-3.5-flash-lite"
GEMINI_TEMPERATURE = 0.0  # Để 0 để mô hình trả lời ổn định, bám sát từng điều luật
GEMINI_MAX_TOKENS = 4096

# Phân loại chủ đề trong phạm vi và chủ đề gây nhiễu (distractor)
IN_SCOPE_TOPICS = {"quyen_tac_gia_ctmt"}
DISTRACTOR_TOPICS = {
    "sang_che",
    "kieu_dang_cong_nghiep",
    "nhan_hieu",
    "quyen_lien_quan",    # Quyền liên quan (người biểu diễn, bản ghi âm...)
    "bi_mat_kinh_doanh", # Bí mật kinh doanh
    "distractor_khac",
}
LAW_CODE = "67/VBHN-VPQH"

# Tham số truy hồi văn bản
TOP_K = 5
MAX_SEQ_LENGTH = 256
EMBEDDING_DIM = 768
RETRIEVAL_MODE = "hybrid"      # Chế độ truy hồi mặc định: "hybrid", "dense", hoặc "bm25"
RRF_K = 20                     # Hằng số chuẩn cho thuật toán Reciprocal Rank Fusion (tối ưu độ dốc điểm cho top đầu)
CANDIDATE_POOL_SIZE = 50       # Số lượng ứng viên lấy từ mỗi nhánh trước khi hợp nhất RRF

# Ngưỡng lọc và cổng từ chối (Refusal Gate)
MIN_SCORE_TIN_CAY = 0.22      # Điểm tương đồng ngữ nghĩa tối thiểu (Cosine Similarity) để xem kết quả là đáng tin
MAX_DISTRACTOR_RATIO = 0.6    # Tỷ lệ tối đa các đoạn distractor trong top-k
EFFECTIVE_STATUS_VALID = "hieu_luc"
REFUSAL_THRESHOLD = 0.6

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

# Cấu hình bộ dữ liệu kiểm thử
TESTSET_SIZE = 100
TESTSET_GROUPS = {
    1: "trong pham vi, truc tiep",
    2: "trong pham vi, tinh huong thuc te",
    3: "tra cuu dieu khoan",
    4: "ngoai pham vi nhung gan chu de",
    5: "buoc phai tu choi vi thieu can cu",
}
