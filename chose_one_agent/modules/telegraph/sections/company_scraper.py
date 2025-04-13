# -*- coding: utf-8 -*-
import logging
import time
import random
from typing import List, Dict, Any
import traceback

from chose_one_agent.utils.helpers import parse_datetime
from chose_one_agent.modules.telegraph.base_telegraph_scraper import BaseTelegraphScraper
from chose_one_agent.modules.telegraph.post_extractor import PostExtractor

# 配置日志
logger = logging.getLogger(__name__)

class CompanyScraper(BaseTelegraphScraper):
    """
    公司板块的电报爬虫类，用于抓取和分析公司电报内容
    """
    
    def __init__(self, cutoff_date, headless=True, debug=False):
        """
        初始化公司电报爬虫
        
        Args:
            cutoff_date: 截止日期，爬虫只会获取该日期到当前时间范围内的电报
            headless: 是否使用无头模式运行浏览器
            debug: 是否启用调试模式
        """
        super().__init__(cutoff_date, headless, debug)
        self.post_extractor = PostExtractor()
        self.section_name = "公司"
    
    def scrape_section(self) -> List[Dict[str, Any]]:
        """
        抓取公司板块的电报内容
        
        Returns:
            处理后的电报内容列表
        """
        section_results = []
        processed_titles = set()  # 用于跟踪已处理的帖子标题，避免重复
        
        try:
            load_more_attempts = 0
            max_load_attempts = 1  # 最大加载尝试次数
            consecutive_failures = 0  # 连续加载失败次数
            
            # 确保当前是正确的板块
            logger.info(f"确保当前页面是 '{self.section_name}' 板块")
            
            try:
                current_url = self.page.url
                current_content = self.page.content()
                
                if "company" not in current_url.lower() and "公司" not in current_content:
                    logger.info(f"当前页面不是公司板块，尝试导航")
                    self.navigate_to_telegraph_section(self.section_name)
                
                # 等待页面完全加载
                time.sleep(2)
                self.page.wait_for_load_state("networkidle")
            except Exception as e:
                logger.error(f"确认和导航到正确板块时出错: {e}")
            
            # 立即提取第一页数据
            logger.info("立即提取第一页数据")
            posts, reached_cutoff = self.post_extractor.extract_posts_from_page(self.page)
            
            # 判断第一页是否有符合条件的数据
            if not posts or len(posts) == 0:
                logger.warning(f"第一页未找到符合条件的数据，不再尝试加载更多")
                return section_results
                
            # 处理第一页数据    
            if posts and len(posts) > 0:
                logger.info(f"第一页发现 {len(posts)} 条帖子")
                
                for post in posts:
                    # 跳过已处理的标题相同的帖子
                    if post["title"] in processed_titles:
                        logger.info(f"跳过重复帖子: '{post['title']}'")
                        continue
                    
                    # 检查帖子日期是否早于截止日期
                    if post["date"] and post["time"] and post["date"] != "未知日期":
                        try:
                            post_date = parse_datetime(post["date"], post["time"])
                            # 如果帖子时间早于截止日期，则跳过处理
                            if post_date < self.cutoff_date:
                                logger.info(f"帖子日期 {post['date']} {post['time']} 早于截止日期 {self.cutoff_date}，跳过处理")
                                continue
                        except Exception as e:
                            logger.error(f"检查日期时出错: {e}")
                            # 如果解析失败，仍然处理该帖子
                    
                    # 把标题加入已处理集合
                    processed_titles.add(post["title"])
                    
                    # 分析帖子
                    result = self.analyze_post(post)
                    result["section"] = self.section_name  # 添加板块信息
                    
                    # 添加到结果列表
                    section_results.append(result)
                    logger.info(f"处理完成帖子: '{post['title']}', 情感: {result.get('sentiment', '未知')}")
                    logger.info(f"帖子日期: {post['date']} {post['time']}")
            
            # 如果已经找到符合条件的数据且需要继续加载更多
            while load_more_attempts < max_load_attempts and consecutive_failures < 3:
                # 尝试加载更多内容
                load_more_attempts += 1
                logger.info(f"尝试第 {load_more_attempts}/{max_load_attempts} 次加载更多内容")
                
                # 通过load_more_posts函数加载更多内容
                if not self.post_extractor.load_more_posts(self.page):
                    consecutive_failures += 1
                    logger.info(f"尝试加载更多内容失败，连续失败次数: {consecutive_failures}")
                    
                    # 随机等待一段时间后重试
                    random_wait = random.uniform(1.5, 3.0)
                    logger.info(f"随机等待 {random_wait:.1f} 秒后重试")
                    time.sleep(random_wait)
                    
                    if consecutive_failures >= 3:
                        logger.info("连续3次未能加载更多内容，结束处理")
                        break
                else:
                    # 如果成功加载更多，重置连续失败计数
                    consecutive_failures = 0
                
                # 提取当前页面的帖子
                new_posts, reached_cutoff = self.post_extractor.extract_posts_from_page(self.page)
                
                # 如果没有新的符合条件的帖子，增加失败计数
                if not new_posts or len(new_posts) == 0:
                    consecutive_failures += 1
                    logger.info(f"未找到新的符合条件的帖子，连续失败次数: {consecutive_failures}")
                    
                    # 如果已经连续3次没有找到新帖子，停止尝试
                    if consecutive_failures >= 3:
                        logger.info("连续3次未找到新的符合条件的帖子，结束处理")
                        break
                    continue
                
                # 处理新获取的帖子
                valid_posts_found = 0
                for post in new_posts:
                    # 跳过已处理的标题相同的帖子
                    if post["title"] in processed_titles:
                        continue
                    
                    # 检查帖子日期是否早于截止日期
                    if post["date"] and post["time"] and post["date"] != "未知日期":
                        try:
                            post_date = parse_datetime(post["date"], post["time"])
                            # 如果帖子时间早于截止日期，则跳过处理
                            if post_date < self.cutoff_date:
                                logger.info(f"帖子日期 {post['date']} {post['time']} 早于截止日期 {self.cutoff_date}，跳过处理")
                                continue
                        except Exception as e:
                            logger.error(f"检查日期时出错: {e}")
                            # 如果解析失败，仍然处理该帖子
                    
                    # 把标题加入已处理集合
                    processed_titles.add(post["title"])
                    valid_posts_found += 1
                    
                    # 分析帖子
                    result = self.analyze_post(post)
                    result["section"] = self.section_name  # 添加板块信息
                    
                    # 添加到结果列表
                    section_results.append(result)
                    logger.info(f"处理完成帖子: '{post['title']}', 情感: {result.get('sentiment', '未知')}")
                
                # 如果已达到截止日期且找到了足够的帖子，停止加载更多
                if reached_cutoff and len(section_results) > 0:
                    logger.info("已达到截止日期且找到了足够的帖子，停止爬取")
                    break
                
                # 如果本次没有找到任何新的有效帖子，增加连续失败计数
                if valid_posts_found == 0:
                    consecutive_failures += 1
                    logger.info(f"本次未找到新的有效帖子，连续失败次数: {consecutive_failures}")
                else:
                    # 找到了有效帖子，重置连续失败计数
                    consecutive_failures = 0
                
                # 随机等待时间，避免请求过于频繁
                random_wait = random.uniform(1.5, 3.0)
                time.sleep(random_wait)
            
            # 记录最终结果
            logger.info(f"'{self.section_name}'板块爬取完成，经过 {load_more_attempts} 次翻页尝试，获取 {len(section_results)} 条结果")

        except Exception as e:
            logger.error(f"爬取'{self.section_name}'板块时出错: {e}")
            logger.error(traceback.format_exc())

        return section_results
        
    def run(self) -> List[Dict[str, Any]]:
        """
        执行公司板块的爬取和分析过程
        
        Returns:
            包含所有分析结果的列表
        """
        try:
            # 只有当页面已初始化时才进行导航
            if self.page:
                # 导航到电报页面
                logger.info("导航到电报公司页面")
                try:
                    # 首先尝试直接导航到公司板块
                    telegraph_company_url = f"{self.base_url}/telegraph/company"
                    self.page.goto(telegraph_company_url)
                    self.page.wait_for_load_state("networkidle")
                    time.sleep(2)
                    logger.info(f"直接导航到电报公司页面URL: {telegraph_company_url}")
                except Exception as e:
                    logger.error(f"直接导航到电报公司页面失败: {e}")
                    # 如果直接导航失败，尝试从电报主页导航
                    try:
                        telegraph_url = f"{self.base_url}/telegraph"
                        self.page.goto(telegraph_url)
                        self.page.wait_for_load_state("networkidle")
                        time.sleep(2)
                        
                        # 点击公司导航
                        self.navigate_to_telegraph_section(self.section_name)
                    except Exception as e:
                        logger.error(f"从电报主页导航到公司页面失败: {e}")
                        return []
            
                # 爬取公司板块内容
                results = self.scrape_section()
                self.results.extend(results)
            else:
                logger.error("页面未初始化，无法执行爬取")
                return []
            
            return self.results
            
        except Exception as e:
            logger.error(f"运行公司电报爬虫时出错: {e}")
            logger.error(traceback.format_exc())
            return self.results 