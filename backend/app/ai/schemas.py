"""AI 研判结构化输出模型与解析（依据设计文档 §8.6）。"""

import json
import re

from pydantic import BaseModel, Field


class AiAnalysis(BaseModel):
    summary: str = ""
    risk_assessment: str = ""
    confidence: float = 0.0
    evidence: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    needs_human_review: bool = False


def parse_response(text: str) -> AiAnalysis:
    """从模型输出中提取 JSON 并校验为 AiAnalysis（容忍代码块围栏/前后杂讯）。"""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("AI 响应中未找到 JSON 对象")
    data = json.loads(match.group(0))
    return AiAnalysis(**data)
