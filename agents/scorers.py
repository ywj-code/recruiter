"""
复筛评分员 Agent（5 种评估性格并行打分）

提供 5 种不同评估视角的评分员：
1. 严格型 - 高标准严要求，对任何瑕疵敏感
2. 宽松型 - 看重潜力，对不足较宽容
3. 技术导向型 - 重点考察技术深度和广度
4. 文化导向型 - 重点考察团队契合度和软技能
5. 综合型 - 全面平衡各方面因素
"""

import json
import logging
from typing import Dict, Any, List
from concurrent.futures import ThreadPoolExecutor, as_completed

from utils.llm_client import get_llm_client
from utils.prompts import SCORER_SYSTEM_PROMPT, SCORER_USER_PROMPT

logger = logging.getLogger(__name__)

# 五种评分员性格定义（保留在 agent 代码中，非 prompt 文本）
SCORER_PERSONAS = [
    {"name": "严格型评分员", "persona": "严格苛刻、标准极高，对候选人的任何瑕疵都高度敏感，只有明显超出要求的候选人才给高分", "temperature": 0.1},
    {"name": "宽松型评分员", "persona": "宽容友好、看重候选人潜力与成长性，对于经验略不足但学习能力强的候选人也会给较高分数", "temperature": 0.4},
    {"name": "技术导向型评分员", "persona": "极度关注技术深度与广度，会深入评估技术栈匹配度、代码能力、架构经验等硬技能", "temperature": 0.2},
    {"name": "文化导向型评分员", "persona": "关注候选人与团队的契合度，重点评估沟通能力、协作精神、价值观匹配等软性素质", "temperature": 0.3},
    {"name": "综合型评分员", "persona": "全面平衡各项因素，不偏向任何单一维度，力求给出最公允的评估", "temperature": 0.25},
]

DEFAULT_SCORER_RESULT = {
    "score": 50,
    "dimension_scores": {},
    "reason": "评分失败，使用默认分数",
    "confidence": "低"
}


def _run_single_scorer(
    persona: Dict[str, str],
    secondary_screening: Dict[str, Any],
    resume_json: Dict[str, Any],
) -> Dict[str, Any]:
    """
    运行单个评分员

    Args:
        persona: 评分员性格定义
        secondary_screening: 复筛规则
        resume_json: 候选人画像

    Returns:
        评分结果字典，包含 scorer_name
    """
    try:
        llm = get_llm_client()
        result = llm.get_json_response(
            system_prompt=SCORER_SYSTEM_PROMPT.format(persona=persona["persona"]),
            user_prompt=SCORER_USER_PROMPT.format(
                secondary_screening=json.dumps(secondary_screening, ensure_ascii=False),
                resume_json=json.dumps(resume_json, ensure_ascii=False)
            ),
            temperature=persona.get("temperature", 0.3),
            default=DEFAULT_SCORER_RESULT,
        )
        result["scorer_name"] = persona["name"]
        logger.info(f"{persona['name']} 评分完成: {result.get('score')}")
        return result
    except Exception as e:
        logger.error(f"{persona['name']} 评分失败: {e}")
        fail_result = dict(DEFAULT_SCORER_RESULT)
        fail_result["scorer_name"] = persona["name"]
        fail_result["reason"] = f"评分过程异常: {str(e)}"
        return fail_result


def run_all_scorers(
    secondary_screening: Dict[str, Any],
    resume_json: Dict[str, Any],
    max_workers: int = 5,
) -> List[Dict[str, Any]]:
    """
    并行运行所有 5 个评分员

    Args:
        secondary_screening: 复筛规则
        resume_json: 候选人画像
        max_workers: 最大并行数

    Returns:
        5 个评分员结果的列表
    """
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                _run_single_scorer, persona, secondary_screening, resume_json
            ): persona["name"]
            for persona in SCORER_PERSONAS
        }
        for future in as_completed(futures):
            try:
                results.append(future.result())
            except Exception as e:
                name = futures[future]
                logger.error(f"评分员 {name} 执行异常: {e}")
                fail_result = dict(DEFAULT_SCORER_RESULT)
                fail_result["scorer_name"] = name
                results.append(fail_result)

    # 保持顺序
    name_order = [p["name"] for p in SCORER_PERSONAS]
    results.sort(key=lambda x: name_order.index(x["scorer_name"]) if x["scorer_name"] in name_order else 99)

    logger.info(f"评分员全部完成，共 {len(results)} 份评分")
    return results
