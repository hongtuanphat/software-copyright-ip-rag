"""
config.py — Cấu hình hằng số hệ thống RAG.
"""

from pathlib import Path

# Đường dẫn dữ liệu & chỉ mục
PROJECT_ROOT = Path(__file__).resolve().parent
DATA_RAW_DIR = PROJECT_ROOT / "data" / "raw"
DATA_PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
CHUNKS_PATH = DATA_PROCESSED_DIR / "chunks.jsonl"
TESTSET_PATH = DATA_PROCESSED_DIR / "testset.jsonl"
ALERTS_PATH = DATA_PROCESSED_DIR / "alerts.jsonl"
FAISS_INDEX_PATH = DATA_PROCESSED_DIR / "faiss.index"

# Mô hình & Dịch vụ AI
EMBEDDING_MODEL_NAME = "bkai-foundation-models/vietnamese-bi-encoder"
LLM_PROVIDER = "gemini"
GEMINI_MODEL_NAME = "gemini-3.6-flash"

# Chủ đề & Văn bản áp dụng
IN_SCOPE_TOPICS = {"quyen_tac_gia_ctmt"}
DISTRACTOR_TOPICS = {
    "sang_che",
    "kieu_dang_cong_nghiep",
    "nhan_hieu",
    "quyen_lien_quan",    # Quyền liên quan (người biểu diễn, bản ghi âm, chương trình phát sóng)
    "bi_mat_kinh_doanh", # Bí mật kinh doanh
    "distractor_khac",
}
LAW_CODE = "67/VBHN-VPQH"

# Cấu hình Retrieval
TOP_K = 5

# Cấu hình Refusal Gate
MIN_SCORE_TIN_CAY = 0.35      # Ngưỡng điểm tương đồng tối thiểu để tin tưởng kết quả
MAX_DISTRACTOR_RATIO = 0.6    # Tỷ lệ distractor tối đa trong top-k 

# Cấu hình Monitoring & Giám sát hiệu lực
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

# Cấu hình Bộ dữ liệu kiểm thử (Testset)
TESTSET_SIZE = 100
TESTSET_GROUPS = {
    1: "trong pham vi, truc tiep",
    2: "trong pham vi, tinh huong thuc te",
    3: "tra cuu dieu khoan",
    4: "ngoai pham vi nhung gan chu de",
    5: "buoc phai tu choi vi thieu can cu",
}
