"""
JD 规则生成 Agent
分析职位描述（JD），自动生成初筛规则（硬性条件）和复筛规则（评分维度+权重）。
"""

import json
import logging
from typing import Dict, Any

from utils.llm_client import get_llm_client
from utils.prompts import JD_AGENT_SYSTEM_PROMPT, JD_AGENT_USER_PROMPT
from utils.validators import validate_json_structure, validate_dimensions, validate_initial_screening

logger = logging.getLogger(__name__)


def generate_rules(jd_text: str) -> Dict[str, Any]:
    """
    调用 JD 规则生成 Agent

    Args:
        jd_text: JD 文本内容

    Returns:
        包含 initial_screening 和 secondary_screening 的字典
    """
    llm = get_llm_client()

    default_result = {
        "initial_screening": {
            "must_have": [],
            "description": "无明确硬性条件，所有候选人进入复筛"
        },
        "secondary_screening": {
            "dimensions": [
                {"name": "技术匹配", "weight": 40, "criteria": "技术栈匹配程度"},
                {"name": "项目经验", "weight": 30, "criteria": "项目复杂度、主导程度"},
                {"name": "软性素质", "weight": 20, "criteria": "沟通、学习能力"},
                {"name": "文化契合", "weight": 10, "criteria": "价值观、团队协作"}
            ],
            "scoring_guide": "每个维度0-100分，加权总分0-100。总分>=80推荐面试，60-79待定，<60不推荐。"
        }
    }

    try:
        result = llm.get_json_response(
            system_prompt=JD_AGENT_SYSTEM_PROMPT,
            user_prompt=JD_AGENT_USER_PROMPT.format(jd_text=jd_text),
            temperature=0.2,
            default=default_result,
        )

        # 验证结果结构
        if not validate_json_structure(result, ["initial_screening", "secondary_screening"], "JD规则"):
            logger.warning("JD 规则生成结果缺少必要字段，使用默认值")
            return default_result

        if not validate_initial_screening(result["initial_screening"]):
            logger.warning("初筛规则验证失败，使用默认初筛规则")
            result["initial_screening"] = default_result["initial_screening"]

        if not validate_dimensions(result["secondary_screening"]):
            logger.warning("复筛规则维度权重验证失败，使用默认复筛规则")
            result["secondary_screening"] = default_result["secondary_screening"]

        logger.info("JD 规则生成成功")
        return result

    except Exception as e:
        logger.error(f"JD 规则生成失败: {e}")
        return default_result
