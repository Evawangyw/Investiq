"""
db.py — 数据库连接 + 表结构初始化
运行一次即可：python db.py
"""

import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = (
    f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
    f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
)

engine = create_engine(DATABASE_URL)


def get_engine():
    return engine


def init_db():
    """创建所有表，已存在则跳过"""
    with engine.connect() as conn:

        # 财报表 — 存从 SEC EDGAR 拉取的原始数据
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS filings (
                id          SERIAL PRIMARY KEY,
                ticker      TEXT NOT NULL,
                form_type   TEXT NOT NULL,        -- 10-K, 10-Q
                period      TEXT NOT NULL,        -- 2024-Q3
                filed_at    DATE,
                raw_text    TEXT,                 -- 原始财报文本（截取关键段落）
                created_at  TIMESTAMP DEFAULT NOW(),
                UNIQUE(ticker, form_type, period)
            )
        """))

        # 因子表 — 存 LLM 从财报提炼出的结构化指标
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS factors (
                id              SERIAL PRIMARY KEY,
                ticker          TEXT NOT NULL,
                period          TEXT NOT NULL,
                revenue_growth  FLOAT,            -- 营收同比增速
                gross_margin    FLOAT,            -- 毛利率
                guidance_tone   TEXT,             -- 管理层前瞻情绪: positive/neutral/negative
                key_risks       TEXT,             -- LLM 提炼的主要风险点
                key_catalysts   TEXT,             -- LLM 提炼的主要催化剂
                raw_json        TEXT,             -- 完整 LLM 输出备份
                created_at      TIMESTAMP DEFAULT NOW(),
                UNIQUE(ticker, period)
            )
        """))

        # 报告表 — 存 Agent 最终生成的研究报告
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS reports (
                id          SERIAL PRIMARY KEY,
                ticker      TEXT NOT NULL,
                question    TEXT,                 -- 触发这份报告的问题
                content     TEXT,                 -- 完整报告内容
                tool_calls  TEXT,                 -- Agent 调用了哪些工具（JSON）
                created_at  TIMESTAMP DEFAULT NOW()
            )
        """))

        conn.commit()
        print("✓ 数据库表初始化完成")


if __name__ == "__main__":
    init_db()
