"""
数据验证工具
提供 JSON 格式校验、必要字段检查等功能。
"""

import json
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


def validate_json_structure(data: Dict, required_keys: List[str], context: str = "") -> bool:
    """
    验证 JSON 字典是否包含所有必要的键。

    Args:
        data: 待验证的字典
        required_keys: 必须存在的键列表
        context: 上下文描述（用于日志）

    Returns:
        验证是否通过
    """
    missing = [k for k in required_keys if k not in data]
    if missing:
        logger.warning(f"{context} JSON 缺少必要字段: {missing}")
        return False
    return True


def safe_parse_json(text: str, default: Optional[Dict] = None) -> Dict[str, Any]:
    """
    安全解析 JSON 文本，解析失败返回默认值。

    Args:
        text: JSON 文本
        default: 默认值

    Returns:
        解析后的字典
    """
    try:
        # 清理 markdown 代码块
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:])
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
        return json.loads(text)
    except (json.JSONDecodeError, Exception) as e:
        logger.warning(f"JSON 安全解析失败: {e}")
        return default if default is not None else {}


def validate_dimensions(data: Dict) -> bool:
    """
    验证复筛规则中的维度定义是否合法（权重总和应为100）。

    Args:
        data: 包含 dimensions 列表和 scoring_guide 的字典

    Returns:
        是否合法
    """
    dims = data.get("dimensions", [])
    if not dims:
        return False
    total_weight = sum(d.get("weight", 0) for d in dims)
    if abs(total_weight - 100) > 1:  # 允许1分误差
        logger.warning(f"维度权重总和为 {total_weight}，不等于 100")
        return False
    return True


def validate_initial_screening(data: Dict) -> bool:
    """
    验证初筛规则是否合法。

    Args:
        data: 包含 must_have 列表的字典

    Returns:
        是否合法
    """
    must_have = data.get("must_have", [])
    if not isinstance(must_have, list) or len(must_have) == 0:
        logger.warning("初筛规则 must_have 为空或格式错误")
        return False
    return True
