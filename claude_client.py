"""
claude_client.py — Claude API 封装

两种调用模式：
1. simple_chat()   — 普通对话，直接返回文字，用于生成报告文本
2. agent_chat()    — 带工具调用的 Agent 模式，这是 ReAct Agent 的核心
"""

import os
import json
import anthropic
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 8192


def simple_chat(prompt: str, system: str = "") -> str:
    """
    最简单的单轮对话，适合生成报告、总结文本
    遇到服务器过载（529）自动重试3次
    """
    import time
    messages = [{"role": "user", "content": prompt}]
    kwargs = {"model": MODEL, "max_tokens": MAX_TOKENS, "messages": messages}
    if system:
        kwargs["system"] = system

    for attempt in range(3):
        try:
            response = client.messages.create(**kwargs)
            return response.content[0].text
        except anthropic.APIStatusError as e:
            if e.status_code == 529 and attempt < 2:
                wait = (attempt + 1) * 10
                print(f"  服务器过载，{wait}秒后重试（{attempt+1}/3）...")
                time.sleep(wait)
            else:
                raise

def agent_chat(question: str, tools: list[dict], tool_executor, system: str = "", max_steps: int = 10, on_tool_call=None) -> dict:
    """
    ReAct Agent 核心循环
    
    参数：
    - question      用户问题，比如 "NVDA 现在值不值得买"
    - tools         工具定义列表（告诉 Claude 有哪些工具可用）
    - tool_executor 一个函数，接收工具名+参数，真正执行并返回结果
    - system        系统 Prompt
    
    返回：
    {
        "answer":     最终回答文本,
        "tool_calls": [{"tool": "...", "input": {...}, "output": "..."}, ...]
    }
    
    工作流程（ReAct 循环）：
    用户问题
      → Claude 决定调用哪个工具
        → 你的代码执行这个工具
          → 把结果返回给 Claude
            → Claude 决定继续调工具 or 直接回答
              → 循环直到 Claude 不再调工具
    """
    messages = [{"role": "user", "content": question}]
    tool_call_log = []
    
    kwargs = {"model": MODEL, "max_tokens": MAX_TOKENS, "tools": tools, "messages": messages}
    if system:
        kwargs["system"] = system

    # ReAct 循环，最多跑 10 轮防止死循环
    for step in range(max_steps):
        response = client.messages.create(**kwargs)
        
        print(f"\n── Step {step + 1} ── stop_reason: {response.stop_reason}")

        # stop_reason == "end_turn" 表示 Claude 决定直接回答，不再调工具
        if response.stop_reason == "end_turn":
            final_text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    final_text += block.text
            return {"answer": final_text, "tool_calls": tool_call_log}

        # stop_reason == "tool_use" 表示 Claude 要调用一个或多个工具
        if response.stop_reason == "tool_use":
            # 把 Claude 的这轮回复加入对话历史
            messages.append({"role": "assistant", "content": response.content})
            
            # 处理本轮所有工具调用（有时 Claude 会一次要求调多个工具）
            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                
                tool_name = block.name
                tool_input = block.input
                print(f"  → 调用工具: {tool_name}，参数: {json.dumps(tool_input, ensure_ascii=False)}")
                if on_tool_call: on_tool_call("calling", tool_name, tool_input, None)
                
                # 真正执行工具
                try:
                    result = tool_executor(tool_name, tool_input)
                    result_str = json.dumps(result, ensure_ascii=False) if isinstance(result, (dict, list)) else str(result)
                except Exception as e:
                    result_str = f"工具执行出错: {str(e)}"
                
                print(f"  ← 结果: {result_str[:100]}...")
                if on_tool_call: on_tool_call("done", tool_name, tool_input, result_str)
                
                tool_call_log.append({
                    "tool": tool_name,
                    "input": tool_input,
                    "output": result_str
                })
                
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result_str
                })
            
            # 把工具结果返回给 Claude，进入下一轮
            messages.append({"role": "user", "content": tool_results})
            kwargs["messages"] = messages

    return {"answer": "达到最大循环次数，Agent 未能完成任务", "tool_calls": tool_call_log}


# ── 直接运行这个文件就是做连通性测试 ──
if __name__ == "__main__":
    print("测试 Claude API 连接...")
    
    # 测试1：简单对话
    reply = simple_chat("用一句话解释什么是市盈率 P/E ratio")
    print(f"\n简单对话测试：\n{reply}")
    
    # 测试2：工具调用
    print("\n\n工具调用测试...")
    
    test_tools = [
        {
            "name": "get_stock_price",
            "description": "获取某支股票的当前价格",
            "input_schema": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string", "description": "股票代码，如 NVDA"}
                },
                "required": ["ticker"]
            }
        }
    ]
    
    def test_executor(tool_name, tool_input):
        # 假数据，只测试 tool_use 流程是否跑通
        if tool_name == "get_stock_price":
            return {"ticker": tool_input["ticker"], "price": 875.40, "currency": "USD"}
    
    result = agent_chat(
        question="NVDA 现在的股价是多少？",
        tools=test_tools,
        tool_executor=test_executor,
        system="你是一个投资研究助手。"
    )
    
    print(f"\n最终回答：{result['answer']}")
    print(f"工具调用记录：{result['tool_calls']}")
    print("\n✓ Claude API 连通性测试通过")
