"""
简历解析 Agent
将简历文本解析为结构化画像（JSON 格式）。
"""

import json
import logging
from typing import Dict, Any

from utils.llm_client import get_llm_client
from utils.prompts import RESUME_PARSER_SYSTEM_PROMPT, RESUME_PARSER_USER_PROMPT

logger = logging.getLogger(__name__)

DEFAULT_PROFILE = {
    "name": "未知",
    "gender": "",
    "age": None,
    "education": "未知",
    "school": "未知",
    "years_of_experience": None,
    "current_company": "",
    "current_position": "",
    "skills": [],
    "work_experience": [],
    "project_experience": [],
    "certifications": [],
    "language_ability": "",
    "summary": "解析失败"
}


def parse_resume(resume_text: str) -> Dict[str, Any]:
    """
    解析简历文本

    Args:
        resume_text: 简历纯文本

    Returns:
        结构化的候选人画像字典
    """
    llm = get_llm_client()
    try:
        result = llm.get_json_response(
            system_prompt=RESUME_PARSER_SYSTEM_PROMPT,
            user_prompt=RESUME_PARSER_USER_PROMPT.format(resume_text=resume_text[:8000]),
            temperature=0.1,
            default=DEFAULT_PROFILE,
        )
        # 确保必要字段存在
        for key in DEFAULT_PROFILE:
            if key not in result:
                result[key] = DEFAULT_PROFILE[key]
        logger.info(f"简历解析成功: {result.get('name', '未知')}")
        return result
    except Exception as e:
        logger.error(f"简历解析失败: {e}")
        return DEFAULT_PROFILE
