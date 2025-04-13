# -*- coding: utf-8 -*-
"""
电报板块爬虫模块，包含各个板块的专用爬虫实现
"""

from chose_one_agent.modules.telegraph.sections.kanpan_scraper import KanpanScraper
from chose_one_agent.modules.telegraph.sections.company_scraper import CompanyScraper

__all__ = [
    'KanpanScraper',
    'CompanyScraper'
] 