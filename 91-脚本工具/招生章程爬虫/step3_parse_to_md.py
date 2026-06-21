"""
第3步：解析章程全文 → 生成结构化 Markdown

读取第2步下载的章程 HTML 文件，提取关键字段，
按院校模板格式生成结构化 Markdown 文件。

提取的字段包括：
  - 学校基本信息（名称、所在地、层次、类型）
  - 录取规则（分数清/专业清/专业级差）
  - 选科要求（首选/再选科目限制）
  - 单科成绩要求
  - 身体条件限制
  - 外语口试要求
  - 学费标准
  - 招生计划（在河南的投放情况）

使用方法：
    python step3_parse_to_md.py                   # 解析全部已下载章程
    python step3_parse_to_md.py --school 北京大学  # 只解析指定学校
    python step3_parse_to_md.py --sync             # 解析后同步到知识库
"""

import io
import logging
import os
import re
import sys
from datetime import datetime

from bs4 import BeautifulSoup

# 修复 Windows 控制台 GBK 编码报错
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from crawler_config import (
    CHARTERS_DIR,
    PARSED_DIR,
    KB_SCHOOL_DIR,
    LOGS_DIR,
)

# ============================================================
# 日志配置
# ============================================================
log_file = os.path.join(LOGS_DIR, f"step3_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


# ============================================================
# HTML → 纯文本
# ============================================================
def extract_text_from_html(html: str) -> str:
    """
    从 HTML 中提取纯文本内容。

    策略：
    1. 用 BeautifulSoup 找到章程正文所在的容器
    2. 去除导航、页脚等无关内容
    3. 保留段落结构
    """
    soup = BeautifulSoup(html, "lxml")

    # 移除 script/style 标签
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()

    # 尝试定位章程正文容器
    # 常见的 class/id 名：content, article, main, zszc-content, detail
    content_div = None
    for selector in [
        {"class_": "content"},
        {"class_": "article"},
        {"class_": "detail"},
        {"class_": "zszc-content"},
        {"id": "content"},
        {"id": "article"},
        {"id": "detail"},
    ]:
        content_div = soup.find("div", **selector)
        if content_div:
            break

    if content_div is None:
        # 找不到特定容器，回退到 body
        content_div = soup.find("body") or soup

    # 提取文本，保留段落结构
    paragraphs = []
    for p in content_div.find_all(["p", "div", "h1", "h2", "h3", "h4", "li"]):
        text = p.get_text(strip=True)
        if text and len(text) > 2:  # 跳过空白行
            paragraphs.append(text)

    return "\n\n".join(paragraphs)


# ============================================================
# 字段提取
# ============================================================
def extract_school_name(text: str, filename: str) -> str:
    """从文本或文件名中提取学校名称。"""
    # 优先从文本开头提取（章程通常以学校名开头）
    first_lines = text[:500]
    # 常见格式："XXX大学2026年本科招生章程"
    match = re.search(r"(.+?大学|.+?学院).*?招生章程", first_lines)
    if match:
        return match.group(1)

    # 回退：从文件名提取
    # 文件名格式：{sch_id}_{学校名称}_{info_id}.html
    parts = filename.split("_")
    if len(parts) >= 2:
        return parts[1]

    return "未知"


def extract_admission_rules(text: str) -> list[str]:
    """
    提取录取规则相关条款。

    查找关键词：
    - "分数优先" / "分数清" → 分数优先录取
    - "专业优先" / "专业清" / "志愿优先" → 专业优先录取
    - "专业级差" → 有专业级差
    - "平行志愿" → 平行志愿投档
    """
    rules = []

    # 分数优先（分数清）
    if re.search(r"分数优先|分数清", text):
        rules.append("录取规则：**分数优先**（分数清）—— 按分数从高到低依次满足专业志愿")

    # 专业优先（专业清）
    if re.search(r"专业优先|专业清|志愿优先", text):
        rules.append("录取规则：**专业优先**（专业清）—— 先录第一志愿，再录后续志愿")

    # 专业级差
    match = re.search(r"专业级差[为设]?(\d+[,\s、]*)*分", text)
    if match:
        rules.append(f"专业级差：{match.group(0)}")

    # 调档比例
    match = re.search(r"调[档挡]比例[不超过为]?\s*(\d+)%", text)
    if match:
        rules.append(f"调档比例：不超过 {match.group(1)}%")

    return rules


def extract_subject_requirements(text: str) -> list[str]:
    """
    提取选科要求。

    查找：
    - "首选科目" + 历史/物理/不限
    - "再选科目" + 具体科目
    - "选考科目" 相关内容
    """
    requirements = []

    # 新高考 3+1+2 选科要求
    # 首选科目
    if re.search(r"首选科目.*?历史|历史类.*?可[以报].*?考", text):
        requirements.append("首选科目：历史（文科可报）")
    elif re.search(r"首选科目.*?物理", text):
        requirements.append("首选科目：**仅物理**（文科不能报）⚠️")
    elif re.search(r"首选科目.*?不限|不提.*?首选.*?要求", text):
        requirements.append("首选科目：物理或历史均可")

    # 再选科目
    for subject in ["政治", "地理", "化学", "生物"]:
        if re.search(rf"再选科目.*?{subject}", text):
            requirements.append(f"再选科目要求：含 {subject}")

    # 如果没有明确的选科章节，搜索全文
    if not requirements:
        # 搜索 "3+1+2" 相关段落
        match = re.search(
            r"(?:选[考科]|高考综合改革|3\+1\+2).*?(?:\n|$)",
            text[:3000],
            re.DOTALL,
        )
        if match:
            requirements.append(f"选科相关：{match.group(0)[:200]}")

    return requirements


def extract_score_requirements(text: str) -> list[str]:
    """
    提取单科成绩要求。

    常见限制：
    - 外语 ≥ XX 分
    - 数学 ≥ XX 分
    - 语文 ≥ XX 分
    """
    reqs = []

    # 外语单科成绩
    match = re.search(
        r"(?:外语|英语)(?:单科)?(?:成绩|高考成绩)[不低于是须达到]+\s*(\d+)\s*分", text
    )
    if match:
        reqs.append(f"外语单科成绩要求：≥ {match.group(1)} 分")

    # 数学单科
    match = re.search(
        r"(?:数学)(?:单科)?(?:成绩|高考成绩)[不低于是须达到]+\s*(\d+)\s*分", text
    )
    if match:
        reqs.append(f"数学单科成绩要求：≥ {match.group(1)} 分")

    # 口语考试
    if re.search(r"外语口试|口语考试|英语口试", text):
        reqs.append("外语口试：**需要参加** ⚠️（报考外语类专业通常需要）")

    return reqs


def extract_physical_requirements(text: str) -> list[str]:
    """
    提取身体条件限制。

    常见限制：
    - 色盲/色弱限报
    - 身高要求
    - 视力要求
    """
    reqs = []

    if re.search(r"色盲|色弱", text):
        reqs.append("身体条件：色盲/色弱有限报专业（详见章程原文）")

    if re.search(r"身高.*?\d+.*?[厘c]m", text):
        match = re.search(r"身高.*?\d+.*?[厘c]m", text)
        reqs.append(f"身高要求：{match.group(0)}")

    if re.search(r"裸眼视力|矫正视力", text):
        reqs.append("视力有要求（详见章程原文）")

    return reqs


def extract_tuition(text: str) -> list[str]:
    """提取学费信息。"""
    info = []

    # 查找学费段落
    tuition_section = re.search(
        r"(?:学费|收费标准).{0,200}?(?:\n|$)",
        text[:5000],
        re.DOTALL | re.IGNORECASE,
    )
    if tuition_section:
        # 提取金额
        amounts = re.findall(r"(\d{4,6})\s*元", tuition_section.group(0))
        if amounts:
            info.append(f"学费范围：{min(amounts)} ~ {max(amounts)} 元/年")

    return info


def extract_henan_plan(text: str) -> list[str]:
    """
    提取在河南的招生信息。

    招生章程通常不会列出分省计划（分省计划在招生计划专刊中），
    但有些学校会在章程中提到。
    """
    info = []

    # 搜索 "河南" 相关段落
    henan_context = re.findall(
        r"[^。]*河南[^。]*(?:招生|计划|录取|人数)[^。]*[。]",
        text[:10000],
    )
    if henan_context:
        info.append(f"河南相关：{henan_context[0][:200]}")

    return info


# ============================================================
# Markdown 生成
# ============================================================
def generate_markdown(
    school_name: str,
    filename: str,
    text: str,
    extracted: dict,
    source_url: str = "",
) -> str:
    """
    根据院校模板格式生成 Markdown。

    参数：
        school_name: 学校名称
        filename:    源文件名
        text:        章程全文
        extracted:   提取到的结构化字段
        source_url:  章程原始 URL
    """

    # 拼接录取规则
    admission_rules = (
        "\n".join(f"- {r}" for r in extracted["admission_rules"])
        if extracted["admission_rules"]
        else "- （待从章程中手动确认）"
    )

    # 拼接选科要求
    subject_reqs = (
        "\n".join(f"- {r}" for r in extracted["subject_requirements"])
        if extracted["subject_requirements"]
        else "- （待从章程中手动确认）"
    )

    # 拼接单科要求
    score_reqs = (
        "\n".join(f"- {r}" for r in extracted["score_requirements"])
        if extracted["score_requirements"]
        else "- 无特殊单科成绩要求"
    )

    # 拼接身体条件
    physical_reqs = (
        "\n".join(f"- {r}" for r in extracted["physical_requirements"])
        if extracted["physical_requirements"]
        else "- 无特殊身体条件限制"
    )

    # 拼接学费
    tuition_info = (
        "\n".join(f"- {r}" for r in extracted["tuition"])
        if extracted["tuition"]
        else "- （待从章程中手动确认）"
    )

    md = f"""---
type: university
school_name: {school_name}
province: {extracted.get('province', '')}
city: {extracted.get('city', '')}
school_level: ""
tags: [招生章程, 2026]
source: {source_url}
updated: {datetime.now().strftime('%Y-%m-%d')}
status: unverified
---

# {school_name}

> 📄 以下信息提取自《{school_name}2026年本科招生章程》，由脚本自动提取。
> ⚠️ 自动提取可能存在遗漏或错误，填报前请核对章程原文。

---

## 录取规则

{admission_rules}

---

## 选科要求（河南 3+1+2 历史类）

{subject_reqs}

---

## 单科成绩要求

{score_reqs}

---

## 身体条件限制

{physical_reqs}

---

## 学费

{tuition_info}

---

## 章程原文关键段落

> 以下为章程中被识别为关键条款的原文，供人工复核。

"""
    # 附加章程中提取到的关键段落
    key_sections = []
    keywords = [
        "录取规则", "录取原则", "投档", "调档", "专业安排",
        "选考科目", "首选科目", "再选科目",
        "单科成绩", "外语口试", "口语",
        "身体健康", "体检", "色盲", "色弱",
        "学费", "收费标准", "住宿费",
    ]

    for line in text.split("\n"):
        line = line.strip()
        if len(line) < 10:
            continue
        for kw in keywords:
            if kw in line:
                key_sections.append(f"> {line[:300]}")
                break
        if len(key_sections) >= 30:  # 最多保留30条
            break

    md += "\n\n".join(key_sections[:30])
    md += f"\n\n---\n\n*此文件由招生章程爬虫自动生成，数据来源：[阳光高考平台]({source_url})*"
    md += "\n"

    return md


# ============================================================
# 主流程
# ============================================================
def parse_one_charter(filepath: str) -> dict | None:
    """
    解析单个章程文件。

    返回包含所有提取字段的字典，失败返回 None。
    """
    filename = os.path.basename(filepath)

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            html = f.read()
    except Exception as e:
        logger.error(f"读取文件失败 {filename}：{e}")
        return None

    # HTML → 纯文本
    text = extract_text_from_html(html)

    if not text or len(text) < 100:
        logger.warning(f"  {filename} 提取文本过短，可能解析失败")
        return None

    # 提取各字段
    school_name = extract_school_name(text, filename)

    # 尝试从文件名提取省份
    province = ""
    # 从学校名称推测省份（简单映射）
    province_keywords = {
        "北京": ["北京", "北大", "清华", "人大", "北师大", "北航", "北理工"],
        "河南": ["河南", "郑州", "郑大", "河大", "河师大"],
        "上海": ["上海", "复旦", "上交", "同济", "华东师大", "上财"],
        "湖北": ["湖北", "武汉", "武大", "华中科大", "华中师大"],
        "广东": ["广东", "广州", "中山", "暨南", "华南"],
        "江苏": ["江苏", "南京", "南大", "东南", "南师大"],
        "陕西": ["陕西", "西安", "西交", "西北"],
        "四川": ["四川", "成都", "川大", "电子科大"],
        "湖南": ["湖南", "长沙", "中南", "湖大"],
        "浙江": ["浙江", "杭州", "浙大"],
        "天津": ["天津", "南开", "天大"],
        "山东": ["山东", "济南", "山大", "中国海洋"],
    }
    for prov, keywords in province_keywords.items():
        for kw in keywords:
            if kw in school_name or kw in filename:
                province = prov
                break
        if province:
            break

    extracted = {
        "province": province,
        "city": "",
        "admission_rules": extract_admission_rules(text),
        "subject_requirements": extract_subject_requirements(text),
        "score_requirements": extract_score_requirements(text),
        "physical_requirements": extract_physical_requirements(text),
        "tuition": extract_tuition(text),
        "henan_plan": extract_henan_plan(text),
    }

    return {"school_name": school_name, "filename": filename, "text": text, "extracted": extracted}


def main(target_school: str | None = None, sync: bool = False):
    """
    主函数：解析所有已下载的章程文件。

    参数：
        target_school: 只解析指定学校（按学校名称模糊匹配）
        sync:          是否同步到知识库学校目录
    """
    logger.info("=" * 50)
    logger.info("招生章程爬虫 — 第3步：解析生成 Markdown")
    logger.info("=" * 50)

    # 获取所有已下载的章程文件
    if not os.path.exists(CHARTERS_DIR):
        logger.error(f"章程目录不存在：{CHARTERS_DIR}")
        logger.error("请先运行 step2_fetch_charters.py 下载章程。")
        return

    html_files = [f for f in os.listdir(CHARTERS_DIR) if f.endswith(".html")]
    if not html_files:
        logger.error("章程目录为空，请先运行 step2_fetch_charters.py。")
        return

    logger.info(f"共找到 {len(html_files)} 个章程文件。")

    if target_school:
        html_files = [f for f in html_files if target_school in f]
        logger.info(f"筛选「{target_school}」后剩余 {len(html_files)} 个。")

    success = 0
    fail = 0

    for i, html_file in enumerate(html_files):
        filepath = os.path.join(CHARTERS_DIR, html_file)
        logger.info(f"[{i+1}/{len(html_files)}] 解析 {html_file} ...")

        result = parse_one_charter(filepath)

        if result is None:
            fail += 1
            continue

        # 生成 Markdown
        md_content = generate_markdown(
            school_name=result["school_name"],
            filename=result["filename"],
            text=result["text"],
            extracted=result["extracted"],
            source_url=f"https://gaokao.chsi.com.cn/zsgs/zhangcheng/",
        )

        # 保存到 parsed 目录
        safe_name = result["school_name"].replace("/", "_").replace("\\", "_")
        md_filename = f"{safe_name}.md"
        md_filepath = os.path.join(PARSED_DIR, md_filename)

        with open(md_filepath, "w", encoding="utf-8") as f:
            f.write(md_content)

        logger.info(f"  ✅ → {md_filename}")
        success += 1

        # 同步到知识库
        if sync:
            kb_filepath = os.path.join(KB_SCHOOL_DIR, md_filename)
            with open(kb_filepath, "w", encoding="utf-8") as f:
                f.write(md_content)
            logger.info(f"  📂 已同步到知识库：02-学校库/{md_filename}")

    logger.info("=" * 50)
    logger.info(f"完成：解析成功 {success} 个，失败 {fail} 个。")
    logger.info(f"结构化 Markdown 保存在：{PARSED_DIR}")

    if not sync and success > 0:
        logger.info(f"💡 提示：使用 --sync 参数可自动同步到知识库 {KB_SCHOOL_DIR}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="解析章程生成结构化 Markdown")
    parser.add_argument("--school", type=str, help="只解析指定学校")
    parser.add_argument("--sync", action="store_true", help="解析后同步到知识库")
    args = parser.parse_args()

    main(target_school=args.school, sync=args.sync)