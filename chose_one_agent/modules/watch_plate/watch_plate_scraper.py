import logging
import time
import datetime
from typing import List, Dict, Any, Tuple

from chose_one_agent.scrapers.base_scraper import BaseScraper
from chose_one_agent.utils.helpers import parse_datetime, is_before_cutoff, extract_date_time, is_in_date_range
from chose_one_agent.analyzers.sentiment_analyzer import SentimentAnalyzer

# 配置日志
logger = logging.getLogger(__name__)

class WatchPlateScraper(BaseScraper):
    """
    财经网站的盯盘爬虫类，用于抓取和分析盯盘内容
    """
    
    def __init__(self, cutoff_date: datetime.datetime, headless: bool = True):
        """
        初始化盯盘爬虫
        
        Args:
            cutoff_date: 截止日期，早于此日期的内容将被忽略
            headless: 是否使用无头模式运行浏览器
        """
        super().__init__(cutoff_date, headless)
        self.sentiment_analyzer = SentimentAnalyzer()
        
    def extract_post_info(self, post_element) -> Dict[str, Any]:
        """
        从盯盘元素中提取信息
        
        Args:
            post_element: 盯盘的DOM元素
            
        Returns:
            包含盯盘信息的字典
        """
        try:
            # 根据实际网站结构调整选择器
            # 提取标题
            title_element = post_element.query_selector(".title, .watch-plate-title")
            title = title_element.inner_text() if title_element else "无标题"
            
            # 提取日期和时间
            time_element = post_element.query_selector(".time, .watch-plate-time")
            date_time_text = time_element.inner_text() if time_element else ""
            date_str, time_str = extract_date_time(date_time_text)
            
            # 提取评论数
            comment_element = post_element.query_selector(".comment-count, .watch-plate-comment-count")
            comment_count_text = comment_element.inner_text() if comment_element else "0"
            try:
                comment_count = int(comment_count_text)
            except ValueError:
                comment_count = 0
                
            return {
                "title": title,
                "date": date_str,
                "time": time_str,
                "comment_count": comment_count,
                "element": post_element
            }
        except Exception as e:
            logger.error(f"提取盯盘信息时出错: {e}")
            return {
                "title": "错误",
                "date": "",
                "time": "",
                "comment_count": 0,
                "element": post_element
            }
    
    def get_comments(self, post_element) -> List[str]:
        """
        获取盯盘的评论
        
        Args:
            post_element: 盯盘的DOM元素
            
        Returns:
            评论内容列表
        """
        comments = []
        try:
            # 点击评论按钮
            comment_btn = post_element.query_selector(".comment-count, .watch-plate-comment-count")
            if comment_btn:
                comment_btn.click()
                self.page.wait_for_load_state("networkidle")
                
                # 等待评论加载
                time.sleep(3)
                
                # 提取评论内容
                comment_elements = self.page.query_selector_all(".comment-content, .comment-item-content")
                for element in comment_elements:
                    comment_text = element.inner_text()
                    if comment_text:
                        comments.append(comment_text)
                
                # 返回到列表页面
                self.page.go_back()
                self.page.wait_for_load_state("networkidle")
                time.sleep(1)
        except Exception as e:
            logger.error(f"获取评论时出错: {e}")
        
        return comments
    
    def analyze_post(self, post_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        分析盯盘信息，提取评论并进行情感分析
        
        Args:
            post_info: 包含盯盘信息的字典
            
        Returns:
            添加了情感分析结果的盯盘信息字典
        """
        result = {
            "title": post_info["title"],
            "date": post_info["date"],
            "time": post_info["time"]
        }
        
        # 如果有评论，获取评论并进行情感分析
        if post_info["comment_count"] > 0:
            comments = self.get_comments(post_info["element"])
            sentiment = self.sentiment_analyzer.analyze_comments(comments)
            result["sentiment"] = sentiment
        
        return result
    
    def scrape_section(self, section: str) -> List[Dict[str, Any]]:
        """
        爬取指定板块的盯盘内容
        
        Args:
            section: 板块名称
            
        Returns:
            分析结果列表
        """
        section_results = []
        reached_cutoff = False
        
        try:
            # 导航到指定板块
            self.navigate_to_section("盯盘", section)
            
            # 记录已处理的盯盘标题，避免重复处理
            processed_titles = set()
            
            # 循环加载并处理盯盘内容
            while not reached_cutoff:
                # 获取当前页面上的所有盯盘元素
                # 使用多个选择器尝试匹配不同可能的元素类名
                post_elements = self.page.query_selector_all(".watch-item, .list-item, .watch-plate-item")
                
                if not post_elements:
                    logger.warning("未找到盯盘内容元素，请检查选择器是否正确")
                    break
                
                for post_element in post_elements:
                    # 提取盯盘信息
                    post_info = self.extract_post_info(post_element)
                    
                    # 检查是否已处理过该盯盘内容
                    if post_info["title"] in processed_titles:
                        continue
                    
                    processed_titles.add(post_info["title"])
                    
                    # 解析日期时间
                    if post_info["date"] and post_info["time"]:
                        post_datetime = parse_datetime(post_info["date"], post_info["time"])
                        
                        # 检查日期是否在截止日期和当前时间范围内
                        if not is_in_date_range(post_datetime, self.cutoff_date):
                            logger.info(f"帖子日期 {post_info['date']} {post_info['time']} 早于截止日期 {self.cutoff_date}，跳过")
                            # 如果帖子时间早于截止日期，则标记已达到截止日期，不再继续爬取
                            if post_datetime < self.cutoff_date:
                                logger.info("已找到早于截止日期的帖子，停止爬取")
                                reached_cutoff = True
                                break
                            continue
                        
                        # 分析盯盘内容
                        result = self.analyze_post(post_info)
                        section_results.append(result)
                        
                        logger.info(f"已处理盯盘：{post_info['title']}")
                
                # 如果已达到截止日期，停止加载更多
                if reached_cutoff:
                    break
                
                # 尝试加载更多
                if not self.load_more_content():
                    logger.info("没有更多盯盘内容可加载")
                    break
        
        except Exception as e:
            logger.error(f"爬取盯盘'{section}'板块时出错: {e}")
        
        return section_results
    
    def run(self) -> List[Dict[str, Any]]:
        """
        执行爬取和分析过程
        
        Returns:
            包含所有分析结果的列表
        """
        try:
            # 导航到网站
            self.navigate_to_site()
            
            # 盯盘的具体板块需要根据实际网站结构调整
            logger.info("开始爬取盯盘内容...")
            
            # 找到网站上可能的盯盘板块名称，尝试多个可能的板块名
            possible_sections = ["主页", "要闻", "快讯"]
            
            for section in possible_sections:
                try:
                    section_results = self.scrape_section(section)
                    if section_results:
                        self.results.extend(section_results)
                        logger.info(f"成功从'{section}'板块爬取了{len(section_results)}条内容")
                except Exception as e:
                    logger.warning(f"爬取'{section}'板块时出错: {e}")
            
            return self.results
            
        except Exception as e:
            logger.error(f"运行盯盘爬虫时出错: {e}")
            return self.results 