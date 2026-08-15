"""
main.py — Điểm vào CLI kiểm thử hệ thống PoC RAG.

Quy trình xử lý:
    raw text -> chunker -> metadata -> embedder -> FAISS + BM25 -> retriever
    -> refusal_gate -> prompt_builder -> llm -> citation
"""
from __future__ import annotations

import numpy as np
import config
from ingestion.chunker import parse_law_text
from ingestion.metadata import attach_effective_metadata, load_law_meta
from retrieval.embedder import get_embedder
from retrieval.faiss_index import FaissFlatIndex
from retrieval.bm25_index import Bm25Index
from retrieval.retriever import retrieve
from generation.refusal_gate import decide
from generation.prompt_builder import build_prompt
from generation.llm import generate
from generation.citation import build_citations


SOURCE_URL = (
    "https://congbao.chinhphu.vn/van-ban/van-ban-hop-nhat-so-67-vbhn-vpqh-469197.htm"
)

SAMPLE_QUESTIONS = [
    # Nhóm 1: Trực tiếp trong phạm vi
    {
        "group": 1,
        "group_name": "Nhóm 1: Trong phạm vi, trực tiếp",
        "question": "Quyền tác giả đối với chương trình máy tính bao gồm những quyền nhân thân và quyền tài sản nào?"
    },
    # Nhóm 2: Tình huống thực tế
    {
        "group": 2,
        "group_name": "Nhóm 2: Trong phạm vi, tình huống thực tế",
        "question": "Công ty A thuê lập trình viên B viết phần mềm quản lý bán hàng nhưng hợp đồng không có thỏa thuận về quyền sở hữu. Vậy ai là chủ sở hữu quyền tác giả đối với phần mềm này?"
    },
    # Nhóm 3: Tra cứu điều khoản cụ thể
    {
        "group": 3,
        "group_name": "Nhóm 3: Tra cứu điều khoản cụ thể",
        "question": "Theo Điều 22 Luật Sở hữu trí tuệ, việc tạo bản sao dự phòng chương trình máy tính được quy định như thế nào?"
    },
    # Nhóm 4: Ngoài phạm vi gần chủ đề (Distractor)
    {
        "group": 4,
        "group_name": "Nhóm 4: Ngoài phạm vi nhưng gần chủ đề (Distractor)",
        "question": "Chương trình máy tính có được bảo hộ dưới danh nghĩa sáng chế theo Điều 59 Luật Sở hữu trí tuệ không?"
    },
    # Nhóm 5: Hoàn toàn ngoài phạm vi (Buộc từ chối)
    {
        "group": 5,
        "group_name": "Nhóm 5: Buộc từ chối vì ngoài phạm vi / thiếu căn cứ",
        "question": "Mức xử phạt vi phạm hành chính đối với hành vi điều khiển xe máy vượt đèn đỏ theo Luật Giao thông đường bộ là bao nhiêu?"
    },
]


def build_corpus() -> list:
    """Nạp dữ liệu thô từ VBHN 67/VBHN-VPQH, tách chunks và gán metadata."""
    import json

    raw_path = config.DATA_RAW_DIR / "67-VBHN-VPQH.txt"
    text = raw_path.read_text(encoding="utf-8")
    provisions = parse_law_text(text, law_code=config.LAW_CODE, source_url=SOURCE_URL)
    law_meta = load_law_meta(raw_path)
    provisions = attach_effective_metadata(provisions, law_meta)

    # Ghi tự động danh sách chunks mới ra data/processed/chunks.jsonl
    with config.CHUNKS_PATH.open("w", encoding="utf-8") as f:
        for p in provisions:
            f.write(json.dumps(p.to_dict(), ensure_ascii=False) + "\n")

    return provisions


def index_corpus(provisions: list):
    """Xây dựng chỉ mục FAISS và BM25 cho tập dữ liệu, điền vector_id & embedding_model, và đồng bộ chunks.jsonl."""
    import json

    embedder = get_embedder()
    texts = [p.text for p in provisions]
    vectors = embedder.encode(texts)
    dim = vectors.shape[1]

    # Điền vector_id và embedding_model cho từng Provision
    model_name = getattr(embedder, "model_name", config.EMBEDDING_MODEL_NAME)
    for idx, p in enumerate(provisions):
        p.vector_id = idx
        p.embedding_model = model_name

    # Cập nhật thông tin vector vào file chunks.jsonl
    with config.CHUNKS_PATH.open("w", encoding="utf-8") as f:
        for p in provisions:
            f.write(json.dumps(p.to_dict(), ensure_ascii=False) + "\n")

    faiss_index = FaissFlatIndex(dim)
    faiss_index.add(np.asarray(vectors), [p.provision_id for p in provisions])
    faiss_index.save(config.FAISS_INDEX_PATH)

    bm25 = Bm25Index(texts, [p.provision_id for p in provisions])
    return embedder, faiss_index, bm25


def answer_question(item: dict, provisions, embedder, faiss_index) -> None:
    """Thực thi pipeline tìm kiếm, đánh giá từ chối và sinh câu trả lời cho một câu hỏi."""
    query = item["question"]
    g_name = item["group_name"]
    print("=" * 78)
    print(f"[{g_name}]")
    print(f"CÂU HỎI: {query}")

    hits = retrieve(query, provisions, embedder, faiss_index, top_k=config.TOP_K)
    print(f"-> Retrieval trả về {len(hits)} kết quả còn hiệu lực (top_k={config.TOP_K}):")
    for h in hits:
        flag = " [DISTRACTOR]" if h.provision.is_distractor else ""
        print(f"   score={h.score:.4f}  Điều {h.provision.article_no}{flag}  {h.provision.title}")

    decision = decide(query, hits)
    print(f"-> Refusal gate: should_refuse={decision.should_refuse} | lý do: {decision.reason}")

    if decision.should_refuse:
        print(">> TỪ CHỐI TRẢ LỜI (Kích hoạt Refusal Gate).")
        return

    prompt = build_prompt(query, hits)
    answer = generate(query, prompt, hits)
    citations = build_citations(hits)

    print(">> CÂU TRẢ LỜI:")
    print(answer)
    print(">> TRÍCH DẪN PHÁP LÝ (Metadata):")
    for c in citations:
        print(f"   - Điều {c['article_no']} ({c['law_code']}), status={c['status']}")


def main() -> None:
    from retrieval.retriever import evaluate_retriever_recall

    print("--- [1/3] Xây dựng corpus từ VBHN 67/VBHN-VPQH ---")
    provisions = build_corpus()
    n_in_scope = sum(1 for p in provisions if not p.is_distractor)
    n_distractor = sum(1 for p in provisions if p.is_distractor)
    print(f"Tổng số chunks: {len(provisions)} ({n_in_scope} trong phạm vi, {n_distractor} distractor).\n")

    print("--- [2/3] Khởi tạo Embedder & Cấu trúc chỉ mục ---")
    embedder, faiss_index, bm25 = index_corpus(provisions)
    print(f"Mô hình Embedding: {getattr(embedder, 'model_name', 'unknown')}")
    print(f"Chỉ mục FAISS: {len(faiss_index)} vectors (đã lưu tại {config.FAISS_INDEX_PATH}).")
    print(f"Đã cập nhật vector_id và embedding_model vào {config.CHUNKS_PATH}.\n")

    # Đánh giá sơ bộ Recall@k
    sample_eval = [
        {
            "question": "Quyền tác giả đối với chương trình máy tính bao gồm những quyền nhân thân và quyền tài sản nào?",
            "gold_provision_ids": ["67-VBHN-VPQH_Art22_Kh1"],
        },
        {
            "question": "Theo Điều 22 Luật Sở hữu trí tuệ, việc tạo bản sao dự phòng chương trình máy tính được quy định như thế nào?",
            "gold_provision_ids": ["67-VBHN-VPQH_Art22_Kh1"],
        },
    ]
    recalls = evaluate_retriever_recall(
        sample_eval, provisions, embedder, faiss_index,
        k=config.TOP_K,
        bm25_index=bm25,
        mode="both",
    )
    print(f"-> Recall@{config.TOP_K} (FAISS Dense):  {recalls['faiss'] * 100:.1f}%")
    print(f"-> Recall@{config.TOP_K} (BM25 Sparse):  {recalls['bm25'] * 100:.1f}%  ← baseline\n")

    print("--- [3/3] Chạy thử nghiệm các nhóm câu hỏi mẫu ---")
    for item in SAMPLE_QUESTIONS:
        answer_question(item, provisions, embedder, faiss_index)
    print("=" * 78)


if __name__ == "__main__":
    main()
