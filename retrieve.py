"""
retrieve.py —— Day 3：检索

它做两件事：
  1. 把 index/chunks.json 里的块建成"关键词检索索引"（BM25）
  2. 给一个问题，返回最相关的 5 个块（带文件名和页码）

用法：
  python retrieve.py "2025年营业收入是多少"
"""

import json
import sys
from pathlib import Path

import jieba
from rank_bm25 import BM25Okapi

# 关掉 jieba 启动时那行多余的提示
jieba.setLogLevel(20)

# 路径：都基于本脚本所在文件夹
BASE_DIR = Path(__file__).parent
INDEX_FILE = BASE_DIR / "index" / "chunks.json"


# ============================================================
# 第 1 步：加载数据
# ============================================================
def load_chunks():
    """读取 chunks.json，返回所有块的列表"""
    if not INDEX_FILE.exists():
        raise FileNotFoundError(
            f"找不到索引文件：{INDEX_FILE}\n请先运行 python ingest.py"
        )
    with open(INDEX_FILE, encoding="utf-8") as f:
        return json.load(f)


# ============================================================
# 第 2 步：分词
# ============================================================
def tokenize(text):
    """把一段中文切成词。

    为什么要分词？
        BM25 是按"词"匹配的，不是按整句。
        例如："2025年营业收入是多少"
        → 切成 ["2025", "年", "营业收入", "是", "多少"]
    """
    return list(jieba.cut(text))


# ============================================================
# 第 3 步：建立索引
# ============================================================
def build_index(chunks):
    """把每个块都切词，交给 BM25 建立索引

    这一步就是"提前把 1096 个块整理好"，
    以后每次提问就不需要重新读文件了。
    """
    tokenized_chunks = [tokenize(c["text"]) for c in chunks]
    return BM25Okapi(tokenized_chunks)


# ============================================================
# 第 4 步：检索（核心函数）
# ============================================================
def search(query, chunks, bm25, top_k=5):
    """给一个问题，返回最相关的 top_k 个块

    流程：
        问题 → 分词 → BM25 打分 → 排序 → 取前 top_k 个
    """
    # 1) 问题也要分词
    query_tokens = tokenize(query)

    # 2) 给 1096 个块逐个打分（分数越高越相关）
    scores = bm25.get_scores(query_tokens)

    # 3) 按分数从高到低排序，取前 top_k 个
    ranked_indexes = sorted(
        range(len(scores)), key=lambda i: scores[i], reverse=True
    )[:top_k]

    # 4) 组装结果（保留 chunk_id / file / page / text）
    results = []
    for i in ranked_indexes:
        c = chunks[i]
        results.append({
            "chunk_id": c["chunk_id"],
            "file": c["file"],
            "page": c["page"],
            "text": c["text"],
            "score": float(scores[i]),
        })
    return results


# ============================================================
# 第 5 步：命令行测试
# ============================================================
def main():
    if len(sys.argv) < 2:
        print('用法: python retrieve.py "你的问题"')
        return

    query = sys.argv[1]

    print("正在加载索引...")
    chunks = load_chunks()          # 读文件
    bm25 = build_index(chunks)      # 建索引
    print(f"共 {len(chunks)} 个块\n")

    results = search(query, chunks, bm25, top_k=5)

    print(f"问题: {query}")
    print(f"\n找到 {len(results)} 个相关块：\n")
    for n, r in enumerate(results, 1):
        preview = r["text"][:100].replace("\n", " ")   # 前 100 字，去掉换行
        print(f'[{n}] {r["file"]}  第 {r["page"]} 页  得分 {r["score"]:.2f}')
        print(f'    "{preview}..."')
        print()


if __name__ == "__main__":
    main()
