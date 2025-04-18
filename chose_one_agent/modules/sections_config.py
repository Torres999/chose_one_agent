# -*- coding: utf-8 -*-
"""
电报板块配置文件，统一管理各板块的配置信息
"""

from typing import Dict, List, Any
from chose_one_agent.utils.constants import BASE_URLS

# 板块URL映射 - 使用常量替换硬编码URL
SECTION_URLS = {
    "看盘": BASE_URLS["telegraph"],
    "公司": BASE_URLS["telegraph"],
    "宏观": BASE_URLS["telegraph"]
}

# 电报选择器 - 基于截图中的实际DOM结构
SELECTORS = {
    # 帖子容器选择器
    "post_items": ".b-c-e6e7ea.telegraph-list",
    
    # 帖子内容盒子选择器
    "post_content_box": ".clearfix.m-b-15.f-s-16.telegraph-content-box",
    
    # 帖子时间选择器
    "post_date": ".f-l.l-h-13636.f-w-b.c-de0422.telegraph-time-box, .telegraph-time-box",
    
    # 帖子标题选择器
    "post_title": "strong",
    
    # 加载更多按钮选择器
    "load_more": "div.f-s-14.list-more-button.more-button, div.f-s-14.list-more-button.more-button:has-text('加载更多')"
}

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
        "url": SECTION_URLS.get(section, BASE_URLS["telegraph"]),
        "selectors": SELECTORS
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
    return SELECTORS.get(selector_name, "") 