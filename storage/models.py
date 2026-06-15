"""
Pydantic 数据模型定义
对应 SQLite 表结构和 API 交互数据结构。
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


# ── 初筛规则 ──

class InitialScreeningRule(BaseModel):
    """初筛规则：硬性条件"""
    must_have: List[str] = Field(default_factory=list, description="必须满足的条件列表")
    description: str = ""


# ── 复筛规则 ──

class Dimension(BaseModel):
    """复筛维度定义"""
    name: str
    weight: float
    criteria: str


class SecondaryScreeningRule(BaseModel):
    """复筛规则：评分维度及权重"""
    dimensions: List[Dimension] = Field(default_factory=list)
    scoring_guide: str = "每个维度0-100分，加权总分0-100。总分>=80推荐面试，60-79待定，<60不推荐。"


# ── 完整规则 ──

class ScreeningRules(BaseModel):
    """完整的筛选规则"""
    initial_screening: InitialScreeningRule = Field(default_factory=InitialScreeningRule)
    secondary_screening: SecondaryScreeningRule = Field(default_factory=SecondaryScreeningRule)


# ── 简历画像 ──

class ResumeProfile(BaseModel):
    """简历解析后的结构化画像"""
    name: str = ""
    gender: str = ""
    age: Optional[int] = None
    education: str = ""
    school: str = ""
    years_of_experience: Optional[int] = None
    current_company: str = ""
    current_position: str = ""
    skills: List[str] = Field(default_factory=list)
    work_experience: List[Dict[str, Any]] = Field(default_factory=list)
    project_experience: List[Dict[str, Any]] = Field(default_factory=list)
    certifications: List[str] = Field(default_factory=list)
    language_ability: str = ""
    summary: str = ""


# ── 初筛结果 ──

class InitialScreenResult(BaseModel):
    """初筛结果"""
    passed: bool = False
    reason: str = ""


# ── 评分员结果 ──

class ScorerResult(BaseModel):
    """单个评分员的评分结果"""
    scorer_name: str = ""
    score: int = 0
    dimension_scores: Dict[str, int] = Field(default_factory=dict)
    reason: str = ""
    confidence: str = "中"  # 高/中/低


# ── 综合裁判结果 ──

class FinalJudgment(BaseModel):
    """综合裁判最终结论"""
    final_score: int = 0
    recommendation: str = "consider"  # pass / consider / reject
    strengths: str = ""
    weaknesses: str = ""
    used_ratings: List[int] = Field(default_factory=list)


# ── 评估记录 ──

class EvaluationRecord(BaseModel):
    """单份简历的完整评估记录"""
    id: Optional[int] = None
    jd_rules_id: int = 0
    resume_name: str = ""
    resume_text: str = ""
    resume_json: str = "{}"
    initial_pass: bool = False
    initial_reason: str = ""
    final_score: int = 0
    recommendation: str = "consider"
    strengths: str = ""
    weaknesses: str = ""
    ratings_detail: str = "[]"
    evaluated_at: Optional[str] = None


# ── JD 规则记录 ──

class JDRulesRecord(BaseModel):
    """JD 规则版本记录"""
    id: Optional[int] = None
    jd_text: str = ""
    initial_screening: str = "{}"
    secondary_screening: str = "{}"
    version: int = 1
    created_at: Optional[str] = None


# ── 反思日志 ──

class ReflectionLog(BaseModel):
    """反思与进化日志"""
    id: Optional[int] = None
    jd_rules_id: int = 0
    batch_evaluations_ids: str = "[]"
    updated_rules: str = "{}"
    change_log: str = ""
    created_at: Optional[str] = None
