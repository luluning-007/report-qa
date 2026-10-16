"""
ingest.py —— Day 2：把 PDF 变成可检索的小块

它做三件事：
  1. 读 data/ 文件夹里的所有 PDF
  2. 逐页提取文字
  3. 把文字切成小块，存到 index/chunks.json

用法：
  python ingest.py
"""

import json
from collections import Counter
from pathlib import Path

import pdfplumber

# ============================================================
# 可调参数（这两个数字很重要，Day 4 讲"为什么这么切"时会用到）
# ============================================================
CHUNK_SIZE = 500    # 每块最多多少字
CHUNK_OVERLAP = 50    # 相邻两块重叠多少字（防止一句话被劈开）

# ============================================================
# 路径设置：都基于本脚本所在的文件夹，所以你在哪里运行都不会找错
# ============================================================
BASE_DIR = Path(__file__).parent        # report-qa 文件夹
DATA_DIR = BASE_DIR / "data"            # 年报 PDF 放这里
INDEX_DIR = BASE_DIR / "index"          # 结果存这里
OUTPUT_FILE = INDEX_DIR / "chunks.json"


def extract_pages(pdf_path):
    """读一个 PDF，返回 [(页码, 该页文字), ...]

    页码从 1 开始（符合人的习惯，PDF 阅读器也这么显示）。
    提取不出文字的页（比如扫描图片页）会被跳过。
    """
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            text = text.strip()
            if text:                                   # 跳过空白页
                pages.append((i + 1, text))
    return pages


def split_into_chunks(text, size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """把一段长文字切成若干块。

    为什么要"重叠"？
        如果一句话正好落在两个块的边界上，两块就都不完整。
        让相邻两块重叠一段，能保证这句话至少完整地出现在某一块里。

    举例（size=10, overlap=3）：
        原文: ABCDEFGHIJKLMNOP
        块1:  ABCDEFGHIJ
        块2:  HIJKLMNOP     ← 从第 8 个字符开始（10-3+1），和块1 重叠了 HIJ
    """
    if len(text) <= size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + size
        chunks.append(text[start:end])
        if end >= len(text):
            break
        start = end - overlap        # 往后退 overlap 个字，形成重叠
    return chunks


def main():
    INDEX_DIR.mkdir(exist_ok=True)

    # ---------- 1. 找出所有 PDF ----------
    pdf_files = sorted(DATA_DIR.glob("*.pdf"))
    if not pdf_files:
        print(f"[X] 没找到 PDF。请把年报放进: {DATA_DIR}")
        return

    print(f"找到 {len(pdf_files)} 个 PDF 文件\n")

    # ---------- 2. 逐个处理 ----------
    all_chunks = []
    chunk_id = 0

    for pdf_path in pdf_files:
        print(f"[文件] {pdf_path.name}")
        pages = extract_pages(pdf_path)
        print(f"       提取到 {len(pages)} 页有文字")

        for page_no, page_text in pages:
            for piece in split_into_chunks(page_text):
                all_chunks.append({
                    "chunk_id": chunk_id,   # 唯一编号，方便追踪
                    "file": pdf_path.name,  # 来自哪个文件
                    "page": page_no,        # 第几页  <-- 这个字段是"引用溯源"的关键
                    "text": piece,          # 文字内容
                })
                chunk_id += 1

    # ---------- 3. 保存 ----------
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_chunks, f, ensure_ascii=False, indent=1)

    print(f"\n[OK] 完成！共生成了 {len(all_chunks)} 个块")
    print(f"     保存到: {OUTPUT_FILE}")

    # ---------- 4. 统计打印（方便你检查结果）----------
    print("\n统计：")
    counter = Counter(ch["file"] for ch in all_chunks)
    for name, n in counter.items():
        print(f"  {name}: {n} 块")


if __name__ == "__main__":
    main()
