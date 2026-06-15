"""
初筛 Agent
根据硬性条件（must_have 列表）判断候选人是否通过初筛。
"""

import json
import logging
from typing import Dict, Any

from utils.llm_client import get_llm_client
from utils.prompts import PREFILTER_SYSTEM_PROMPT, PREFILTER_USER_PROMPT

logger = logging.getLogger(__name__)


def prefilter(must_have: list, resume_json: Dict[str, Any]) -> Dict[str, Any]:
    """
    执行初筛判断

    Args:
        must_have: 硬性条件列表（字符串数组）
        resume_json: 候选人结构画像

    Returns:
        包含 pass, reason, checks 的字典
    """
    if not must_have:
        logger.warning("初筛规则为空，默认通过")
        return {"pass": True, "reason": "初筛规则为空，默认通过", "checks": []}

    llm = get_llm_client()

    default = {
        "pass": True,
        "reason": "LLM 判断失败，默认通过初筛（宽容策略）",
        "checks": []
    }

    try:
        result = llm.get_json_response(
            system_prompt=PREFILTER_SYSTEM_PROMPT,
            user_prompt=PREFILTER_USER_PROMPT.format(
                must_have=json.dumps(must_have, ensure_ascii=False),
                resume_json=json.dumps(resume_json, ensure_ascii=False)
            ),
            temperature=0.1,
            default=default,
        )
        logger.info(f"初筛结果: pass={result.get('pass')}, reason={result.get('reason', '')[:50]}")
        return result
    except Exception as e:
        logger.error(f"初筛判断失败: {e}")
        return default
