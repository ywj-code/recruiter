"""
追问生成 Agent
针对候选人简历中的模糊点、矛盾点或需要深入了解的地方，生成追问问题。
"""

import json
import logging
from typing import Dict, Any, List

from utils.llm_client import get_llm_client
from utils.prompts import FOLLOWUP_SYSTEM_PROMPT, FOLLOWUP_USER_PROMPT

logger = logging.getLogger(__name__)

DEFAULT_FOLLOWUP = {
    "followup_questions": [
        {"question": "请详细描述您最近项目中承担的角色和具体贡献", "focus_area": "项目经验", "purpose": "了解实际贡献度"},
        {"question": "您对职位要求的技术栈有多少实际经验？请举例说明", "focus_area": "技术匹配", "purpose": "验证技术深度"},
        {"question": "请分享一次您主导解决技术难题的经历", "focus_area": "解决问题能力", "purpose": "评估独立工作能力"},
    ]
}


def generate_followup_questions(
    resume_json: Dict[str, Any],
    evaluation: Dict[str, Any],
) -> List[Dict[str, str]]:
    """
    生成追问问题

    Args:
        resume_json: 候选人画像
        evaluation: 评估结果（含 recommendation, final_score, strengths, weaknesses）

    Returns:
        追问问题列表
    """
    llm = get_llm_client()
    try:
        result = llm.get_json_response(
            system_prompt=FOLLOWUP_SYSTEM_PROMPT,
            user_prompt=FOLLOWUP_USER_PROMPT.format(
                resume_json=json.dumps(resume_json, ensure_ascii=False),
                recommendation=evaluation.get("recommendation", ""),
                final_score=evaluation.get("final_score", 0),
                strengths=evaluation.get("strengths", ""),
                weaknesses=evaluation.get("weaknesses", ""),
            ),
            temperature=0.5,
            default=DEFAULT_FOLLOWUP,
        )
        questions = result.get("followup_questions", DEFAULT_FOLLOWUP["followup_questions"])
        logger.info(f"追问生成完成: {len(questions)} 个问题")
        return questions
    except Exception as e:
        logger.error(f"追问生成失败: {e}")
        return DEFAULT_FOLLOWUP["followup_questions"]
