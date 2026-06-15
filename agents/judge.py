"""
综合裁判 Agent
聚合 5 个评分员的结果，输出最终分数、推荐状态、亮点/拒因。
"""

import json
import logging
from typing import Dict, Any, List
from statistics import median

from utils.llm_client import get_llm_client
from utils.prompts import JUDGE_SYSTEM_PROMPT, JUDGE_USER_PROMPT

logger = logging.getLogger(__name__)


def judge_results(
    initial_result: Dict[str, Any],
    ratings_list: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    综合裁判

    Args:
        initial_result: 初筛结果 {"pass": bool, "reason": str}
        ratings_list: 评分员结果列表，每项含 scorer_name, score 等

    Returns:
        最终结论字典
    """
    llm = get_llm_client()

    # ── 规则化预处理：计算中位数和异常检测 ──
    scores = [r.get("score", 0) for r in ratings_list if r.get("score") is not None]

    if len(scores) >= 2:
        med = median(scores)

        # 标记异常：与中位数差 > 30 且置信度低
        valid_indices = []
        for i, r in enumerate(ratings_list):
            s = r.get("score", 0)
            conf = r.get("confidence", "中")
            if abs(s - med) > 30 and conf == "低":
                logger.info(f"剔除异常评分: {r.get('scorer_name')} score={s} (中位数={med:.1f}, 置信度={conf})")
            else:
                valid_indices.append(i)

        if len(valid_indices) < 2:
            logger.warning(f"有效评分不足（{len(valid_indices)}个），最终分数设为50")
            return {
                "final_score": 50,
                "recommendation": "consider",
                "strengths": "",
                "weaknesses": "有效评分员不足，无法给出可靠结论",
                "used_ratings": [i + 1 for i in valid_indices],
            }

        final_score = round(median([scores[i] for i in valid_indices]))
    else:
        final_score = 50
        valid_indices = list(range(len(ratings_list)))

    # ── 确定推荐状态 ──
    if not initial_result.get("pass", True):
        recommendation = "reject"
        weaknesses = initial_result.get("reason", "初筛不通过")
        strengths = ""
    elif final_score >= 80:
        recommendation = "pass"
        strengths = ""
        weaknesses = ""
    elif final_score >= 60:
        recommendation = "consider"
        strengths = ""
        weaknesses = ""
    else:
        recommendation = "reject"
        strengths = ""
        weaknesses = "综合评分低于60分"

    # ── 调用 LLM 润色亮点/拒因（有评分员理由时） ──
    try:
        llm_result = llm.get_json_response(
            system_prompt=JUDGE_SYSTEM_PROMPT,
            user_prompt=JUDGE_USER_PROMPT.format(
                initial_result=json.dumps(initial_result, ensure_ascii=False),
                ratings_list=json.dumps(ratings_list, ensure_ascii=False),
            ),
            temperature=0.2,
            default={
                "final_score": final_score,
                "recommendation": recommendation,
                "strengths": strengths,
                "weaknesses": weaknesses,
                "used_ratings": [i + 1 for i in valid_indices],
            },
        )

        # 使用规则计算的结果覆盖 LLM 可能存在的不一致
        llm_result["final_score"] = final_score
        llm_result["recommendation"] = recommendation
        llm_result["used_ratings"] = [i + 1 for i in valid_indices]

        # 如果 LLM 未覆盖亮点/拒因，使用规则结果
        if recommendation == "pass" and not llm_result.get("strengths"):
            # 从评分员理由中提取亮点
            reasons = [r.get("reason", "") for r in ratings_list if r.get("score", 0) >= 70]
            if reasons:
                llm_result["strengths"] = reasons[0][:200]

        if recommendation == "reject" and not llm_result.get("weaknesses"):
            llm_result["weaknesses"] = weaknesses

        logger.info(f"裁判完成: score={final_score}, recommendation={recommendation}")
        return llm_result

    except Exception as e:
        logger.error(f"综合裁判 LLM 调用失败: {e}")
        return {
            "final_score": final_score,
            "recommendation": recommendation,
            "strengths": strengths,
            "weaknesses": weaknesses,
            "used_ratings": [i + 1 for i in valid_indices],
        }
