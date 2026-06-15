"""
LangGraph 简历评估工作流
实现：简历解析 → 初筛 → 并行复筛评分 → 综合裁判

工作流图结构：
    Start → ParseResume → PreFilter
                          ├── pass → ParallelScorers → Judge → End
                          └── reject → Judge(bypass) → End
"""

import logging
from typing import Dict, Any

from langgraph.graph import StateGraph, END

from graph.state import ResumeEvaluationState
from agents.resume_parser import parse_resume
from agents.prefilter import prefilter
from agents.scorers import run_all_scorers
from agents.judge import judge_results

logger = logging.getLogger(__name__)


# ──────────── 节点函数 ────────────

def node_parse_resume(state: ResumeEvaluationState) -> Dict[str, Any]:
    """节点：简历解析"""
    logger.info(f"[工作流] 解析简历: {state.get('resume_name', '未知')}")
    resume_json = parse_resume(state["resume_text"])
    return {
        "resume_json": resume_json,
        "current_step": "parsed"
    }


def node_prefilter(state: ResumeEvaluationState) -> Dict[str, Any]:
    """节点：初筛"""
    logger.info(f"[工作流] 初筛: {state.get('resume_name', '未知')}")
    must_have = state["initial_screening"].get("must_have", [])
    resume_json = state.get("resume_json") or {}

    result = prefilter(must_have, resume_json)
    return {
        "initial_pass": result.get("pass", True),
        "initial_reason": result.get("reason", "判断失败，默认通过"),
        "current_step": "prefiltered"
    }


def node_parallel_scorers(state: ResumeEvaluationState) -> Dict[str, Any]:
    """节点：并行复筛评分（5个评分员）"""
    logger.info(f"[工作流] 复筛评分: {state.get('resume_name', '未知')}")
    secondary = state["secondary_screening"]
    resume_json = state.get("resume_json") or {}

    ratings = run_all_scorers(secondary, resume_json)
    return {
        "ratings_list": ratings,
        "current_step": "scored"
    }


def node_judge(state: ResumeEvaluationState) -> Dict[str, Any]:
    """节点：综合裁判"""
    logger.info(f"[工作流] 综合裁判: {state.get('resume_name', '未知')}")

    initial_result = {
        "pass": state.get("initial_pass", True),
        "reason": state.get("initial_reason", "")
    }

    # 如果初筛不通过，跳过复筛评分，直接裁判为 reject
    if not initial_result["pass"]:
        logger.info(f"[工作流] 初筛不通过，直接标记 reject")
        return {
            "final_score": 0,
            "recommendation": "reject",
            "strengths": "",
            "weaknesses": initial_result["reason"],
            "used_ratings": [],
            "ratings_list": [],
            "current_step": "judged"
        }

    # 复筛评分 + 综合裁判
    ratings = state.get("ratings_list", [])
    if not ratings:
        logger.warning("[工作流] 评分结果为空，使用默认值")
        return {
            "final_score": 50,
            "recommendation": "consider",
            "strengths": "",
            "weaknesses": "评分流程异常",
            "used_ratings": [],
            "current_step": "judged"
        }

    result = judge_results(initial_result, ratings)

    return {
        "final_score": result.get("final_score", 50),
        "recommendation": result.get("recommendation", "consider"),
        "strengths": result.get("strengths", ""),
        "weaknesses": result.get("weaknesses", ""),
        "used_ratings": result.get("used_ratings", []),
        "current_step": "judged"
    }


# ──────────── 条件路由 ────────────

def route_after_prefilter(state: ResumeEvaluationState) -> str:
    """初筛后路由：通过 → 复筛；不通过 → 直接裁判"""
    if state.get("initial_pass", True):
        return "parallel_scorers"
    else:
        return "judge"


# ──────────── 构建工作流图 ────────────

def build_evaluation_graph() -> StateGraph:
    """
    构建简历评估工作流图

    Returns:
        编译后的 LangGraph StateGraph
    """
    workflow = StateGraph(ResumeEvaluationState)

    # 添加节点
    workflow.add_node("parse_resume", node_parse_resume)
    workflow.add_node("prefilter", node_prefilter)
    workflow.add_node("parallel_scorers", node_parallel_scorers)
    workflow.add_node("judge", node_judge)

    # 设置入口
    workflow.set_entry_point("parse_resume")

    # 添加边
    workflow.add_edge("parse_resume", "prefilter")

    # 条件分支：初筛后 → 复筛 或 直接裁判
    workflow.add_conditional_edges(
        "prefilter",
        route_after_prefilter,
        {
            "parallel_scorers": "parallel_scorers",
            "judge": "judge",
        }
    )

    workflow.add_edge("parallel_scorers", "judge")
    workflow.add_edge("judge", END)

    compiled = workflow.compile()
    logger.info("LangGraph 评估工作流编译完成")
    return compiled


# ──────────── 便捷调用函数 ────────────

# 全局单例
_evaluation_graph = None


def get_evaluation_graph() -> StateGraph:
    """获取全局工作流实例"""
    global _evaluation_graph
    if _evaluation_graph is None:
        _evaluation_graph = build_evaluation_graph()
    return _evaluation_graph


def evaluate_single_resume(
    resume_text: str,
    resume_name: str,
    jd_rules_id: int,
    initial_screening: Dict[str, Any],
    secondary_screening: Dict[str, Any],
) -> Dict[str, Any]:
    """
    评估单份简历（便捷函数）

    Args:
        resume_text: 简历文本
        resume_name: 文件名
        jd_rules_id: 规则版本 ID
        initial_screening: 初筛规则
        secondary_screening: 复筛规则

    Returns:
        最终评估状态字典
    """
    graph = get_evaluation_graph()
    initial_state: ResumeEvaluationState = {
        "resume_text": resume_text,
        "resume_name": resume_name,
        "jd_rules_id": jd_rules_id,
        "initial_screening": initial_screening,
        "secondary_screening": secondary_screening,
        "resume_json": None,
        "initial_pass": None,
        "initial_reason": None,
        "ratings_list": [],
        "final_score": None,
        "recommendation": None,
        "strengths": None,
        "weaknesses": None,
        "used_ratings": [],
        "error": None,
        "current_step": "start",
    }

    final_state = graph.invoke(initial_state)
    return final_state
