"""
第1步：获取全国高校招生章程列表

从阳光高考平台分页抓取所有已公布招生章程的高校列表，
提取学校ID、学校名称、所在地，保存为 CSV。

技术方案：
    使用 requests + BeautifulSoup 直接请求页面。
    实测发现该页面无需 Selenium 即可正常访问。

使用方法：
    python step1_list_schools.py              # 全量获取
    python step1_list_schools.py --test       # 只抓第1页（测试用）
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
    LIST_URL_TEMPLATE,
    REQUEST_DELAY,
    SCHOOL_LIST_CSV,
    LOGS_DIR,
)

# ============================================================
# 日志配置
# ============================================================
log_file = os.path.join(LOGS_DIR, f"step1_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
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
    """
    创建带基础请求头的 HTTP 会话。

    为什么以前说要用 Selenium？搜索结果显示该站有瑞数反爬，
    但实测发现招生章程列表页可以直接用 requests 访问。
    可能是反爬规则仅针对特定接口（如搜索接口），列表页不受影响。
    """
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
            "Accept-Encoding": "gzip, deflate, br",
        }
    )
    return session


# ============================================================
# 页面解析
# ============================================================
def parse_school_list_page(html: str) -> list[dict]:
    """
    从列表页 HTML 中提取学校信息。

    页面结构（实际）：
        <div class="sch-item">          ← 每所学校一个容器
            <div class="sch-title">
                <a href="...schId-123.dhtml">北京大学</a>   ← 学校名称
            </div>
            <div class="info-box">
                北京 | 主管部门：教育部                         ← 所在地
            </div>
            <div class="info-box">
                本科 "双一流"建设高校
            </div>
        </div>

    返回：
        [{"sch_id": "123", "name": "北京大学", "province": "北京"}, ...]
    """
    soup = BeautifulSoup(html, "lxml")
    schools = []

    # 找到所有学校容器
    sch_items = soup.find_all("div", class_="sch-item")
    logger.info(f"  页面中找到 {len(sch_items)} 个 sch-item 容器")

    for item in sch_items:
        # --- 提取学校名称和 ID ---
        title_div = item.find("div", class_="sch-title")
        if not title_div:
            continue

        name_link = title_div.find("a")
        if not name_link:
            continue

        name = name_link.get_text(strip=True)
        href = name_link.get("href", "")

        # 从 href 中提取 schId
        # 格式：/zsgs/zhangcheng/listZszc--schId-123.dhtml
        sch_id = ""
        match = re.search(r"schId-(\d+)", href)
        if match:
            sch_id = match.group(1)

        if not name or not sch_id:
            continue

        # --- 提取所在地（省份） ---
        province = ""
        info_boxes = item.find_all("div", class_="info-box")
        for box in info_boxes:
            text = box.get_text(strip=True)
            # 第一个 info-box 通常包含 "北京 | 主管部门：..."
            # 提取 | 前面的部分作为所在地
            if "|" in text:
                province = text.split("|")[0].strip()
                # 去除特殊字符（如 ）
                province = re.sub(r"[^一-鿿]", "", province)[:10]
                break

        schools.append(
            {
                "sch_id": sch_id,
                "name": name,
                "province": province,
            }
        )

    return schools


# ============================================================
# 主流程
# ============================================================
def main(test_mode: bool = False):
    """
    主函数：获取全国高校招生章程列表。

    参数：
        test_mode: True 时只爬第1页（共100条），用于快速测试
    """
    logger.info("=" * 50)
    logger.info("招生章程爬虫 -- 第1步：获取学校列表")
    logger.info("=" * 50)

    session = create_session()
    all_schools = []
    page = 0
    start = 0

    try:
        while True:
            page += 1
            url = LIST_URL_TEMPLATE.format(start=start)
            logger.info(f"正在获取第 {page} 页（start={start}）...")

            try:
                resp = session.get(url, timeout=30)
                resp.raise_for_status()
                # 网站使用 GBK/GB2312 编码
                resp.encoding = "utf-8"
                html = resp.text
            except requests.RequestException as e:
                logger.error(f"  请求失败：{e}")
                break

            # 解析页面
            schools = parse_school_list_page(html)

            if not schools:
                logger.warning(f"  第 {page} 页未解析到学校，可能已到末尾或页面结构变化。")
                # 保存调试文件
                debug_file = os.path.join(
                    LOGS_DIR, f"debug_page_{page}_start_{start}.html"
                )
                with open(debug_file, "w", encoding="utf-8") as f:
                    f.write(html)
                logger.info(f"  页面源码已保存到 {debug_file}")
                break

            all_schools.extend(schools)
            logger.info(
                f"  第 {page} 页获取到 {len(schools)} 所学校（累计 {len(all_schools)}）"
            )

            # 测试模式：只爬一页
            if test_mode:
                logger.info("测试模式：只爬取第1页，停止。")
                break

            # 如果本页获取数 < 100，说明是最后一页
            if len(schools) < 100:
                logger.info("已到达最后一页。")
                break

            start += 100
            time.sleep(REQUEST_DELAY)

    except KeyboardInterrupt:
        logger.info("用户中断，保存已获取的数据...")
    except Exception as e:
        logger.error(f"爬取过程出错：{e}")

    # ============================================================
    # 保存结果
    # ============================================================
    if all_schools:
        # 去重（以 sch_id 为准）
        seen = set()
        unique_schools = []
        for s in all_schools:
            if s["sch_id"] not in seen:
                seen.add(s["sch_id"])
                unique_schools.append(s)

        # 写入 CSV
        with open(SCHOOL_LIST_CSV, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=["sch_id", "name", "province"])
            writer.writeheader()
            writer.writerows(unique_schools)

        logger.info(f"[OK] 共获取 {len(unique_schools)} 所高校，已保存到 {SCHOOL_LIST_CSV}")
    else:
        logger.warning("[FAIL] 未获取到任何学校数据。")
        logger.warning(
            "   可能原因：1) 网站结构已变化  2) 网络连接问题  3) 编码设置不对"
        )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="获取全国高校招生章程列表")
    parser.add_argument("--test", action="store_true", help="测试模式，只爬第1页")
    args = parser.parse_args()

    main(test_mode=args.test)
