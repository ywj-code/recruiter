"""
LangGraph 状态定义
使用 TypedDict 定义简历评估工作流中各节点的输入/输出状态。
"""

from typing import TypedDict, List, Dict, Any, Optional


class ResumeEvaluationState(TypedDict):
    """单份简历评估工作流的状态"""

    # 输入
    resume_text: str                      # 简历原始文本
    resume_name: str                      # 简历文件名
    jd_rules_id: int                      # 使用的规则版本 ID
    initial_screening: Dict[str, Any]     # 初筛规则
    secondary_screening: Dict[str, Any]   # 复筛规则

    # 简历解析结果
    resume_json: Optional[Dict[str, Any]]  # 解析后的结构化画像

    # 初筛结果
    initial_pass: Optional[bool]           # 是否通过初筛
    initial_reason: Optional[str]          # 初筛理由

    # 复筛评分结果
    ratings_list: List[Dict[str, Any]]     # 5个评分员的评分结果

    # 综合裁判结果
    final_score: Optional[int]             # 最终分数
    recommendation: Optional[str]          # pass / consider / reject
    strengths: Optional[str]               # 亮点
    weaknesses: Optional[str]              # 拒因
    used_ratings: List[int]                # 使用的评分员

    # 流程控制
    error: Optional[str]                   # 错误信息
    current_step: str                      # 当前步骤
