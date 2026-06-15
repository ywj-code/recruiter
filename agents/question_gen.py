"""
试题生成 Agent
为通过初筛的候选人生成面试题本（10 道题），覆盖技术、行为、项目等维度。
"""

import json
import logging
from typing import Dict, Any, List

from utils.llm_client import get_llm_client
from utils.prompts import QUESTION_GEN_SYSTEM_PROMPT, QUESTION_GEN_USER_PROMPT

logger = logging.getLogger(__name__)

DEFAULT_QUESTIONS = {
    "questions": [
        {
            "number": i,
            "type": t,
            "difficulty": d,
            "question": f"第{i}题（{t}/{d}）：请根据您的经验回答",
            "inspection_point": "综合能力",
            "reference_answer": "根据回答评估",
            "estimated_time": 5
        }
        for i, (t, d) in enumerate([
            ("基础知识", "简单"), ("基础知识", "简单"), ("场景设计", "中等"),
            ("编程题", "中等"), ("行为面试", "中等"), ("系统设计", "中等"),
            ("编程题", "困难"), ("系统设计", "困难"), ("场景设计", "困难"),
            ("行为面试", "简单"),
        ], 1)
    ],
    "total_time": 55,
    "difficulty_breakdown": {"简单": 3, "中等": 4, "困难": 3}
}


def generate_questions(
    resume_json: Dict[str, Any],
    jd_text: str,
    evaluation: Dict[str, Any],
) -> Dict[str, Any]:
    """
    生成面试题本

    Args:
        resume_json: 候选人画像
        jd_text: 职位描述
        evaluation: 评估结果

    Returns:
        包含 questions 列表的字典
    """
    llm = get_llm_client()
    try:
        result = llm.get_json_response(
            system_prompt=QUESTION_GEN_SYSTEM_PROMPT,
            user_prompt=QUESTION_GEN_USER_PROMPT.format(
                resume_json=json.dumps(resume_json, ensure_ascii=False),
                jd_text=jd_text[:4000],
                final_score=evaluation.get("final_score", 0),
                strengths=evaluation.get("strengths", ""),
                weaknesses=evaluation.get("weaknesses", ""),
            ),
            temperature=0.6,
            max_tokens=4096,
            default=DEFAULT_QUESTIONS,
        )
        logger.info(f"试题生成完成: {len(result.get('questions', []))} 题")
        return result
    except Exception as e:
        logger.error(f"试题生成失败: {e}")
        return DEFAULT_QUESTIONS
