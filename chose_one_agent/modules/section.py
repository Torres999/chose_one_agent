# -*- coding: utf-8 -*-
"""
通用电报板块类，用于统一管理各板块的爬取逻辑
"""

import logging
import time
import traceback
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin

from chose_one_agent.scrapers.base_scraper import BaseScraper
from chose_one_agent.modules.sections_config import get_section_config, get_selector
from chose_one_agent.utils.config import BASE_URL
from chose_one_agent.utils.logging_utils import get_logger, log_error

# 获取日志记录器
logger = get_logger(__name__)

class Section(BaseScraper):
    """通用电报板块爬虫，处理各板块的电报内容爬取"""

    def __init__(self, section_name: str = "", cutoff_date=None, headless=True, debug=False, 
                 sentiment_analyzer_type="snownlp", deepseek_api_key=None):
        """
        初始化通用板块爬虫
        
        Args:
            section_name: 板块名称
            cutoff_date: 截止日期，爬虫只会获取该日期到当前时间范围内的电报
            headless: 是否使用无头模式运行浏览器
            debug: 是否启用调试模式
            sentiment_analyzer_type: 情感分析器类型，可选值："snownlp"或"deepseek"
            deepseek_api_key: DeepSeek API密钥，当sentiment_analyzer_type为"deepseek"时必须提供
        """
        super().__init__(cutoff_date, headless, debug, sentiment_analyzer_type, deepseek_api_key)
        
        # 设置板块名称和配置
        self.section_name = section_name
        if section_name:
            config = get_section_config(section_name)
            self.section_url = config["url"]  # 这里已经是完整URL，不需要额外拼接
            self.selectors = config["selectors"]
            
            logger.info(f"初始化板块爬虫: {section_name}")
    
    def run(self) -> List[Dict[str, Any]]:
        """
        运行板块爬虫
        
        Returns:
            List[Dict[str, Any]]: 分析结果列表
        """
        if not self.section_name:
            logger.error("未设置板块名称，无法运行")
            return []
            
        logger.info(f"开始运行{self.section_name}板块爬虫")
        
        # 导航到板块页面
        try:
            # 直接访问特定页面，确保URL格式正确
            self.navigate_to_url(self.section_url, timeout=15000)
            
            # 确保导航到正确的板块
            if not self.navigate_to_section(self.section_name):
                logger.warning(f"无法确认当前页面是{self.section_name}板块，但仍将尝试爬取内容")
        except Exception as e:
            logger.error(f"导航时出错: {e}")
            if self.debug:
                logger.error(traceback.format_exc())
            
        # 爬取板块内容
        posts = self.scrape_section(self.section_name)
        
        # 分析爬取结果
        results = []
        for post in posts:
            try:
                # 添加分析结果
                analysis = self.analyze_post(post)
                results.append({**post, "analysis": analysis})
            except Exception as e:
                logger.error(f"分析帖子时出错: {e}")
                if self.debug:
                    logger.error(traceback.format_exc())
                # 保留未分析的原始数据
                results.append(post)
        
        logger.info(f"{self.section_name}板块爬虫完成，获取了{len(results)}个帖子")
        return results 