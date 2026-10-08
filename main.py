"""
main.py — Điểm vào CLI kiểm thử hệ thống RAG Đa Văn Bản (Luật SHTT 67 + NĐ 17/2023 + NĐ 134/2026).

Quy trình xử lý:
    raw texts (Luật + Nghị định) -> chunker -> metadata -> embedder -> FAISS + BM25
    -> retrieve_hybrid (RRF) -> refusal_gate -> prompt_builder -> llm -> citation
"""
from __future__ import annotations

import sys
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import argparse
import json
from pathlib import Path
import numpy as np

import config
from ingestion.chunker import parse_law_text, Provision, save_provisions
from ingestion.metadata import attach_effective_metadata, load_law_meta
from ingestion.utils import build_index_text
from retrieval.embedder import get_embedder
from retrieval.faiss_index import FaissFlatIndex
from retrieval.bm25_index import Bm25Index
from retrieval.retriever import retrieve_hybrid
from generation.refusal_gate import decide
from generation.prompt_builder import build_prompt
from generation.llm import generate
from monitoring.effective_checker import get_active_alerts


AMENDED_ARTICLES_IN_ND17 = config.PARTIALLY_AMENDED_ARTICLES["17/2023/ND-CP"]

# 5 Câu hỏi đại diện cho 5 Nhóm kiểm thử
SAMPLE_QUESTIONS = [
    # Nhóm 1: Trong phạm vi, hỏi trực tiếp
    {
        "group": 1,
        "group_name": "Nhóm 1: Trong phạm vi, trực tiếp",
        "question": "Quyền tác giả đối với chương trình máy tính bao gồm những quyền nhân thân và quyền tài sản nào?",
    },
    # Nhóm 2: Tình huống thực tế (Hợp đồng gia công, bản sao lưu)
    {
        "group": 2,
        "group_name": "Nhóm 2: Tình huống thực tế (thuê ngoài phần mềm)",
        "question": "Công ty A thuê công ty B phát triển phần mềm kế toán theo hợp đồng dịch vụ mà không có điều khoản chuyển nhượng quyền tác giả. Công ty A có quyền sao chép dự phòng và sửa đổi phần mềm không?",
    },
    # Nhóm 3: Tra cứu điều khoản
    {
        "group": 3,
        "group_name": "Nhóm 3: Tra cứu điều khoản",
        "question": "Điều 22 Luật Sở hữu trí tuệ quy định về quyền tác giả đối với chương trình máy tính như thế nào?",
    },
    # Nhóm 4: Gần chủ đề nhưng ngoài phạm vi (Soft refusal)
    {
        "group": 4,
        "group_name": "Nhóm 4: Ngoài phạm vi nhưng gần chủ đề (Soft refusal)",
        "question": "Chương trình máy tính có được bảo hộ dưới danh nghĩa sáng chế theo Điều 59 Luật Sở hữu trí tuệ không?",
    },
    # Nhóm 5: Hoàn toàn ngoài phạm vi (Buộc từ chối)
    {
        "group": 5,
        "group_name": "Nhóm 5: Buộc từ chối vì ngoài phạm vi / thiếu căn cứ",
        "question": "Mức xử phạt vi phạm hành chính đối với hành vi điều khiển xe máy vượt đèn đỏ theo Luật Giao thông đường bộ là bao nhiêu?",
    },
]


def build_corpus(force: bool = False) -> list[Provision]:
    """Nạp dữ liệu thô từ toàn bộ các văn bản luật và nghị định, tách chunks và gán metadata.

    Nếu force=False và file chunks.jsonl đã tồn tại đầy đủ thì nạp từ cache.
    """
    if not force and config.CHUNKS_PATH.exists():
        cached: list[Provision] = []
        with config.CHUNKS_PATH.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    cached.append(Provision(**json.loads(line)))
        if len(cached) >= 1000:
            return cached

    raw_dir = config.DATA_RAW_DIR
    all_provisions: list[Provision] = []

    docs_config = [
        ("67-VBHN-VPQH.txt", "67/VBHN-VPQH", "https://congbao.chinhphu.vn/van-ban/van-ban-hop-nhat-so-67-vbhn-vpqh-469197.htm"),
        ("17-2023-ND-CP.txt", "17/2023/ND-CP", "https://congbao.chinhphu.vn/van-ban/nghi-dinh-so-17-2023-nd-cp-39279.htm"),
        ("134-2026-ND-CP.txt", "134/2026/ND-CP", "https://congbao.chinhphu.vn/van-ban/nghi-dinh-so-134-2026-nd-cp-469388/64378.htm")
    ]

    for filename, law_code, source_url in docs_config:
        raw_path = raw_dir / filename
        if not raw_path.exists():
            continue
        text = raw_path.read_text(encoding="utf-8")
        provisions = parse_law_text(text, law_code=law_code, source_url=source_url)
        law_meta = load_law_meta(raw_path)
        provisions = attach_effective_metadata(provisions, law_meta)

        # Xử lý trạng thái bị sửa đổi đối với Nghị định 17
        if law_code == "17/2023/ND-CP":
            for p in provisions:
                if p.article_no in AMENDED_ARTICLES_IN_ND17:
                    p.status = "bi_sua_doi"
                    p.replaced_by = "134/2026/ND-CP"
                    p.effective_to = "2026-04-09"
                else:
                    p.status = "hieu_luc"

        all_provisions.extend(provisions)

    # Ghi tự động danh sách chunks mới ra data/processed/chunks.jsonl
    save_provisions(all_provisions, config.CHUNKS_PATH)

    return all_provisions


def index_corpus(provisions: list[Provision], output_index_path: Path | None = None, output_chunks_path: Path | None = None):
    """Xây dựng chỉ mục FAISS và BM25 cho tập dữ liệu hợp nhất."""
    embedder = get_embedder()
    texts = [build_index_text(p) for p in provisions]
    vectors = embedder.encode(texts)
    dim = vectors.shape[1]

    target_chunks = output_chunks_path or config.CHUNKS_PATH
    target_index = output_index_path or config.FAISS_INDEX_PATH

    # Điền vector_id và embedding_model cho từng Provision
    model_name = getattr(embedder, "model_name", config.EMBEDDING_MODEL_NAME)
    for idx, p in enumerate(provisions):
        p.vector_id = idx
        p.embedding_model = model_name

    # Cập nhật thông tin vector vào file chunks.jsonl
    save_provisions(provisions, target_chunks)

    faiss_index = FaissFlatIndex(dim)
    faiss_index.add(np.asarray(vectors), [p.provision_id for p in provisions])
    faiss_index.save(target_index, model_name=model_name)

    bm25 = Bm25Index(texts, [p.provision_id for p in provisions])
    return embedder, faiss_index, bm25


def answer_question(item: dict, pipeline) -> None:
    """Thực thi pipeline Hybrid Search, đánh giá từ chối và sinh câu trả lời."""
    query = item["question"]
    g_name = item["group_name"]
    print("=" * 78)
    print(f"[{g_name}]")
    print(f"CÂU HỎI: {query}")

    res = pipeline.query(query, top_k=config.TOP_K)
    
    print(f"-> Hybrid Retrieval trả về {len(res.retrieval_hits)} kết quả (top_k={config.TOP_K}):")
    for h in res.retrieval_hits:
        flag = " [DISTRACTOR]" if h.get("is_distractor") else ""
        clause_tag = f" Khoản {h.get('clause_no')}" if h.get("clause_no") else ""
        law_tag = f" ({h.get('law_code')})" if h.get("law_code") else ""
        print(f"   score={h.get('score', 0):.4f}  Điều {h.get('article_no')}{clause_tag}{law_tag}{flag}  {h.get('title')}")

    print(f"-> Refusal gate: should_refuse={res.should_refuse} | lý do: {res.refusal_reason}")
    print(f"-> LLM thô (decision): {getattr(res, 'llm_decision', 'N/A')}")
    print(f"-> LLM thô (used_documents): {getattr(res, 'used_documents', [])}")

    if res.should_refuse:
        print(">> TỪ CHỐI TRẢ LỜI (Kích hoạt Refusal Gate hoặc LLM Dynamic Refusal).")
        print(f">> Lý do: {res.refusal_reason}")
        print()
        return

    print("-> Phản hồi từ mô hình:")
    print(res.answer)
    print()

    print(f"-> Căn cứ pháp lý trích dẫn ({len(res.cited_documents)} điều khoản):")
    for doc in res.cited_documents:
        c_clause = doc.get('clause_no')
        c_tag = f" Khoản {c_clause}" if c_clause else ""
        law_name = doc.get('law_name') or doc.get('law_code') or ""
        law_tag = f" ({law_name})" if law_name else ""
        print(f"   - Điều {doc.get('article_no')}{c_tag}{law_tag}: {doc.get('title')}")
    print()


def main():
    parser = argparse.ArgumentParser(description="Chạy kiểm thử hệ thống RAG Đa Văn Bản.")
    parser.add_argument("--force", action="store_true", help="Làm tươi và tái tạo toàn bộ CSDL và Vector Index.")
    args = parser.parse_args()

    print("=" * 78)
    print("HỆ THỐNG RAG ĐA VĂN BẢN VỀ BẢN QUYỀN PHẦN MỀM & AI (Luật 67 + NĐ 17 + NĐ 134)")
    print("=" * 78)

    print("\n[Bước 1] Nạp dữ liệu và kiểm tra CSDL...")
    provisions = build_corpus(force=args.force)
    print(f"-> Đã nạp thành công {len(provisions)} đoạn luật (Provision) từ 3 văn bản.")

    print("\n[Bước 2] Xây dựng hoặc tải Chỉ mục Vector (FAISS IndexFlatIP Cosine Similarity + BM25)...")
    if args.force or not config.FAISS_INDEX_PATH.exists():
        print("-> Đang thực hiện làm tươi và tính toán vector nhúng...")
        embedder, faiss_index, bm25_index = index_corpus(provisions)
        print(f"-> Đã lưu chỉ mục vector FAISS ({len(faiss_index)} vectors) và BM25.")
    else:
        print("-> Bỏ qua tính toán vector. Chỉ mục sẽ được nạp thông qua RAGPipeline.")

    from pipeline import get_pipeline
    pipeline = get_pipeline(mode="hybrid")

    print("\n[Bước 3] Chạy thử nghiệm 5 câu hỏi kiểm thử đại diện...")
    for item in SAMPLE_QUESTIONS:
        answer_question(item, pipeline)

    print("=" * 78)
    print("HOÀN THÀNH KIỂM THỬ HỆ THỐNG.")
    print("=" * 78)


if __name__ == "__main__":
    main()
