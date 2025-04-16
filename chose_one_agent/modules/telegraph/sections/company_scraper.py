# -*- coding: utf-8 -*-
import logging
import re
import time
from typing import List, Dict, Any

from chose_one_agent.modules.telegraph.base_telegraph_scraper import BaseTelegraphScraper

# 配置日志
logger = logging.getLogger(__name__)

class CompanyScraper(BaseTelegraphScraper):
    """公司板块电报爬虫，专门处理公司板块的电报内容"""

    def __init__(self, cutoff_date, headless=True, debug=False, sentiment_analyzer_type="snownlp", deepseek_api_key=None):
        """
        初始化公司电报爬虫
        
        Args:
            cutoff_date: 截止日期，爬虫只会获取该日期到当前时间范围内的电报
            headless: 是否使用无头模式运行浏览器
            debug: 是否启用调试模式
            sentiment_analyzer_type: 情感分析器类型，可选值："snownlp"或"deepseek"
            deepseek_api_key: DeepSeek API密钥，当sentiment_analyzer_type为"deepseek"时必须提供
        """
        super().__init__(cutoff_date, headless, debug, sentiment_analyzer_type, deepseek_api_key)
        self.section = "公司"
        
        # 公司板块特有的选择器
        self.selectors = [
            ".company-item",
            ".company-news-item",
            ".enterprise-item",
            ".corporation-item",
            ".firm-news-item",
            ".business-telegraph-item"
        ]
    
    def run(self) -> List[Dict[str, Any]]:
        """
        运行公司板块爬虫
        
        Returns:
            List[Dict[str, Any]]: 分析结果列表
        """
        logger.info("开始运行公司板块爬虫")
        
        # 直接导航到电报页面
        try:
            # 尝试直接访问特定页面
            self.page.goto("https://www.telegraph-site.cn/telegraph", timeout=15000)
            self.page.wait_for_load_state("networkidle", timeout=10000)
            time.sleep(2)
            
            # 尝试导航到公司板块
            navigation_success = self.navigate_to_telegraph_section("公司")
            if not navigation_success:
                logger.error("无法导航到'公司'板块")
                # 即使导航失败，我们也继续尝试抓取当前页面的内容
                logger.info("尝试从当前页面抓取内容...")
        except Exception as e:
            logger.error(f"导航时出错: {e}")
            
        # 抓取板块内容
        results = self.scrape_section("公司")
        return results
            
    def extract_post_info(self, element) -> Dict[str, Any]:
        """
        从电报项元素中提取信息，针对公司板块进行优化
        
        Args:
            element: 电报项网页元素
            
        Returns:
            包含帖子信息的字典
        """
        # 首先使用基类的提取方法
        post_info = super().extract_post_info(element)
        
        # 公司板块特有的处理逻辑
        try:
            # 如果已经识别为有效帖子，则不需要额外处理
            if post_info.get("is_valid_post", False):
                return post_info
                
            # 检查是否有公司名称格式的内容（通常是公司名后跟冒号）
            company_pattern = r'([\u4e00-\u9fa5]{2,10}(公司|集团|股份|科技|控股))[:：]'
            company_match = re.search(company_pattern, element.inner_text())
            if company_match and post_info["title"] == "未知标题":
                # 如果找到公司名但还没有标题，尝试提取包含公司名的整句话作为标题
                text = element.inner_text()
                # 查找包含公司名的整句话
                sentences = text.split('\n')
                for sentence in sentences:
                    if company_match.group(1) in sentence:
                        post_info["title"] = sentence.strip()
                        post_info["is_valid_post"] = True
                        break
            
            return post_info
            
        except Exception as e:
            logger.error(f"公司板块提取帖子信息时出错: {e}")
            return post_info
            
    def analyze_post(self, post_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        分析帖子内容，添加到CompanyScraper以修复继承问题
        
        Args:
            post_info: 包含帖子信息的字典
            
        Returns:
            包含分析结果的字典
        """
        return super().analyze_post(post_info) 