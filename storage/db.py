"""
SQLite 数据库初始化和 CRUD 操作
管理 JD 规则版本、简历评估记录、反思日志的持久化存储。
"""

import os
import json
import sqlite3
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from contextlib import contextmanager

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

DB_PATH = os.getenv("DB_PATH", "data/recruiter.db")


def get_db_path() -> str:
    """获取数据库文件路径，确保目录存在"""
    db_dir = os.path.dirname(DB_PATH)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
    return DB_PATH


@contextmanager
def get_connection():
    """获取数据库连接（上下文管理器，自动提交/回滚）"""
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """初始化数据库表结构"""
    with get_connection() as conn:
        cur = conn.cursor()

        # JD 与规则版本表
        cur.execute("""
            CREATE TABLE IF NOT EXISTS jd_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                jd_text TEXT NOT NULL,
                initial_screening TEXT NOT NULL DEFAULT '{}',
                secondary_screening TEXT NOT NULL DEFAULT '{}',
                version INTEGER NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 简历评估记录表
        cur.execute("""
            CREATE TABLE IF NOT EXISTS resume_evaluations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                jd_rules_id INTEGER NOT NULL,
                resume_name TEXT NOT NULL,
                resume_text TEXT NOT NULL DEFAULT '',
                resume_json TEXT NOT NULL DEFAULT '{}',
                initial_pass BOOLEAN DEFAULT 0,
                initial_reason TEXT DEFAULT '',
                final_score INTEGER DEFAULT 0,
                recommendation TEXT DEFAULT 'consider',
                strengths TEXT DEFAULT '',
                weaknesses TEXT DEFAULT '',
                ratings_detail TEXT DEFAULT '[]',
                evaluated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (jd_rules_id) REFERENCES jd_rules(id)
            )
        """)

        # 反思日志表
        cur.execute("""
            CREATE TABLE IF NOT EXISTS reflection_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                jd_rules_id INTEGER NOT NULL,
                batch_evaluations_ids TEXT NOT NULL DEFAULT '[]',
                updated_rules TEXT NOT NULL DEFAULT '{}',
                change_log TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (jd_rules_id) REFERENCES jd_rules(id)
            )
        """)

        logger.info("数据库表初始化完成")


# ──────────────── JD 规则 CRUD ────────────────

def save_jd_rules(jd_text: str, initial_screening: str, secondary_screening: str) -> int:
    """
    保存 JD 规则（新版本）。

    Returns:
        新记录的 ID
    """
    with get_connection() as conn:
        cur = conn.cursor()
        # 查找当前最大版本号
        cur.execute(
            "SELECT MAX(version) FROM jd_rules WHERE jd_text = ?",
            (jd_text,)
        )
        row = cur.fetchone()
        next_ver = (row[0] or 0) + 1

        cur.execute(
            """INSERT INTO jd_rules (jd_text, initial_screening, secondary_screening, version)
               VALUES (?, ?, ?, ?)""",
            (jd_text, initial_screening, secondary_screening, next_ver)
        )
        rule_id = cur.lastrowid
        logger.info(f"JD 规则已保存，ID={rule_id}, version={next_ver}")
        return rule_id


def update_jd_rules(rule_id: int, initial_screening: str, secondary_screening: str):
    """更新指定规则的筛选条件（不创建新版本，用于用户编辑）"""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """UPDATE jd_rules SET initial_screening = ?, secondary_screening = ?
               WHERE id = ?""",
            (initial_screening, secondary_screening, rule_id)
        )
        logger.info(f"JD 规则已更新，ID={rule_id}")


def get_jd_rules(rule_id: int) -> Optional[Dict[str, Any]]:
    """根据 ID 获取 JD 规则"""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM jd_rules WHERE id = ?", (rule_id,))
        row = cur.fetchone()
        if row:
            return dict(row)
        return None


def get_latest_jd_rules() -> Optional[Dict[str, Any]]:
    """获取最新版本的 JD 规则"""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM jd_rules ORDER BY created_at DESC LIMIT 1"
        )
        row = cur.fetchone()
        if row:
            return dict(row)
        return None


def list_jd_rules() -> List[Dict[str, Any]]:
    """列出所有 JD 规则"""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM jd_rules ORDER BY created_at DESC")
        return [dict(row) for row in cur.fetchall()]


# ──────────────── 简历评估 CRUD ────────────────

def save_evaluation(record: Dict[str, Any]) -> int:
    """保存单份简历评估结果"""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO resume_evaluations
               (jd_rules_id, resume_name, resume_text, resume_json,
                initial_pass, initial_reason, final_score, recommendation,
                strengths, weaknesses, ratings_detail)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                record["jd_rules_id"],
                record["resume_name"],
                record.get("resume_text", ""),
                record.get("resume_json", "{}"),
                int(record.get("initial_pass", False)),
                record.get("initial_reason", ""),
                record.get("final_score", 0),
                record.get("recommendation", "consider"),
                record.get("strengths", ""),
                record.get("weaknesses", ""),
                json.dumps(record.get("ratings_detail", []), ensure_ascii=False),
            )
        )
        eval_id = cur.lastrowid
        logger.info(f"简历评估已保存，ID={eval_id}, name={record['resume_name']}")
        return eval_id


def get_evaluation(eval_id: int) -> Optional[Dict[str, Any]]:
    """获取单份简历评估详情"""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM resume_evaluations WHERE id = ?", (eval_id,))
        row = cur.fetchone()
        if row:
            return dict(row)
        return None


def list_evaluations_by_rules(jd_rules_id: int) -> List[Dict[str, Any]]:
    """列出某规则版本下所有评估记录"""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM resume_evaluations WHERE jd_rules_id = ? ORDER BY final_score DESC",
            (jd_rules_id,)
        )
        return [dict(row) for row in cur.fetchall()]


def get_pass_candidates(jd_rules_id: int) -> List[Dict[str, Any]]:
    """获取推荐面试的候选人列表"""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM resume_evaluations WHERE jd_rules_id = ? AND recommendation = 'pass'",
            (jd_rules_id,)
        )
        return [dict(row) for row in cur.fetchall()]


def update_evaluation_recommendation(eval_id: int, new_recommendation: str, note: str = ""):
    """人工干预：更新评估的推荐状态并记录操作备注"""
    with get_connection() as conn:
        cur = conn.cursor()
        strengths = "" if new_recommendation == "reject" else "人工标记为推荐"
        weaknesses = "" if new_recommendation == "pass" else f"人工标记为不推荐：{note}"
        cur.execute(
            """UPDATE resume_evaluations
               SET recommendation = ?, strengths = ?, weaknesses = ?
               WHERE id = ?""",
            (new_recommendation, strengths, weaknesses, eval_id)
        )
        logger.info(f"人工干预评估 ID={eval_id}: recommendation → {new_recommendation}, note={note}")


def delete_evaluation(eval_id: int):
    """删除单份简历评估记录"""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM resume_evaluations WHERE id = ?", (eval_id,))
        logger.info(f"已删除评估记录 ID={eval_id}")


def delete_evaluations_by_rules(jd_rules_id: int):
    """删除某规则版本下的所有评估记录"""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM resume_evaluations WHERE jd_rules_id = ?", (jd_rules_id,))
        logger.info(f"已删除 jd_rules_id={jd_rules_id} 的所有评估记录")


def delete_jd_rules(rule_id: int):
    """删除 JD 规则及其关联的评估记录和反思日志"""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM reflection_log WHERE jd_rules_id = ?", (rule_id,))
        cur.execute("DELETE FROM resume_evaluations WHERE jd_rules_id = ?", (rule_id,))
        cur.execute("DELETE FROM jd_rules WHERE id = ?", (rule_id,))
        logger.info(f"已删除 JD 规则 ID={rule_id} 及其关联数据")


# ──────────────── 反思日志 CRUD ────────────────

def save_reflection(
    jd_rules_id: int,
    batch_eval_ids: List[int],
    updated_rules: str,
    change_log: str,
) -> int:
    """保存反思日志"""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO reflection_log
               (jd_rules_id, batch_evaluations_ids, updated_rules, change_log)
               VALUES (?, ?, ?, ?)""",
            (
                jd_rules_id,
                json.dumps(batch_eval_ids),
                updated_rules,
                change_log,
            )
        )
        log_id = cur.lastrowid
        logger.info(f"反思日志已保存，ID={log_id}")
        return log_id


def list_reflections(jd_rules_id: int) -> List[Dict[str, Any]]:
    """获取某规则的反思历史"""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM reflection_log WHERE jd_rules_id = ? ORDER BY created_at DESC",
            (jd_rules_id,)
        )
        return [dict(row) for row in cur.fetchall()]


# 程序启动时自动初始化
init_db()
