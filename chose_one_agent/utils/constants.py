"""
常量文件，集中存储项目中使用的常量，避免硬编码
"""
from typing import Dict, Any, List, Tuple

# 网站与API相关常量
BASE_URLS = {
    "main": "https://www.x.cn",
    "telegraph": "https://www.x.cn/telegraph",
    "watch_plate": "https://www.x.cn/watch_plate"
}

# 默认截止时间(天)
DEFAULT_CUTOFF_DAYS = 1

# 日期时间格式常量
DATETIME_FORMATS = {
    "standard": "%Y-%m-%d %H:%M",
    "standard_with_seconds": "%Y-%m-%d %H:%M:%S",
    "slash_date": "%Y/%m/%d %H:%M",
    "chinese_date": "%Y年%m月%d日 %H:%M",
    "dot_date": "%Y.%m.%d %H:%M",
    "dot_date_with_seconds": "%Y.%m.%d %H:%M:%S",
    "date_only": "%Y-%m-%d",
    "time_only": "%H:%M",
    "time_with_seconds": "%H:%M:%S"
}

# 情感标签定义
SENTIMENT_LABELS: Dict[str, Tuple[float, float]] = {
    "极度积极": (0.8, 1.0),
    "积极": (0.3, 0.8),
    "中性": (-0.3, 0.3),
    "消极": (-0.8, -0.3),
    "极度消极": (-1.0, -0.8)
}

# 情感评分转换
SENTIMENT_SCORES = {
    "极度负面": 1,
    "负面": 2,
    "中性": 3,
    "正面": 4,
    "极度正面": 5
}

# 情感评分映射（整数得分到情感描述）
SENTIMENT_SCORE_LABELS = {
    0: "无评论", 
    1: "极度消极", 
    2: "消极", 
    3: "中性", 
    4: "积极", 
    5: "极度积极"
}

# 爬虫相关常量
SCRAPER_CONSTANTS = {
    "max_retries": 5,
    "default_timeout": 30000,  # 毫秒
    "short_timeout": 5000,     # 毫秒
    "page_load_wait": 2,       # 秒
    "element_wait": 1,         # 秒
    "default_headless": True,
    "viewport": {"width": 1280, "height": 800}
}

# 公共选择器
COMMON_SELECTORS = {
    "load_more": [
        "[class*='load-more']", 
        "text='加载更多'",
        "button:has-text('加载更多')",
        "[class*='more']"
    ],
    "next_page": [
        ".next-page",
        "a:has-text('下一页')",
        "[class*='pagination'] [class*='next']"
    ]
}

# 日志级别
LOG_LEVELS = {
    "DEBUG": 10,
    "INFO": 20,
    "WARNING": 30,
    "ERROR": 40,
    "CRITICAL": 50
}

# 财经术语列表
FINANCIAL_TERMS = {
    "股票", "市场", "投资", "基金", "证券", "期货", "期权", "债券", "外汇",
    "黄金", "原油", "指数", "大盘", "个股", "板块", "概念", "题材", "主力",
    "机构", "散户", "游资", "庄家", "筹码", "仓位", "建仓", "加仓", "减仓",
    "清仓", "止损", "止盈", "套利", "套现", "解套", "补仓", "抄底", "逃顶",
    "涨停", "跌停", "高开", "低开", "平开", "高走", "低走", "震荡", "盘整",
    "突破", "回调", "反弹", "反转", "趋势", "支撑", "压力", "均线", "K线",
    "成交量", "换手率", "市盈率", "市净率", "ROE", "EPS", "净利润", "营收",
    "毛利率", "净利率", "负债率", "现金流", "分红", "送转", "增发", "减持",
    "回购", "并购", "重组", "借壳", "退市", "ST", "*ST", "摘帽", "戴帽"
} 