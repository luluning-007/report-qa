"""
answer.py —— Day 3：调 AI 生成回答

流程：
  问题  →  检索出 5 个块  →  拼进 Prompt  →  发给 DeepSeek  →  得到带引用的回答

用法：
  python answer.py "2025年营业收入是多少"
"""

import json
import os
import sys

from openai import OpenAI

from retrieve import build_index, load_chunks, search

# ============================================================
# DeepSeek API 配置
# ============================================================
API_KEY = os.environ.get("DEEPSEEK_API_KEY")   # 从环境变量读，不写死在代码里
BASE_URL = "https://api.deepseek.com"
MODEL = "deepseek-chat"


# ============================================================
# ⭐ 核心：Prompt（决定它会不会瞎编）
# ============================================================
PROMPT_TEMPLATE = """你是一个年报分析助手。请严格根据下面提供的资料回答问题。

【规则】
1. 只允许使用资料中的信息，不许使用你自己的常识或记忆
2. 如果资料中没有答案，answer 字段必须写"资料中没有找到相关内容"，并把 can_answer 设为 false
3. supporting 里每一条都必须注明来源（文件名 + 页码）
4. 只输出 JSON 格式，不要输出任何其他文字、不要加解释

【输出格式】
{{
  "answer": "一句话结论",
  "confidence": "高 或 中 或 低",
  "supporting": [
    {{"point": "支撑这个结论的事实", "file": "文件名", "page": 页码}}
  ],
  "risks": ["需要提醒用户注意的、或资料不足的地方"],
  "can_answer": true 或 false
}}

【置信度怎么判断】
- 高：资料里有明确、直接的数字或表述
- 中：资料里有相关信息，但需要推断或计算
- 低：资料里只有间接提示，或者存在口径不一致

【资料】
{context}

【问题】
{question}
"""

def build_context(found_chunks):
    """把检索到的块拼成一段"给 AI 看的资料"

    每块前面标上来源，这样 AI 才知道该引用哪个文件、哪一页。
    """
    parts = []
    for i, c in enumerate(found_chunks, 1):
        parts.append(f"[资料{i}] 来源：{c['file']} 第 {c['page']} 页\n{c['text']}")
    return "\n\n".join(parts)


def parse_json_safely(raw):
    """把 AI 的输出解析成 JSON

    模型有时候会用 ```json ... ``` 把结果包起来，
    所以要先把这层壳剥掉。
    """
    text = raw.strip()
    if text.startswith("```"):
        # 去掉开头的 ```json 和结尾的 ```
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # 解析失败也要返回，不能让程序崩掉
        return {
            "answer": raw,
            "can_answer": None,
            "citations": [],
            "parse_error": True,
        }


def answer_question(question, chunks, bm25, top_k=5):
    """核心函数：检索 → 拼 Prompt → 调 AI → 解析结果"""

    # ---------- 1) 检索：找出最相关的 5 个块 ----------
    found = search(question, chunks, bm25, top_k=top_k)

    # ---------- 2) 拼 Prompt ----------
    context = build_context(found)
    prompt = PROMPT_TEMPLATE.format(context=context, question=question)

    # ---------- 3) 调用 DeepSeek ----------
    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,          # 0 = 尽量稳定，不要自由发挥
    )

    raw = response.choices[0].message.content
    usage = response.usage

    # ---------- 4) 解析 JSON ----------
    result = parse_json_safely(raw)
    result["_retrieved"] = found                 # 保留了哪些块（方便调试）
    result["_tokens"] = {                        # 用了多少 token（成本意识）
        "输入": usage.prompt_tokens,
        "输出": usage.completion_tokens,
    }
    return result


# ============================================================
# 命令行测试
# ============================================================
def main():
    if not API_KEY:
        print("❌ 没读到 DEEPSEEK_API_KEY 环境变量")
        print("   请先设置环境变量，然后重启终端")
        return

    if len(sys.argv) < 2:
        print('用法: python answer.py "你的问题"')
        return

    question = sys.argv[1]

    print("正在加载索引...")
    chunks = load_chunks()
    bm25 = build_index(chunks)

    print(f"问题: {question}")
    print("正在问 AI...\n")

    result = answer_question(question, chunks, bm25)

    print("=" * 60) 
    print("结论：")
    print(result.get("answer", "（无）"))
    print()

    if result.get("can_answer") is False:
        print("⚠️  系统判断：资料中没有找到依据")
    else:
        # 置信度
        print(f"置信度：{result.get('confidence', '未提供')}")
        print()

        # 支撑因素
        supporting = result.get("supporting", [])
        if supporting:
            print("支撑因素：")
            for s in supporting:
                print(f"  · {s.get('point')}")
                print(f"    📄 {s.get('file')}  第 {s.get('page')} 页")
            print()

        # 待核实 / 风险
        risks = result.get("risks", [])
        if risks:
            print("待核实 / 风险：")
            for r in risks:
                print(f"  ⚠️ {r}")
            print()

    print("=" * 60)

    # 成本信息
    t = result.get("_tokens", {})
    if t:
        print(f"\n本次消耗 token：输入 {t.get('输入')} / 输出 {t.get('输出')}")

    # 如果 JSON 解析失败，把原始输出打出来方便排查
    if result.get("parse_error"):
        print("\n⚠️ JSON 解析失败，AI 的原始输出是：")
        print(result["answer"][:500])


if __name__ == "__main__":
    main()
