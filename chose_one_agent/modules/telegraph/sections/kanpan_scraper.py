# -*- coding: utf-8 -*-
import logging
import re
from typing import List, Dict, Any

from chose_one_agent.modules.telegraph.base_telegraph_scraper import BaseTelegraphScraper

# 配置日志
logger = logging.getLogger(__name__)

class KanpanScraper(BaseTelegraphScraper):
    """看盘板块电报爬虫，专门处理看盘板块的电报内容"""

    def __init__(self, cutoff_date, headless=True, debug=False, sentiment_analyzer_type="snownlp", deepseek_api_key=None):
        """
        初始化看盘电报爬虫
        
        Args:
            cutoff_date: 截止日期，爬虫只会获取该日期到当前时间范围内的电报
            headless: 是否使用无头模式运行浏览器
            debug: 是否启用调试模式
            sentiment_analyzer_type: 情感分析器类型，可选值："snownlp"或"deepseek"
            deepseek_api_key: DeepSeek API密钥，当sentiment_analyzer_type为"deepseek"时必须提供
        """
        super().__init__(cutoff_date, headless, debug, sentiment_analyzer_type, deepseek_api_key)
        self.section = "看盘"
        
        # 看盘板块特有的选择器
        self.selectors = [
            ".kanpan-item",
            ".telescope-item",
            ".market-item",
            ".market-view-item",
            ".market-news-item",
            ".market-telegraph-item"
        ]
    
    def run(self) -> List[Dict[str, Any]]:
        """
        执行看盘板块的爬取和分析过程
        
        Returns:
            包含所有分析结果的列表
        """
        try:
            logger.info("开始运行看盘板块爬虫")
            
            # 导航到看盘板块
            if not self.navigate_to_telegraph_section(self.section):
                logger.error(f"无法导航到'{self.section}'板块")
                return []
            
            # 使用基类的通用方法爬取板块内容
            results = self.scrape_section(self.section)
            
            # 确保所有结果都标记为看盘板块
            for result in results:
                result["section"] = "看盘"
                
            logger.info(f"看盘板块爬取完成，获取到 {len(results)} 条电报")
            return results
            
        except Exception as e:
            logger.error(f"运行看盘爬虫时出错: {e}")
            return []
            
    def extract_post_info(self, element) -> Dict[str, Any]:
        """
        从看盘电报项元素中提取信息，优化为看盘版块提取

        Args:
            element: 电报项网页元素

        Returns:
            包含帖子信息的字典
        """
        result = super().extract_post_info(element)
        
        try:
            # 优化元素选择效率
            element_text = element.inner_text()
            
            # 更高效的股票代码提取
            # 同时支持多种格式: 600001.SH, 600001(SH), SH600001, 600001SH
            stock_code_patterns = [
                r'(\d{6}\.(SH|SZ|BJ|HK))',  # 600001.SH
                r'(\d{6})\((SH|SZ|BJ|HK)\)',  # 600001(SH)
                r'(SH|SZ|BJ|HK)(\d{6})',  # SH600001
                r'(\d{6})(SH|SZ|BJ|HK)',  # 600001SH
            ]
            
            # 寻找所有可能的股票代码
            result['stock_codes'] = []
            for pattern in stock_code_patterns:
                matches = re.finditer(pattern, element_text)
                for match in matches:
                    if len(match.groups()) == 2:
                        # 根据匹配组的数量和位置处理不同格式
                        if re.match(r'(SH|SZ|BJ|HK)', match.group(1)):
                            # 格式: SH600001
                            market = match.group(1)
                            code = match.group(2)
                            stock_code = f"{code}.{market}"
                        elif re.match(r'(SH|SZ|BJ|HK)', match.group(2)):
                            # 格式: 600001.SH 或 600001(SH) 或 600001SH
                            code = match.group(1)
                            market = match.group(2)
                            stock_code = f"{code}.{market}"
                        else:
                            continue
                        
                        if stock_code not in result['stock_codes']:
                            result['stock_codes'].append(stock_code)
            
            # 处理帖子中可能包含的图片和链接
            result['has_image'] = element.query_selector('img') is not None
            result['has_link'] = element.query_selector('a') is not None
            
            logger.debug(f"从看盘版块提取到股票代码: {result['stock_codes']}")
            
        except Exception as e:
            logger.error(f"解析看盘帖子信息时出错: {e}")
            result['stock_codes'] = []
        
        return result
        
    def analyze_post(self, post_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        分析帖子内容，添加到KanpanScraper以修复继承问题
        
        Args:
            post_info: 包含帖子信息的字典
            
        Returns:
            包含分析结果的字典
        """
        return super().analyze_post(post_info) 