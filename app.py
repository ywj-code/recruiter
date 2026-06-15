"""
智能简历筛选多智能体系统 - Streamlit 主程序

三页面交互：
1. JD 分析页：上传 JD → 生成规则 → 确认/调整 → 保存
2. 简历评估总表页：批量上传简历 → 逐份评估 → 总表展示 → 反思进化
3. 简历详情与面试准备页：查看详情 → 生成面试材料
"""

import streamlit as st
import json
import logging
import time
from datetime import datetime
from io import BytesIO

# 页面配置
st.set_page_config(
    page_title="智能简历筛选系统",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 初始化日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ──────────── 初始化 Session State ────────────

def init_session_state():
    """初始化所有 session_state 变量"""
    defaults = {
        "page": "page1",                    # 当前页面: page1/page2/page3
        "current_rules_id": None,           # 当前使用的规则 ID
        "jd_text": "",                      # JD 文本
        "initial_screening": {},            # 初筛规则
        "secondary_screening": {},          # 复筛规则
        "evaluated_results": [],            # 批量评估结果列表
        "selected_eval_id": None,            # 选中的评估记录 ID
        "selected_eval_data": None,          # 选中的评估记录数据
        "followup_questions": [],            # 追问问题列表
        "test_questions": {},               # 试题本
        "batch_eval_complete": False,        # 批量评估是否完成
        "editing_rules": False,             # 是否正在编辑规则
    }
    for key, default in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default


# ──────────── 导入业务模块 ────────────

@st.cache_resource
def load_modules():
    """加载所有业务模块（缓存避免重复导入）"""
    from storage.db import (
        save_jd_rules, update_jd_rules, get_jd_rules, get_latest_jd_rules,
        list_jd_rules, save_evaluation, get_evaluation, list_evaluations_by_rules,
        save_reflection, list_reflections, update_evaluation_recommendation,
        delete_evaluation, delete_evaluations_by_rules, delete_jd_rules,
    )
    from graph.workflow import evaluate_single_resume
    from agents.jd_agent import generate_rules
    from agents.reflection import reflect_and_evolve
    from agents.followup import generate_followup_questions
    from agents.question_gen import generate_questions
    from utils.file_parser import parse_file
    from utils.llm_client import get_llm_client

    return {
        "save_jd_rules": save_jd_rules,
        "update_jd_rules": update_jd_rules,
        "get_jd_rules": get_jd_rules,
        "get_latest_jd_rules": get_latest_jd_rules,
        "list_jd_rules": list_jd_rules,
        "save_evaluation": save_evaluation,
        "get_evaluation": get_evaluation,
        "list_evaluations_by_rules": list_evaluations_by_rules,
        "save_reflection": save_reflection,
        "list_reflections": list_reflections,
        "update_evaluation_recommendation": update_evaluation_recommendation,
        "delete_evaluation": delete_evaluation,
        "delete_evaluations_by_rules": delete_evaluations_by_rules,
        "delete_jd_rules": delete_jd_rules,
        "evaluate_single_resume": evaluate_single_resume,
        "generate_rules": generate_rules,
        "reflect_and_evolve": reflect_and_evolve,
        "generate_followup_questions": generate_followup_questions,
        "generate_questions": generate_questions,
        "parse_file": parse_file,
        "get_llm_client": get_llm_client,
    }


# ──────────── 侧边栏 ────────────

def render_sidebar():
    """渲染全局侧边栏"""
    with st.sidebar:
        st.title("🎯 智能简历筛选系统")

        # LLM 状态检查
        st.subheader("🔌 系统状态")
        try:
            mods = load_modules()
            llm = mods["get_llm_client"]()
            st.success(f"✅ LLM: {llm.provider.upper()} ({llm.model})")
        except Exception as e:
            st.error(f"❌ LLM 未就绪: {e}")

        st.divider()

        # 导航
        st.subheader("📋 导航")
        page_names = {
            "page1": "📝 步骤一：JD 分析",
            "page2": "📊 步骤二：简历评估",
            "page3": "🔍 步骤三：简历详情",
        }
        current = st.session_state.get("page", "page1")
        for key, label in page_names.items():
            if st.button(label, key=f"nav_{key}", type="primary" if current == key else "secondary", width='stretch'):
                st.session_state["page"] = key
                st.rerun()

        st.divider()

        # 当前规则信息
        rule_id = st.session_state.get("current_rules_id")
        if rule_id:
            st.info(f"📌 当前规则版本 ID: {rule_id}")
        else:
            st.warning("⚠️ 请先在步骤一中创建规则")

        st.divider()
        st.caption("AI Resume Screening System")


# ──────────── 通用工具函数 ────────────

# ──────────── 页面 1: JD 分析 ────────────

def render_page1():
    """JD 分析页面"""
    st.title("📝 步骤一：JD 分析与规则生成")
    st.markdown("上传职位描述（JD），系统将自动生成初筛和复筛规则。您可以审核并调整规则后进入下一步。")

    mods = load_modules()

    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("📄 输入 JD")
        input_method = st.radio("选择输入方式", ["上传文件", "手动输入"], horizontal=True, key="jd_input_method")

        jd_text = ""
        if input_method == "上传文件":
            jd_file = st.file_uploader("上传 JD 文件", type=["pdf", "docx", "txt"], key="jd_upload")
            if jd_file:
                try:
                    jd_text = mods["parse_file"](jd_file.read(), jd_file.name)
                    st.text_area("JD 文本预览", jd_text, height=200, key="jd_preview", disabled=True)
                except Exception as e:
                    st.error(f"文件解析失败: {e}")
        else:
            jd_text = st.text_area("请输入 JD 文本", height=200, key="jd_text_input",
                                   value=st.session_state.get("jd_text", ""))

        if jd_text:
            st.session_state["jd_text"] = jd_text

        if st.button("🔍 分析 JD 并生成规则", type="primary", width='stretch',
                     disabled=not jd_text):
            with st.spinner("正在分析 JD，生成筛选规则..."):
                rules = mods["generate_rules"](jd_text)
                st.session_state["initial_screening"] = rules.get("initial_screening", {})
                st.session_state["secondary_screening"] = rules.get("secondary_screening", {})
                st.session_state["editing_rules"] = False
                st.success("✅ 规则生成完成！请在右侧审核。")
                st.rerun()

    with col2:
        st.subheader("⚙️ 筛选规则")

        init = st.session_state.get("initial_screening", {})
        sec = st.session_state.get("secondary_screening", {})
        editing = st.session_state.get("editing_rules", False)

        has_rules = bool(init and sec)

        if not has_rules:
            st.info("👈 请先输入 JD 并点击「分析 JD 并生成规则」")
        elif not editing:
            # 展示模式
            st.markdown("#### 🚫 初筛规则（硬性条件）")
            must_have = init.get("must_have", [])
            for i, item in enumerate(must_have, 1):
                st.markdown(f"{i}. ✅ {item}")
            st.caption(init.get("description", ""))

            st.markdown("#### 📊 复筛规则（评分维度）")
            dims = sec.get("dimensions", [])
            if dims:
                dim_data = []
                for d in dims:
                    dim_data.append({
                        "维度": d.get("name", ""),
                        "权重": f"{d.get('weight', 0)}%",
                        "评分标准": d.get("criteria", "")[:60] + "..."
                    })
                st.dataframe(dim_data, width='stretch', hide_index=True)
            st.caption(sec.get("scoring_guide", ""))

            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("✏️ 编辑规则", width='stretch'):
                    st.session_state["editing_rules"] = True
                    st.rerun()
            with col_b:
                if st.button("✅ 确认规则并保存", type="primary", width='stretch'):
                    init_json = json.dumps(init, ensure_ascii=False)
                    sec_json = json.dumps(sec, ensure_ascii=False)
                    rule_id = mods["save_jd_rules"](
                        jd_text=st.session_state.get("jd_text", ""),
                        initial_screening=init_json,
                        secondary_screening=sec_json
                    )
                    st.session_state["current_rules_id"] = rule_id
                    st.success(f"✅ 规则已保存！规则 ID: {rule_id}")
                    st.info("👉 请点击左侧导航进入「步骤二：简历评估」")
        else:
            # 表单编辑模式（不展示 JSON）
            st.markdown("#### 🚫 初筛规则（硬性条件）")

            # 初始化编辑中的 must_have 列表
            if "edit_must_have" not in st.session_state:
                st.session_state["edit_must_have"] = list(init.get("must_have", []))

            # 展示每个条件并允许删除
            must_have = st.session_state["edit_must_have"]
            to_remove = []
            for i, item in enumerate(must_have):
                col_i1, col_i2 = st.columns([5, 1])
                with col_i1:
                    new_val = st.text_input(f"条件 {i + 1}", value=item, key=f"mh_{i}")
                    if new_val != item:
                        must_have[i] = new_val
                with col_i2:
                    if st.button("🗑", key=f"del_mh_{i}"):
                        to_remove.append(i)
            for idx in reversed(to_remove):
                must_have.pop(idx)

            # 添加新条件
            if st.button("➕ 添加初筛条件", key="add_mh"):
                must_have.append("")

            st.text_area(
                "条件说明（可选）",
                value=init.get("description", ""),
                key="edit_desc",
                height=60,
            )

            st.markdown("#### 📊 复筛规则（评分维度）")

            # 初始化编辑中的 dimensions 列表
            if "edit_dimensions" not in st.session_state:
                st.session_state["edit_dimensions"] = [
                    dict(d) for d in sec.get("dimensions", [])
                ]

            dims = st.session_state["edit_dimensions"]
            to_remove_dim = []
            for i, d in enumerate(dims):
                with st.container():
                    st.markdown(f"**维度 {i + 1}**")
                    col_d1, col_d2, col_d3, col_d4 = st.columns([2, 1, 4, 0.5])
                    with col_d1:
                        d["name"] = st.text_input("维度名", value=d.get("name", ""), key=f"dim_name_{i}")
                    with col_d2:
                        d["weight"] = st.number_input("权重%", value=d.get("weight", 0), min_value=0, max_value=100, key=f"dim_weight_{i}")
                    with col_d3:
                        d["criteria"] = st.text_area("评分标准", value=d.get("criteria", ""), key=f"dim_criteria_{i}", height=60, label_visibility="collapsed")
                    with col_d4:
                        if st.button("🗑", key=f"del_dim_{i}"):
                            to_remove_dim.append(i)
                    st.divider()
            for idx in reversed(to_remove_dim):
                dims.pop(idx)

            if st.button("➕ 添加维度", key="add_dim"):
                dims.append({"name": "", "weight": 0, "criteria": ""})

            scoring_guide = st.text_area(
                "评分指南",
                value=sec.get("scoring_guide", ""),
                key="edit_scoring",
                height=60,
            )

            col_a, col_b, col_c = st.columns(3)
            with col_a:
                if st.button("💾 保存编辑", type="primary", width='stretch'):
                    # 检查权重和
                    total_w = sum(d.get("weight", 0) for d in dims)
                    if total_w != 100:
                        st.error(f"维度权重总和为 {total_w}%，必须等于 100%")
                    else:
                        new_init = {
                            "must_have": must_have,
                            "description": st.session_state.get("edit_desc", ""),
                        }
                        new_sec = {
                            "dimensions": dims,
                            "scoring_guide": scoring_guide,
                        }
                        st.session_state["initial_screening"] = new_init
                        st.session_state["secondary_screening"] = new_sec
                        st.session_state["editing_rules"] = False
                        # 清理编辑状态
                        for k in ["edit_must_have", "edit_dimensions"]:
                            if k in st.session_state:
                                del st.session_state[k]
                        st.success("规则已更新！")
                        st.rerun()
            with col_b:
                if st.button("↩️ 放弃编辑", width='stretch'):
                    st.session_state["editing_rules"] = False
                    for k in ["edit_must_have", "edit_dimensions"]:
                        if k in st.session_state:
                            del st.session_state[k]
                    st.rerun()
            with col_c:
                if st.button("🔄 重新生成", width='stretch'):
                    with st.spinner("重新生成规则..."):
                        from agents.jd_agent import generate_rules
                        rules = generate_rules(st.session_state.get("jd_text", ""))
                        st.session_state["initial_screening"] = rules.get("initial_screening", {})
                        st.session_state["secondary_screening"] = rules.get("secondary_screening", {})
                        st.session_state["edit_must_have"] = list(rules.get("initial_screening", {}).get("must_have", []))
                        st.session_state["edit_dimensions"] = [dict(d) for d in rules.get("secondary_screening", {}).get("dimensions", [])]
                        st.rerun()

    # 历史规则版本
    st.divider()
    st.subheader("📚 历史规则版本")
    rules_list = mods["list_jd_rules"]()
    if rules_list:
        for r in rules_list:
            col_a, col_b, col_c = st.columns([3, 1, 0.5])
            with col_a:
                jd_preview = r["jd_text"][:100] + "..." if len(r["jd_text"]) > 100 else r["jd_text"]
                st.markdown(f"**ID {r['id']}** (v{r['version']}) - {jd_preview}")
            with col_b:
                if st.button("📌 选用", key=f"use_{r['id']}"):
                    rule_data = mods["get_jd_rules"](r["id"])
                    if rule_data:
                        st.session_state["current_rules_id"] = r["id"]
                        st.session_state["initial_screening"] = json.loads(rule_data["initial_screening"])
                        st.session_state["secondary_screening"] = json.loads(rule_data["secondary_screening"])
                        st.session_state["jd_text"] = rule_data["jd_text"]
                        st.success(f"已选用规则 ID {r['id']}")
                        st.rerun()
            with col_c:
                    if st.button("🗑", key=f"del_rule_{r['id']}"):
                        # 如果当前选中的就是这条规则，清除选中状态
                        if st.session_state.get("current_rules_id") == r["id"]:
                            st.session_state["current_rules_id"] = None
                            st.session_state["initial_screening"] = {}
                            st.session_state["secondary_screening"] = {}
                        mods["delete_jd_rules"](r["id"])
                        st.rerun()
    else:
        st.info("暂无历史规则")


# ──────────── 页面 2: 简历评估总表 ────────────

def render_page2():
    """简历评估总表页面"""
    st.title("📊 步骤二：简历批量评估")

    rule_id = st.session_state.get("current_rules_id")
    if not rule_id:
        st.warning("⚠️ 请先在「步骤一：JD 分析」中创建或选用规则")
        if st.button("👉 前往步骤一"):
            st.session_state["page"] = "page1"
            st.rerun()
        return

    mods = load_modules()
    rule_data = mods["get_jd_rules"](rule_id)
    if not rule_data:
        st.error("规则数据不存在")
        return

    init_rule = json.loads(rule_data["initial_screening"])
    sec_rule = json.loads(rule_data["secondary_screening"])

    st.markdown(f"**当前规则**: ID {rule_id} (v{rule_data['version']})")
    with st.expander("📋 查看当前规则详情"):
        st.markdown("**🚫 初筛规则（硬性条件）**")
        must_have = init_rule.get("must_have", [])
        if must_have:
            for item in must_have:
                st.markdown(f"- ✅ {item}")
        else:
            st.caption("无硬性条件，所有候选人进入复筛")
        st.caption(init_rule.get("description", ""))

        st.markdown("**📊 复筛规则（评分维度）**")
        dims = sec_rule.get("dimensions", [])
        if dims:
            dim_data = []
            for d in dims:
                dim_data.append({
                    "维度": d.get("name", ""),
                    "权重": f"{d.get('weight', 0)}%",
                    "评分标准": d.get("criteria", ""),
                })
            st.dataframe(dim_data, width='stretch', hide_index=True)
        st.caption(sec_rule.get("scoring_guide", ""))

    # 上传简历
    st.subheader("📤 上传简历")
    resume_files = st.file_uploader(
        "支持 PDF / DOCX / TXT 格式，可批量上传",
        type=["pdf", "docx", "txt"],
        accept_multiple_files=True,
        key="resume_upload"
    )

    # 已评估结果表格
    existing_results = mods["list_evaluations_by_rules"](rule_id)
    if existing_results:
        st.subheader(f"📋 已评估简历 ({len(existing_results)} 份)")

        # 构建表格数据
        table_data = []
        for r in existing_results:
            rec = r["recommendation"]
            rec_icon = {"pass": "🟢 推荐", "consider": "🟡 待定", "reject": "🔴 不推荐"}.get(rec, rec)
            table_data.append({
                "ID": r["id"],
                "姓名": r["resume_name"],
                "匹配分": r["final_score"],
                "推荐状态": rec_icon,
                "亮点/拒因": (r["strengths"] if rec == "pass" else r["weaknesses"])[:60] + "..." if (
                    r["strengths"] or r["weaknesses"]) else "-",
                "评估时间": r["evaluated_at"][:16] if r["evaluated_at"] else "",
            })

        # 可点击表格
        for idx, row in enumerate(table_data):
            cols = st.columns([0.5, 1.5, 0.8, 1, 3, 1.5, 1, 0.6])
            with cols[0]:
                st.write(row["ID"])
            with cols[1]:
                st.write(row["姓名"])
            with cols[2]:
                score_color = "green" if row["匹配分"] >= 80 else "orange" if row["匹配分"] >= 60 else "red"
                st.markdown(f":{score_color}[**{row['匹配分']}**]")
            with cols[3]:
                st.write(row["推荐状态"])
            with cols[4]:
                st.write(row["亮点/拒因"])
            with cols[5]:
                st.write(row["评估时间"])
            with cols[6]:
                if st.button("🔍 详情", key=f"detail_{row['ID']}"):
                    st.session_state["selected_eval_id"] = row["ID"]
                    st.session_state["page"] = "page3"
                    st.rerun()
            with cols[7]:
                if st.button("🗑", key=f"del_eval_{row['ID']}"):
                    mods["delete_evaluation"](row["ID"])
                    st.rerun()

    # 上传并评估
    if resume_files:
        col_a, col_b = st.columns([1, 3])
        with col_a:
            if st.button("🚀 开始评估所有简历", type="primary", width='stretch'):
                st.session_state["batch_eval_complete"] = False
                total = len(resume_files)
                progress_bar = st.progress(0, text="准备评估...")
                status_text = st.empty()

                from concurrent.futures import ThreadPoolExecutor, as_completed

                MAX_PARALLEL = 12
                status_text.text(f"正在评估 {total} 份简历...")

                # 先读取所有文件字节（st.file_uploader 对象非线程安全）
                file_data = [(file.name, file.read()) for file in resume_files]

                def evaluate_one(idx, filename, filebytes):
                    try:
                        resume_text = mods["parse_file"](filebytes, filename)
                        state = mods["evaluate_single_resume"](
                            resume_text=resume_text,
                            resume_name=filename,
                            jd_rules_id=rule_id,
                            initial_screening=init_rule,
                            secondary_screening=sec_rule,
                        )
                        eval_record = {
                            "jd_rules_id": rule_id,
                            "resume_name": filename,
                            "resume_text": resume_text,
                            "resume_json": json.dumps(state.get("resume_json", {}), ensure_ascii=False),
                            "initial_pass": state.get("initial_pass", True),
                            "initial_reason": state.get("initial_reason", ""),
                            "final_score": state.get("final_score", 0),
                            "recommendation": state.get("recommendation", "consider"),
                            "strengths": state.get("strengths", ""),
                            "weaknesses": state.get("weaknesses", ""),
                            "ratings_detail": [
                                {**r, "_used": (i + 1) in (state.get("used_ratings") or [])}
                                for i, r in enumerate(state.get("ratings_list", []))
                            ],
                        }
                        mods["save_evaluation"](eval_record)
                        return idx, state
                    except Exception as e:
                        return idx, None, filename, str(e)

                results = [None] * total
                errors = []

                with ThreadPoolExecutor(max_workers=MAX_PARALLEL) as executor:
                    futures = {
                        executor.submit(evaluate_one, i, fn, fb): i
                        for i, (fn, fb) in enumerate(file_data)
                    }
                    completed = 0
                    for future in as_completed(futures):
                        try:
                            result = future.result()
                            idx = result[0]
                            if result[1] is not None:
                                results[idx] = result[1]
                            else:
                                errors.append((result[2], result[3]))
                        except Exception as e:
                            errors.append(("unknown", str(e)))
                        completed += 1
                        progress_bar.progress(completed / total, text=f"评估中 {completed}/{total}")

                progress_bar.progress(1.0, text="评估完成！")
                result_count = sum(1 for r in results if r is not None)
                status_text.text(f"✅ 评估完成！成功 {result_count}/{total} 份简历")
                if errors:
                    for fname, err in errors:
                        st.error(f"❌ {fname} 评估失败: {err}")
                st.session_state["evaluated_results"] = [r for r in results if r is not None]
                st.session_state["batch_eval_complete"] = True
                time.sleep(1)
                st.rerun()

        with col_b:
            if resume_files:
                st.caption(f"已选择 {len(resume_files)} 个文件，点击按钮开始评估")

    # 反思与规则进化
    st.divider()
    st.subheader("🧠 反思与规则进化")

    existing = mods["list_evaluations_by_rules"](rule_id)
    can_reflect = len(existing) >= 3

    if not can_reflect:
        st.info(f"需要至少 3 份评估结果才能触发反思（当前: {len(existing)} 份）")

    col_r1, col_r2 = st.columns([1, 3])
    with col_r1:
        if st.button("🔄 反思并更新规则", type="secondary",
                     disabled=not can_reflect, width='stretch'):
            with st.spinner("正在分析评估数据，优化筛选规则..."):
                current_rules = {
                    "initial_screening": init_rule,
                    "secondary_screening": sec_rule,
                }

                reflection_result = mods["reflect_and_evolve"](current_rules, existing)

                # 保存反思日志
                eval_ids = [r["id"] for r in existing]
                updated_rules_json = json.dumps({
                    "initial_screening": reflection_result.get("updated_initial_screening", init_rule),
                    "secondary_screening": reflection_result.get("updated_secondary_screening", sec_rule),
                }, ensure_ascii=False)

                mods["save_reflection"](
                    jd_rules_id=rule_id,
                    batch_eval_ids=eval_ids,
                    updated_rules=updated_rules_json,
                    change_log=reflection_result.get("change_log", ""),
                )

                # 保存新版本规则
                new_rule_id = mods["save_jd_rules"](
                    jd_text=rule_data["jd_text"],
                    initial_screening=json.dumps(reflection_result.get("updated_initial_screening", init_rule), ensure_ascii=False),
                    secondary_screening=json.dumps(reflection_result.get("updated_secondary_screening", sec_rule), ensure_ascii=False),
                )

                # 不切换当前规则，保持现有评估记录可见。新规则存为历史版本供后续选用。
                st.success(f"✅ 反思完成！新规则已保存（ID: {new_rule_id}），可在步骤一历史规则中选用")
                st.info(reflection_result.get("change_log", "规则已优化"))
                time.sleep(2)
                st.rerun()

    with col_r2:
        # 显示历史反思
        reflections = mods["list_reflections"](rule_id)
        if reflections:
            with st.expander(f"📜 反思历史 ({len(reflections)} 条)"):
                for ref in reflections:
                    st.markdown(f"**{ref['created_at'][:16] if ref['created_at'] else ''}**")
                    st.caption(ref.get("change_log", ""))
                    st.divider()

    # 统计信息
    if existing:
        st.divider()
        st.subheader("📈 评估统计")
        col_s1, col_s2, col_s3, col_s4 = st.columns(4)
        total = len(existing)
        pass_count = sum(1 for r in existing if r["recommendation"] == "pass")
        consider_count = sum(1 for r in existing if r["recommendation"] == "consider")
        reject_count = sum(1 for r in existing if r["recommendation"] == "reject")

        with col_s1:
            st.metric("总简历数", total)
        with col_s2:
            st.metric("🟢 推荐面试", pass_count)
        with col_s3:
            st.metric("🟡 待定", consider_count)
        with col_s4:
            st.metric("🔴 不推荐", reject_count)

        scores = [r["final_score"] for r in existing if r["initial_pass"]]
        if scores:
            avg_score = sum(scores) / len(scores)
            st.caption(f"通过初筛候选人平均分: {avg_score:.1f}")


# ──────────── 页面 3: 简历详情与面试准备 ────────────

def render_page3():
    """简历详情与面试准备页面"""
    st.title("🔍 步骤三：简历详情与面试准备")

    eval_id = st.session_state.get("selected_eval_id")
    if not eval_id:
        st.info("👈 请先在「步骤二：简历评估」中点击某份简历的「详情」按钮")
        return

    mods = load_modules()
    eval_data = mods["get_evaluation"](eval_id)

    if not eval_data:
        st.error("评估记录不存在")
        return

    resume_json = json.loads(eval_data.get("resume_json", "{}"))
    recommendation = eval_data["recommendation"]

    # 推荐状态标签
    rec_color = {"pass": "green", "consider": "orange", "reject": "red"}.get(recommendation, "grey")
    rec_label = {"pass": "🟢 推荐面试", "consider": "🟡 待定", "reject": "🔴 不推荐"}.get(recommendation, recommendation)

    col_info1, col_info2, col_info3 = st.columns(3)
    with col_info1:
        st.markdown(f"### {eval_data['resume_name']}")
    with col_info2:
        st.markdown(f"### 匹配分: :{rec_color}[**{eval_data['final_score']}**]")
    with col_info3:
        st.markdown(f"### 状态: :{rec_color}[{rec_label}]")

    # 简历画像（折叠）
    with st.expander("📋 简历结构化画像", expanded=False):
        profile_cols = st.columns(2)
        with profile_cols[0]:
            st.markdown(f"**姓名**: {resume_json.get('name', '-')}")
            st.markdown(f"**性别**: {resume_json.get('gender', '-')}")
            st.markdown(f"**学历**: {resume_json.get('education', '-')}")
            st.markdown(f"**毕业院校**: {resume_json.get('school', '-')}")
            st.markdown(f"**工作年限**: {resume_json.get('years_of_experience', '-')} 年")
            st.markdown(f"**当前职位**: {resume_json.get('current_position', '-')} @ {resume_json.get('current_company', '-')}")
        with profile_cols[1]:
            st.markdown(f"**语言能力**: {resume_json.get('language_ability', '-')}")

            skills = resume_json.get("skills", [])
            if skills:
                st.markdown("**技能标签**:")
                skill_tags = " ".join([f"`{s}`" for s in skills])
                st.markdown(skill_tags)

            certs = resume_json.get("certifications", [])
            if certs:
                st.markdown("**证书**:")
                for c in certs:
                    st.markdown(f"- {c}")

        st.markdown(f"**概述**: {resume_json.get('summary', '-')}")

        if resume_json.get("work_experience"):
            st.markdown("**工作经历**:")
            for we in resume_json["work_experience"]:
                st.markdown(f"- **{we.get('position', '')}** @ {we.get('company', '')} ({we.get('duration', '')})")
                st.caption(we.get("description", "")[:200])

        if resume_json.get("project_experience"):
            st.markdown("**项目经验**:")
            for pe in resume_json["project_experience"]:
                techs = ", ".join(pe.get("tech_stack", []))
                st.markdown(f"- **{pe.get('name', '')}** ({pe.get('role', '')}) - {techs}")
                st.caption(pe.get("description", "")[:200])

    # 初筛结果
    st.subheader("🚫 初筛结果")
    if eval_data["initial_pass"]:
        st.success("✅ 通过初筛")
    else:
        st.error(f"❌ 未通过初筛 - {eval_data.get('initial_reason', '')}")

    # 评分员详情
    st.subheader("📊 各评分员打分详情")

    ratings_detail_str = eval_data.get("ratings_detail", "[]")
    ratings = []
    try:
        if isinstance(ratings_detail_str, str):
            ratings = json.loads(ratings_detail_str)
        elif isinstance(ratings_detail_str, list):
            ratings = ratings_detail_str
    except (json.JSONDecodeError, TypeError):
        ratings = []

    if ratings:
        # 详细理由（_used 字段在存储时已注入；旧记录兼容：无 _used 时默认全部已采纳）
        for i, r in enumerate(ratings):
            used = r.get("_used")
            if used is None:
                used_mark = "✅ 已采纳"
            else:
                used_mark = "✅ 已采纳" if used else "⏭ 未采纳"
            with st.expander(f"{used_mark} - {r.get('scorer_name', f'评分员{i+1}')} - 总分: {r.get('score', 0)} (置信度: {r.get('confidence', '-')})"):
                dim_scores = r.get("dimension_scores", {})
                if dim_scores:
                    dim_str = " | ".join([f"{k}: {v}" for k, v in dim_scores.items()])
                    st.markdown(f"**维度分**: {dim_str}")
                st.markdown(f"**理由**: {r.get('reason', '-')}")
    else:
        if not eval_data["initial_pass"]:
            st.info("初筛未通过，未进行复筛评分")

    # 综合结论
    st.subheader("📝 综合结论")
    col_j1, col_j2 = st.columns(2)
    with col_j1:
        if eval_data.get("strengths"):
            st.success(f"**亮点**: {eval_data['strengths']}")
    with col_j2:
        if eval_data.get("weaknesses"):
            st.error(f"**不足**: {eval_data['weaknesses']}")

    # 面试准备（仅 pass 状态）
    if recommendation == "pass":
        st.divider()
        st.subheader("🎤 面试准备")

        if "followup_questions" not in st.session_state:
            st.session_state["followup_questions"] = []
        if "test_questions" not in st.session_state:
            st.session_state["test_questions"] = {}

        col_btn1, col_btn2 = st.columns(2)

        with col_btn1:
            if st.button("🔍 生成追问问题", type="primary", width='stretch'):
                with st.spinner("生成追问问题..."):
                    eval_info = {
                        "recommendation": recommendation,
                        "final_score": eval_data["final_score"],
                        "strengths": eval_data.get("strengths", ""),
                        "weaknesses": eval_data.get("weaknesses", ""),
                    }
                    questions = mods["generate_followup_questions"](resume_json, eval_info)
                    st.session_state["followup_questions"] = questions
                    st.rerun()

        with col_btn2:
            if st.button("📝 生成面试题本", type="primary", width='stretch'):
                with st.spinner("生成面试题本..."):
                    rule_data = mods["get_jd_rules"](eval_data["jd_rules_id"])
                    jd_text = rule_data["jd_text"] if rule_data else ""
                    eval_info = {
                        "recommendation": recommendation,
                        "final_score": eval_data["final_score"],
                        "strengths": eval_data.get("strengths", ""),
                        "weaknesses": eval_data.get("weaknesses", ""),
                    }
                    questions = mods["generate_questions"](resume_json, jd_text, eval_info)
                    st.session_state["test_questions"] = questions
                    st.rerun()

        # 展示追问问题
        followup_qs = st.session_state.get("followup_questions", [])
        if followup_qs:
            st.markdown("#### 🔍 追问问题")
            for i, q in enumerate(followup_qs, 1):
                with st.container():
                    st.markdown(f"**Q{i}** [{q.get('focus_area', '综合')}]：{q.get('question', '')}")
                    st.caption(f"追问目的：{q.get('purpose', '')}")
                    st.divider()

        # 展示面试题本
        test_qs = st.session_state.get("test_questions", {})
        if test_qs and test_qs.get("questions"):
            questions_list = test_qs["questions"]
            st.markdown("#### 📝 面试题本")

            # 难度分布
            breakdown = test_qs.get("difficulty_breakdown", {})
            st.caption(
                f"总预计时间：{test_qs.get('total_time', '-')} 分钟 | "
                f"简单: {breakdown.get('简单', 0)} | "
                f"中等: {breakdown.get('中等', 0)} | "
                f"困难: {breakdown.get('困难', 0)}"
            )

            for q in questions_list:
                difficulty_color = {"简单": "green", "中等": "orange", "困难": "red"}.get(q.get("difficulty", ""), "grey")
                with st.expander(f"第{q.get('number', '?')}题 [{q.get('type', '')}] :{difficulty_color}[{q.get('difficulty', '')}] - {q.get('question', '')[:80]}..."):
                    st.markdown(f"**题目**: {q.get('question', '')}")
                    st.markdown(f"**题型**: {q.get('type', '')} | **难度**: {q.get('difficulty', '')} | **预计时间**: {q.get('estimated_time', 5)} 分钟")
                    st.markdown(f"**考察要点**: {q.get('inspection_point', '')}")
                    st.markdown(f"**参考答案要点**: {q.get('reference_answer', '')}")

            # 下载按钮
            col_dl1, col_dl2 = st.columns(2)
            with col_dl1:
                json_str = json.dumps(test_qs, ensure_ascii=False, indent=2)
                st.download_button(
                    "📥 下载面试题本 (JSON)",
                    data=json_str,
                    file_name=f"面试题本_{eval_data['resume_name']}.json",
                    mime="application/json",
                )

    elif recommendation == "consider":
        st.info("💡 该候选人处于待定状态，您可以参考评估详情后手动判定。")
        col_up, col_down = st.columns(2)
        with col_up:
            if st.button("🟢 升级为推荐面试", type="primary", width='stretch'):
                mods["update_evaluation_recommendation"](eval_id, "pass", "人工升级")
                st.success("已升级为推荐")
                time.sleep(1)
                st.rerun()
        with col_down:
            with st.popover("🔴 降级为不推荐", width='stretch'):
                note = st.text_area("不推荐理由", key=f"reject_note_{eval_id}")
                if st.button("确认降级"):
                    mods["update_evaluation_recommendation"](eval_id, "reject", note or "人工降级")
                    st.success("已降级为不推荐")
                    time.sleep(1)
                    st.rerun()
    else:
        st.warning("⚠️ 该候选人不推荐面试。")


# ──────────── 主入口 ────────────

def main():
    """主程序入口"""
    init_session_state()
    render_sidebar()

    current_page = st.session_state.get("page", "page1")

    if current_page == "page1":
        render_page1()
    elif current_page == "page2":
        render_page2()
    elif current_page == "page3":
        render_page3()


if __name__ == "__main__":
    main()
