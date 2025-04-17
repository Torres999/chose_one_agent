# -*- coding: utf-8 -*-
"""
电报板块配置文件，统一管理各板块的配置信息
"""

from typing import Dict, List, Any
from urllib.parse import urljoin
from chose_one_agent.utils.config import BASE_URL

# 板块URL映射
SECTION_URLS = {
    "看盘": urljoin(BASE_URL, "/telegraph/kanpan"),
    "公司": urljoin(BASE_URL, "/telegraph/company"),
    "宏观": urljoin(BASE_URL, "/telegraph/macro")
}

# 板块选择器配置
SECTION_SELECTORS = {
    "看盘": [
        ".kanpan-item",
        ".telescope-item",
        ".content-item",
        ".view-item",
        ".news-item",
        ".telegraph-kanpan-item"
    ],
    "公司": [
        ".company-item",
        ".business-item",
        ".firm-item",
        ".enterprise-item",
        ".corporation-item"
    ],
    "宏观": [
        ".macro-item",
        ".economic-item",
        ".economy-item"
    ]
}

# 通用选择器
COMMON_SELECTORS = {
    "post_items": ".telegraph-item, .telegraph-list .item, div:has(span.time), div:has(time)",
    "post_title": "h3, .title, .post-title, .headline, strong",
    "post_date": "time, .time, .date, .timestamp, span.post-time",
    "post_content": ".content, .text, .post-content, .body, .message",
    "comments": ".comment-item, .reply-item, .comment, .reply, .response",
    "load_more": "button:has-text('加载更多'), .load-more, .more-btn, button.more"
}

# 兼容性选择器 - 从scraper.py整合而来
LEGACY_SELECTORS = {
    "post_items": "div.tl_article_content > article, .topic-item, article.article-list-item",
    "post_title": "h1, h2 a, h3 a, h2.title span",
    "post_date": "time, .meta-item.meta-item-time, .time",
    "post_content": "article > div",
    "load_more": "div.load-more, .list-more",
    "comments": "div.comment-item, .evaluate-item, .comment-text"
}

# 合并选择器，确保向后兼容性
MERGED_SELECTORS = {}
for key in set(COMMON_SELECTORS.keys()).union(set(LEGACY_SELECTORS.keys())):
    common_selector = COMMON_SELECTORS.get(key, "")
    legacy_selector = LEGACY_SELECTORS.get(key, "")
    
    if common_selector and legacy_selector:
        # 合并两个选择器，去除重复部分
        all_selectors = set(common_selector.split(", ")) | set(legacy_selector.split(", "))
        MERGED_SELECTORS[key] = ", ".join(all_selectors)
    else:
        # 使用非空的选择器
        MERGED_SELECTORS[key] = common_selector or legacy_selector

def get_section_config(section: str) -> Dict[str, Any]:
    """
    获取特定板块的配置
    
    Args:
        section: 板块名称
        
    Returns:
        Dict: 包含板块配置的字典
    """
    return {
        "name": section,
        "url": SECTION_URLS.get(section, urljoin(BASE_URL, "/telegraph")),
        "selectors": SECTION_SELECTORS.get(section, []),
        "common_selectors": MERGED_SELECTORS
    }

def get_all_sections() -> List[str]:
    """
    获取所有支持的板块名称
    
    Returns:
        List[str]: 板块名称列表
    """
    return list(SECTION_URLS.keys())

def get_selector(selector_name: str) -> str:
    """
    获取指定的CSS选择器
    
    Args:
        selector_name: 选择器名称
        
    Returns:
        str: 对应的CSS选择器字符串
    """
    return MERGED_SELECTORS.get(selector_name, "") 