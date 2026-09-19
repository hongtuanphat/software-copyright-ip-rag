"""evaluation/scripts/run_all.py

Chạy tự động và tuần tự 3 hệ thống (Gemini trần, BM25+Gemini, System RAG).
Sau khi chạy xong sẽ tự động gọi run_refusal_metrics để tính TRR/FAR/FRR
dựa trên trường actual_behavior đã có sẵn trong từng file JSONL kết quả.
"""
import argparse
import datetime
import os
import sys
import subprocess
from pathlib import Path

# Đảm bảo chạy từ thư mục gốc
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from evaluation.core.runner import setup_encoding
setup_encoding()

def main():
    parser = argparse.ArgumentParser(description="Chạy tự động toàn bộ evaluation pipeline.")
    parser.add_argument("--limit", type=int, default=None, help="Chạy thử trên tập nhỏ")
    args = parser.parse_args()

    time_str = datetime.datetime.now().strftime("%d_%m_%Y_%H_%M_%S")
    out_dir = PROJECT_ROOT / "evaluation" / "results" / time_str
    out_dir.mkdir(parents=True, exist_ok=True)
    
    scripts = [
        ("Gemini Baseline", "run_gemini.py", "gemini.jsonl"),
        ("BM25 + Gemini", "run_BM25.py", "bm25.jsonl"),
        ("System RAG", "run_RAG.py", "rag.jsonl")
    ]
    
    for name, script, out_name in scripts:
        print(f"\n=======================================================")
        print(f"BẮT ĐẦU CHẠY: {name}")
        print(f"=======================================================\n")
        
        # Gọi subprocess theo chuẩn module (-m) thay vì đường dẫn file, tự động nhận diện root module
        module_name = f"evaluation.scripts.{script[:-3]}"
        cmd = [sys.executable, "-m", module_name, "--output", str(out_dir / out_name)]
        if args.limit:
            cmd.extend(["--limit", str(args.limit)])
            
        try:
            subprocess.run(cmd, check=True, cwd=PROJECT_ROOT)
        except subprocess.CalledProcessError as e:
            print(f"Lỗi khi chạy {script}: {e}")
            sys.exit(1)
        
    print(f"\n=======================================================")
    print(f"CHẤM ĐIỂM TRR/FAR/FRR")
    print(f"=======================================================\n")
    cmd_eval = [sys.executable, "-m", "evaluation.scripts.run_refusal_metrics", "--date", time_str]
    try:
        subprocess.run(cmd_eval, check=True, cwd=PROJECT_ROOT)
    except subprocess.CalledProcessError as e:
        print(f"Lỗi khi chạy run_refusal_metrics.py: {e}")
        
    print("\n[THÀNH CÔNG] Pipeline Evaluation đã hoàn tất!")

if __name__ == "__main__":
    main()
