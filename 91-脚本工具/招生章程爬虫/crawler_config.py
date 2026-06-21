"""
招生章程爬虫 —— 配置文件

修改这里的参数来控制爬虫行为。
"""

import os

# ============================================================
# 目标网站
# ============================================================

# 阳光高考平台 - 招生章程公示系统
BASE_URL = "https://gaokao.chsi.com.cn"

# 一级页面：全国高校招生章程列表（分页，每页100条）
LIST_URL_TEMPLATE = (
    BASE_URL
    + "/zsgs/zhangcheng/listVerifedZszc--method-index,lb-1,start-{start}.dhtml"
)

# 二级页面：某校的招生章程列表
SCHOOL_URL_TEMPLATE = (
    BASE_URL + "/zsgs/zhangcheng/listZszc--schId-{sch_id}.dhtml"
)

# 三级页面：章程详情页
DETAIL_URL_TEMPLATE = (
    BASE_URL
    + "/zsgs/zhangcheng/listVerifedZszc--infoId-{info_id},method-view,schId-{sch_id}.dhtml"
)

# ============================================================
# 爬取设置
# ============================================================

# 请求间隔（秒），请勿低于 2 秒，避免给服务器造成压力
REQUEST_DELAY = 3.0

# 页面加载超时（秒）
PAGE_LOAD_TIMEOUT = 30

# 是否显示浏览器窗口（调试时设 True，正式运行设 False）
SHOW_BROWSER = False

# ============================================================
# 筛选条件
# ============================================================

# 省份筛选（用于 step2）
# 留空 = 全国所有高校
# 填省份名 = 只爬该省份高校，如 "河南"
TARGET_PROVINCE = ""  # 默认空，运行时通过命令行参数覆盖

# 是否只爬取 985/211 院校
# 设为 True 可以大幅减少爬取量（从 2800 降到约 120 所）
ONLY_TOP_SCHOOLS = False

# ============================================================
# 输出路径
# ============================================================

# 当前脚本所在目录
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

# 原始数据输出
OUTPUT_DIR = os.path.join(CURRENT_DIR, "output")
SCHOOL_LIST_CSV = os.path.join(OUTPUT_DIR, "school_list.csv")
CHARTERS_DIR = os.path.join(OUTPUT_DIR, "charters")

# 解析后数据输出
PARSED_DIR = os.path.join(CURRENT_DIR, "parsed")

# 日志
LOGS_DIR = os.path.join(CURRENT_DIR, "logs")

# ============================================================
# 知识库路径（解析后数据可以自动同步到知识库）
# ============================================================

# 高考报考知识库根目录（相对路径：从脚本目录往上3层即 Gaokaoxinxi/）
KB_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))

# 学校库目录
KB_SCHOOL_DIR = os.path.join(KB_ROOT, "02-学校库")

# 原始资料目录
KB_RAW_DIR = os.path.join(KB_ROOT, "05-原始资料")

# 确保输出目录存在
for d in [OUTPUT_DIR, CHARTERS_DIR, PARSED_DIR, LOGS_DIR]:
    os.makedirs(d, exist_ok=True)