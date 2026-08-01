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
GEMINI_MODEL_NAME = "gemini-2.0-flash"

# Chủ đề & Văn bản áp dụng
IN_SCOPE_TOPICS = {"quyen_tac_gia_ctmt"}
DISTRACTOR_TOPICS = {"sang_che", "kieu_dang_cong_nghiep", "nhan_hieu"}
LAW_CODE = "67/VBHN-VPQH"

# Cấu hình Retrieval
TOP_K = 5

# Cấu hình Monitoring & Giám sát hiệu lực
VBPL_BASE_URL = "https://congbao.chinhphu.vn"
SOURCE_URL_EXACT = "https://congbao.chinhphu.vn/van-ban/van-ban-hop-nhat-so-67-vbhn-vpqh-469197.htm"
MONITORED_LAWS = [LAW_CODE]
CRAWL_FREQUENCY = "monthly"
CRAWL_DELAY_SECONDS = 3.0
CRAWLER_USER_AGENT = (
    "TTTN-LegalRAG-Bot/0.1 "
    "(do an thuc tap tot nghiep, phi thuong mai; "
    "lien he: phatht5648@ut.edu.vn)"
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
