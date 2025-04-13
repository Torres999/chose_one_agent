# -*- coding: utf-8 -*-
"""
电报爬虫模块
"""

from chose_one_agent.modules.telegraph.telegraph_scraper import TelegraphScraper
from chose_one_agent.modules.telegraph.base_telegraph_scraper import BaseTelegraphScraper
from chose_one_agent.modules.telegraph.post_extractor import PostExtractor

__all__ = ['TelegraphScraper', 'BaseTelegraphScraper', 'PostExtractor']
