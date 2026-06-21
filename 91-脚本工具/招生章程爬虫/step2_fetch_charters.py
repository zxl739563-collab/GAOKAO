"""
第2步：获取招生章程全文

根据第1步获取的学校列表，逐一获取各校招生章程全文 HTML，
保存到 output/charters/ 目录。

技术方案：
    使用 requests + BeautifulSoup（与 step1 一致）。
    先访问学校章程列表页 → 获取章程ID → 再访问详情页 → 保存 HTML。

使用方法：
    python step2_fetch_charters.py --limit 5        # 只爬5所（测试）
    python step2_fetch_charters.py --province 河南   # 只爬河南省高校
    python step2_fetch_charters.py --all             # 全部爬取
    python step2_fetch_charters.py --resume          # 断点续传（跳过已下载的）
"""

import csv
import io
import logging
import os
import re
import sys
import time
from datetime import datetime

import requests
from bs4 import BeautifulSoup

# 修复 Windows 控制台 GBK 编码报错
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from crawler_config import (
    SCHOOL_URL_TEMPLATE,
    DETAIL_URL_TEMPLATE,
    REQUEST_DELAY,
    SCHOOL_LIST_CSV,
    CHARTERS_DIR,
    LOGS_DIR,
)

# ============================================================
# 日志配置
# ============================================================
log_file = os.path.join(LOGS_DIR, f"step2_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
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
# HTTP 请求
# ============================================================
def create_session() -> requests.Session:
    """创建带基础请求头的 HTTP 会话。"""
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/149.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
    )
    return session


# ============================================================
# 数据获取
# ============================================================
def load_school_list() -> list[dict]:
    """从 CSV 加载学校列表。"""
    if not os.path.exists(SCHOOL_LIST_CSV):
        logger.error(f"学校列表文件不存在：{SCHOOL_LIST_CSV}")
        logger.error("请先运行 step1_list_schools.py 获取学校列表。")
        sys.exit(1)

    schools = []
    with open(SCHOOL_LIST_CSV, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            schools.append(row)
    logger.info(f"已加载 {len(schools)} 所学校。")
    return schools


def get_charter_info(
    session: requests.Session, sch_id: str
) -> list[dict]:
    """
    获取某校的招生章程列表（章程ID和标题）。

    返回：
        [{"info_id": "xxx", "title": "2026年本科招生章程", "year": "2026"}, ...]
    """
    url = SCHOOL_URL_TEMPLATE.format(sch_id=sch_id)
    charters = []

    try:
        resp = session.get(url, timeout=30)
        resp.raise_for_status()
        resp.encoding = "utf-8"

        soup = BeautifulSoup(resp.text, "lxml")

        # 查找章程列表中的链接
        # 链接格式：...infoId-xxx... 或包含 "招生章程" 文字
        all_links = soup.find_all("a", href=True)
        for link in all_links:
            href = link["href"]
            if "infoId-" in href:
                info_id_match = re.search(r"infoId-(\d+)", href)
                if not info_id_match:
                    continue
                info_id = info_id_match.group(1)
                title = link.get_text(strip=True)

                # 提取年份
                year = ""
                year_match = re.search(r"20(\d{2})", title)
                if year_match:
                    year = f"20{year_match.group(1)}"

                charters.append({"info_id": info_id, "title": title, "year": year})

    except Exception as e:
        logger.warning(f"  获取学校 {sch_id} 章程列表时出错：{e}")

    return charters


def fetch_charter_detail(
    session: requests.Session, sch_id: str, info_id: str
) -> str | None:
    """
    获取章程详情页的 HTML 内容。

    返回：HTML 字符串，失败返回 None
    """
    url = DETAIL_URL_TEMPLATE.format(info_id=info_id, sch_id=sch_id)

    try:
        resp = session.get(url, timeout=30)
        resp.raise_for_status()
        resp.encoding = "utf-8"
        return resp.text
    except Exception as e:
        logger.warning(f"    获取详情页出错（infoId={info_id}）：{e}")
        return None


def save_charter(sch_id: str, school_name: str, info_id: str, html: str):
    """
    保存章程 HTML 到文件。

    文件名格式：{学校ID}_{学校名称}_{章程ID}.html
    """
    # 清理文件名中的非法字符
    safe_name = school_name.replace("/", "_").replace("\\", "_").replace(":", "_")
    filename = f"{sch_id}_{safe_name}_{info_id}.html"
    filepath = os.path.join(CHARTERS_DIR, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)

    return filepath


# ============================================================
# 主流程
# ============================================================
def main(
    limit: int | None = None,
    province: str | None = None,
    all_schools: bool = False,
    resume: bool = True,
):
    """
    主函数：获取所有目标学校的招生章程全文。
    """
    logger.info("=" * 50)
    logger.info("招生章程爬虫 -- 第2步：获取章程全文")
    logger.info("=" * 50)

    # 加载学校列表
    schools = load_school_list()

    # 按省份筛选
    if province:
        schools = [
            s for s in schools if province in s.get("province", "")
        ]
        logger.info(f"筛选省份 [{province}] 后剩余 {len(schools)} 所。")

    # 限制数量
    if limit and not all_schools:
        schools = schools[:limit]
        logger.info(f"限制数量：最多爬取 {limit} 所。")

    if not all_schools and not limit and not province:
        logger.warning("未指定 --all、--limit 或 --province，默认使用 --limit 5 测试模式。")
        schools = schools[:5]

    # 断点续传
    skipped = 0
    if resume:
        existing = set(os.listdir(CHARTERS_DIR))
        original_count = len(schools)
        schools_to_process = []
        for s in schools:
            prefix = f"{s['sch_id']}_"
            if not any(f.startswith(prefix) for f in existing):
                schools_to_process.append(s)
        skipped = original_count - len(schools_to_process)
        if skipped > 0:
            logger.info(f"断点续传：跳过 {skipped} 所已下载的学校。")
        schools = schools_to_process

    logger.info(f"即将爬取 {len(schools)} 所学校的招生章程。")
    logger.info("-" * 50)

    session = create_session()
    success_count = 0
    fail_count = 0

    try:
        for i, school in enumerate(schools):
            sch_id = school["sch_id"]
            name = school["name"]
            prov = school.get("province", "未知")

            logger.info(f"[{i+1}/{len(schools)}] {name}（{prov}，ID={sch_id}）")

            # 获取该校章程列表
            charters = get_charter_info(session, sch_id)

            if not charters:
                logger.info(f"  -> 该校无章程记录，跳过。")
                continue

            # 优先取 2026 年的章程，没有则取最新的
            target = None
            for c in charters:
                if c["year"] == "2026":
                    target = c
                    break
            if not target:
                target = charters[0]  # 取第一条

            logger.info(f"  -> 获取章程：{target['title']}（ID={target['info_id']}）")

            # 获取章程全文
            html = fetch_charter_detail(session, sch_id, target["info_id"])

            if html:
                filepath = save_charter(sch_id, name, target["info_id"], html)
                logger.info(f"  [OK] 已保存：{os.path.basename(filepath)}")
                success_count += 1
            else:
                logger.warning(f"  [FAIL] 获取失败")
                fail_count += 1

            # 请求间隔
            time.sleep(REQUEST_DELAY)

    except KeyboardInterrupt:
        logger.info("用户中断。")
    except Exception as e:
        logger.error(f"爬取过程出错：{e}")

    # 总结
    logger.info("=" * 50)
    logger.info(
        f"完成：成功 {success_count} 所，失败 {fail_count} 所，跳过 {skipped} 所。"
    )
    logger.info(f"章程文件保存在：{CHARTERS_DIR}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="获取高校招生章程全文")
    parser.add_argument("--limit", type=int, help="限制爬取学校数量")
    parser.add_argument("--province", type=str, help="只爬指定省份的高校")
    parser.add_argument("--all", action="store_true", help="爬取全部学校")
    parser.add_argument(
        "--no-resume", action="store_true", help="不跳过已下载的文件（重新下载全部）"
    )
    args = parser.parse_args()

    main(
        limit=args.limit,
        province=args.province,
        all_schools=args.all,
        resume=not args.no_resume,
    )
