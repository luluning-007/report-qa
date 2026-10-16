"""
evaluate.py —— Day 6：批量评测

它做四件事：
  1. 读取 testsets/eval_20.json（20 道评测题）
  2. 逐题调用你的系统（检索 + AI 生成）
  3. 按【提前定好的规则】判断通过 / 失败
  4. 统计通过率，列出失败清单，保存详细结果

用法：
    python evaluate.py
"""

import json
import os
import time
from pathlib import Path

from answer import answer_question
from retrieve import build_index, load_chunks

# ============================================================
# 路径
# ============================================================
BASE_DIR = Path(__file__).parent
TESTSET_FILE = BASE_DIR / "testsets" / "eval_20.json"
RESULT_FILE = BASE_DIR / "index" / "eval_result.json"


# ============================================================
# ⭐ 核心：判断规则（必须提前定死，不能跑完再改）
# ============================================================
def judge(result, item):
    """判断一道题是否通过

    规则：
      - must_reject=True（应拒答题）：can_answer 必须是 False
      - must_reject=False（正常题）：can_answer 必须是 True，且 supporting 非空

    返回：(是否通过, 原因说明)
    """
    can_answer = result.get("can_answer")

    if item["must_reject"]:
        # ---------- 应该拒答的题 ----------
        if can_answer is False:
            return True, "正确拒答"
        else:
            return False, "❌ 该拒答却回答了（可能编造）"

    else:
        # ---------- 应该回答的题 ----------
        supporting = result.get("supporting", [])
        if can_answer is True and len(supporting) > 0:
            return True, "有答案且有支撑因素"
        elif can_answer is not True:
            return False, "❌ 该回答却拒答了（漏答）"
        else:
            return False, "❌ 有答案但没有支撑因素"


def main():
    # ---------- 0. 检查环境变量 ----------
    if not os.environ.get("DEEPSEEK_API_KEY"):
        print("[X] 没读到 DEEPSEEK_API_KEY 环境变量")
        return

    # ---------- 1. 读取评测题 ----------
    if not TESTSET_FILE.exists():
        print(f"[X] 找不到评测题文件：{TESTSET_FILE}")
        return

    with open(TESTSET_FILE, encoding="utf-8") as f:
        testset = json.load(f)

    # ---------- 2. 加载索引（只加载一次）----------
    print("正在加载索引...")
    chunks = load_chunks()
    bm25 = build_index(chunks)
    print(f"共 {len(chunks)} 个块")
    print(f"共 {len(testset)} 道评测题")
    print("=" * 72)

    # ---------- 3. 逐题评测 ----------
    results = []
    passed_count = 0

    for item in testset:
        qid = item["id"]
        qtype = item["type"]
        question = item["question"]

        print(f"\n[{qid}/{len(testset)}] ({qtype}类) {question}")

        try:
            result = answer_question(question, chunks, bm25, top_k=5)
            passed, reason = judge(result, item)
        except Exception as e:
            result = {"answer": f"调用异常: {e}", "can_answer": None}
            passed, reason = False, f"[X] 调用异常: {e}"

        if passed:
            passed_count += 1
            print(f"   [OK] 通过 —— {reason}")
        else:
            print(f"   [FAIL] 失败 —— {reason}")

        answer_preview = str(result.get("answer", ""))[:70].replace("\n", " ")
        print(f"   回答: {answer_preview}")

        results.append({
            "id": qid,
            "type": qtype,
            "question": question,
            "must_reject": item["must_reject"],
            "passed": passed,
            "reason": reason,
            "answer": result.get("answer"),
            "confidence": result.get("confidence"),
            "supporting": result.get("supporting"),
            "risks": result.get("risks"),
        })

        time.sleep(0.5)   # 稍微等一下，避免请求太密集

    # ---------- 4. 汇总 ----------
    total = len(testset)
    rate = passed_count / total * 100

    print("\n" + "=" * 72)
    print(f"\n评测结果：{passed_count} / {total} 通过（{rate:.1f}%）\n")

    # 按题型统计
    print("按题型统计：")
    for t in ["A", "B", "C", "D", "E"]:
        items = [r for r in results if r["type"] == t]
        if items:
            p = sum(1 for r in items if r["passed"])
            bar = "#" * p + "." * (len(items) - p)
            print(f"  {t} 类（{len(items)}题）：{p}/{len(items)}   [{bar}]")

    # 失败清单
    failed = [r for r in results if not r["passed"]]
    if failed:
        print(f"\n失败的题（{len(failed)} 道）：")
        for r in failed:
            print(f"  [{r['id']}] ({r['type']}类) {r['question']}")
            print(f"       原因：{r['reason']}")
    else:
        print("\n全部通过！")

    # ---------- 5. 保存结果 ----------
    summary = {
        "total": total,
        "passed": passed_count,
        "pass_rate": round(rate, 1),
        "results": results,
    }
    RESULT_FILE.parent.mkdir(exist_ok=True)
    with open(RESULT_FILE, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"\n详细结果已保存到：{RESULT_FILE}")


if __name__ == "__main__":
    main()
