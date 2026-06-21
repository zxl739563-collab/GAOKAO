# 招生章程爬虫工具

## 用途

从阳光高考平台（gaokao.chsi.com.cn）自动获取高校招生章程，并解析为结构化数据，补充到高考报考知识库。

## 目录说明

```
招生章程爬虫/
├── README.md               # 本文件
├── requirements.txt        # Python 依赖
├── crawler_config.py       # 配置文件
├── step1_list_schools.py   # 第1步：获取学校列表
├── step2_fetch_charters.py # 第2步：获取章程全文
├── step3_parse_to_md.py    # 第3步：解析并生成 Markdown
├── output/                 # 爬取原始数据
│   ├── school_list.csv     # 学校列表（ID + 名称）
│   └── charters/           # 各校章程原文（HTML）
├── parsed/                 # 解析后的结构化 Markdown
└── logs/                   # 运行日志
```

## 环境要求

- Windows 10/11
- Python 3.10+
- Chrome 浏览器（必须安装）

## 安装

```powershell
# 1. 进入工具目录
cd Gaokaoxinxi\91-脚本工具\招生章程爬虫

# 2. 创建虚拟环境（可选但推荐）
python -m venv venv
venv\Scripts\activate

# 3. 安装依赖
pip install -r requirements.txt
```

首次运行时，`webdriver-manager` 会自动下载匹配你 Chrome 版本的 ChromeDriver，无需手动配置。

## 使用方法

### 完整流程（三步）

```powershell
# 第1步：获取全国高校列表（约5-10分钟）
python step1_list_schools.py

# 第2步：获取章程全文（耗时较长，建议先小批量测试）
python step2_fetch_charters.py --limit 5    # 先试5所
python step2_fetch_charters.py --all         # 全部获取

# 第3步：解析为结构化 Markdown
python step3_parse_to_md.py
```

### 只爬河南相关学校

```powershell
# 第2步支持按省份筛选
python step2_fetch_charters.py --province 河南
```

## 输出

- 原始章程 HTML → `output/charters/`
- 结构化 Markdown → `parsed/`（可复制到 `02-学校库/`）
- 运行日志 → `logs/`

## 注意事项

- 爬取间隔默认 3 秒/请求，请勿调太快以免被封 IP
- 全量爬取约 2800 所学校，预计耗时 1-2 小时
- 如果中途中断，重新运行会自动跳过已下载的学校