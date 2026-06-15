"""
反思与进化 Agent
分析批量简历评估结果与规则之间的偏差，自动更新初筛/复筛规则。
"""

import json
import logging
from typing import Dict, Any, List

from utils.llm_client import get_llm_client
from utils.prompts import REFLECTION_SYSTEM_PROMPT, REFLECTION_USER_PROMPT

logger = logging.getLogger(__name__)


def reflect_and_evolve(
    current_rules: Dict[str, Any],
    evaluation_results: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    反思与进化

    Args:
        current_rules: 当前使用的规则 {"initial_screening": ..., "secondary_screening": ...}
        evaluation_results: 评估结果列表，每项含 initial_pass, final_score, recommendation 等

    Returns:
        包含 updated_initial_screening, updated_secondary_screening, change_log 的字典
    """
    if len(evaluation_results) < 3:
        logger.warning("评估结果不足3份，跳过反思")
        return {
            "updated_initial_screening": current_rules.get("initial_screening", {}),
            "updated_secondary_screening": current_rules.get("secondary_screening", {}),
            "change_log": "评估结果不足3份，跳过反思分析",
            "analysis": "数据不足"
        }

    llm = get_llm_client()

    # 构建摘要
    total = len(evaluation_results)
    pass_count = sum(1 for r in evaluation_results if r.get("recommendation") == "pass")
    consider_count = sum(1 for r in evaluation_results if r.get("recommendation") == "consider")
    reject_count = sum(1 for r in evaluation_results if r.get("recommendation") == "reject")
    initial_fail = sum(1 for r in evaluation_results if not r.get("initial_pass", True))
    initial_pass_rate = (total - initial_fail) / total * 100 if total > 0 else 0

    summary = {
        "total_candidates": total,
        "pass": pass_count,
        "consider": consider_count,
        "reject": reject_count,
        "initial_fail_count": initial_fail,
        "initial_pass_rate": f"{initial_pass_rate:.0f}%",
        "details": []
    }

    for r in evaluation_results:
        summary["details"].append({
            "name": r.get("resume_name", "未知"),
            "initial_pass": r.get("initial_pass", True),
            "initial_reason": r.get("initial_reason", ""),
            "final_score": r.get("final_score", 0),
            "recommendation": r.get("recommendation", "consider"),
            "strengths": r.get("strengths", ""),
            "weaknesses": r.get("weaknesses", ""),
        })

    default_rules = {
        "updated_initial_screening": current_rules.get("initial_screening", {}),
        "updated_secondary_screening": current_rules.get("secondary_screening", {}),
        "change_log": "反思分析执行失败，规则保持不变",
        "analysis": "LLM 调用失败"
    }

    try:
        result = llm.get_json_response(
            system_prompt=REFLECTION_SYSTEM_PROMPT,
            user_prompt=REFLECTION_USER_PROMPT.format(
                current_rules=json.dumps(current_rules, ensure_ascii=False),
                results_summary=json.dumps(summary, ensure_ascii=False),
            ),
            temperature=0.3,
            max_tokens=4096,
            default=default_rules,
        )

        logger.info(f"反思分析完成: change_log={result.get('change_log', '')[:80]}")
        return result

    except Exception as e:
        logger.error(f"反思分析失败: {e}")
        return default_rules
