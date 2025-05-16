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

# 爬虫相关常量
SCRAPER_CONSTANTS = {
    "max_retries": 50,         # 最大尝试翻页次数，很大程度决定了爬取的帖子数量，可以终止爬取
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