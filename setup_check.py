"""
setup_check.py — 一键验证所有组件是否正常
"""

import sys

def check(label, fn):
    try:
        fn()
        print(f"  ✓  {label}")
        return True
    except Exception as e:
        print(f"  ✗  {label}")
        print(f"       错误: {e}")
        return False


def test_env():
    from dotenv import load_dotenv
    import os
    load_dotenv()
    assert os.getenv("ANTHROPIC_API_KEY"), "缺少 ANTHROPIC_API_KEY"
    assert os.getenv("DB_NAME"), "缺少 DB_NAME"


def test_db():
    from db import engine
    from sqlalchemy import text
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))


def test_db_tables():
    from db import init_db
    init_db()


def test_chroma():
    from vector_store import add_documents, query_documents
    add_documents(
        texts=["Setup check test document about NVIDIA AI chips"],
        metadatas=[{"ticker": "NVDA", "source": "setup_check", "date": "2024-01-01"}],
        ids=["setup_check_001"]
    )
    results = query_documents("NVIDIA chip", n_results=1)
    assert len(results) > 0


def test_claude():
    from claude_client import simple_chat
    reply = simple_chat("Reply with just the word: OK")
    assert len(reply) > 0


if __name__ == "__main__":
    print("=" * 40)
    print("InvestIQ — 环境检查")
    print("=" * 40)

    results = [
        check(".env 文件加载", test_env),
        check("PostgreSQL 连接", test_db),
        check("数据库表初始化", test_db_tables),
        check("Chroma 存取", test_chroma),
        check("Claude API 调用", test_claude),
    ]

    print("=" * 40)
    passed = sum(results)
    total = len(results)

    if passed == total:
        print(f"全部通过 ({passed}/{total}) — Day 1-2 完成 ✓")
        print("\n下一步：运行 python tools/filing_tool.py 开始 Day 3-4")
    else:
        print(f"通过 {passed}/{total}，请根据错误信息逐一修复")
        sys.exit(1)
