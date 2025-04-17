from chose_one_agent.scrapers.base_scraper import BaseScraper

# TelegraphScraper 现在是 BaseScraper 的一部分
# 为了保持兼容性，创建一个类型别名
TelegraphScraper = BaseScraper

__all__ = ["TelegraphScraper", "BaseScraper"]
