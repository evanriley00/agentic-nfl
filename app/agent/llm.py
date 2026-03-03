import os
import json
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from openai import OpenAI

from app.agent.schema import AgentDecision

load_dotenv()

_client: Optional[OpenAI] = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is missing. Put it in your .env file.")
        _client = OpenAI(api_key=api_key)
    return _client


def decide_with_llm(user_message: str, history: list[dict[str, str]]) -> AgentDecision:
    print("LLM DECIDE CALLED [OK]")

    client = get_client()

    # Strict schema: only allow calculator + required expression arg
    tools = [
        {
            "type": "function",
            "function": {
                "name": "agent_decision",
                "description": "Return the agent's next action as an AgentDecision.",
                "parameters": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "type": {"type": "string", "enum": ["tool", "final"]},
                        "tool": {
                            "type": ["object", "null"],
                            "additionalProperties": False,
                            "properties": {
                                "name": {"type": "string", "enum": ["calculator"]},
                                "args": {
                                    "type": "object",
                                    "additionalProperties": False,
                                    "properties": {
                                        "expression": {"type": "string"}
                                    },
                                    "required": ["expression"]
                                }
                            },
                            "required": ["name", "args"]
                        },
                        "final": {"type": ["string", "null"]}
                    },
                    "required": ["type"]
                }
            }
        }
    ]

    system = (
        "You are an agent controller.\n"
        "You MUST choose ONE:\n"
        "- type='tool' with tool.name + tool.args\n"
        "- type='final' with a short final answer\n\n"
        "Available tools:\n"
        "- calculator(expression: str)\n\n"
        "Rules:\n"
        "1) If the user asks for math, use calculator.\n"
        "2) Otherwise return type='final'.\n"
        "3) Never invent tools.\n"
    )

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages = [{"role": "system", "content": system}] + history + [{"role": "user", "content": user_message}],
        tools=tools,
        tool_choice={"type": "function", "function": {"name": "agent_decision"}},
    )

    msg = resp.choices[0].message
    if not msg.tool_calls:
        return AgentDecision(type="final", final="No decision returned.")

    raw_args: Any = msg.tool_calls[0].function.arguments
    if isinstance(raw_args, str):
        raw_args = json.loads(raw_args)

    return AgentDecision.model_validate(raw_args)

