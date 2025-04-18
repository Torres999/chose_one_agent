"""
基础爬虫类，供各功能模块继承使用
"""
import time
import datetime
import re
import traceback
from typing import List, Dict, Any, Optional, Tuple, Union, Callable
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright, Page, Browser, Response

from chose_one_agent.utils.config import BASE_URL
from chose_one_agent.utils.constants import SCRAPER_CONSTANTS, BASE_URLS
from chose_one_agent.utils.logging_utils import get_logger, log_error
from chose_one_agent.utils.datetime_utils import is_before_cutoff, parse_datetime
from chose_one_agent.scrapers.base_navigator import BaseNavigator

# 获取日志记录器
logger = get_logger(__name__)

class BaseScraper:
    """
    基础爬虫类，供各功能模块继承使用
    """
    
    def __init__(self, cutoff_date: datetime.datetime = None, headless: bool = True, debug: bool = False,
                 sentiment_analyzer_type: str = "snownlp", deepseek_api_key: str = None):
        """
        初始化爬虫
        
        Args:
            cutoff_date: 截止日期，早于此日期的内容将被忽略
            headless: 是否使用无头模式运行浏览器
            debug: 是否启用调试模式
            sentiment_analyzer_type: 情感分析器类型，默认为'snownlp'
            deepseek_api_key: DeepSeek API密钥（如果使用DeepSeek分析器）
        """
        self.cutoff_date = cutoff_date
        self.headless = headless
        self.debug = debug
        self.browser = None
        self.page = None
        self.context = None
        self.base_url = BASE_URL
        self.results = []
        self.navigator = None
        self.playwright = None
        self.max_retries = 3
        self.sentiment_analyzer_type = sentiment_analyzer_type
        self.deepseek_api_key = deepseek_api_key
        
        # 以下组件将在需要时初始化
        self._comment_extractor = None
        self._post_analyzer = None
        self._sentiment_analyzer = None
        self._keyword_analyzer = None
        self.section = None
        
    def __enter__(self):
        """
        上下文管理器入口，启动浏览器
        """
        self.start_browser()
        return self
            
    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        上下文管理器出口，关闭浏览器
        """
        self.close_browser()
    
    def start_browser(self):
        """启动浏览器"""
        try:
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch(headless=self.headless)
            self.context = self.browser.new_context(viewport=SCRAPER_CONSTANTS["viewport"])
            self.page = self.context.new_page()
            self.navigator = BaseNavigator(self.page, self.base_url, self.debug)
            self._init_components()
        except Exception as e:
            log_error(logger, "启动浏览器时出错", e, self.debug)
            self.close_browser()  # 确保资源释放
            raise
    
    def _init_components(self):
        """初始化组件"""
        if not self.page:
            return
            
        # 导入需要的组件
        try:
            from chose_one_agent.modules.comment_extractor import CommentExtractor
            from chose_one_agent.analyzers.sentiment_analyzer import SentimentAnalyzer
            from chose_one_agent.modules.telegraph_analyzer import TelegraphAnalyzer
            
            # 创建分析器实例
            self._post_analyzer = TelegraphAnalyzer(
                sentiment_analyzer_type=self.sentiment_analyzer_type,
                deepseek_api_key=self.deepseek_api_key,
                debug=self.debug
            )
            
            # 创建评论提取器实例并注入分析器
            self._comment_extractor = CommentExtractor(self.page, self.debug, self._post_analyzer)
            
            # 保留这些实例以便向后兼容
            self._sentiment_analyzer = SentimentAnalyzer(
                self.sentiment_analyzer_type, self.deepseek_api_key
            )
            
            # 尝试导入KeywordAnalyzer，但如果不存在不会影响主要功能
            try:
                from chose_one_agent.analyzers.keyword_analyzer import KeywordAnalyzer
                self._keyword_analyzer = KeywordAnalyzer()
            except ImportError:
                logger.warning("KeywordAnalyzer模块不存在，将不使用关键词分析功能")
                self._keyword_analyzer = None
            
        except ImportError as e:
            # 这些组件可能不是所有爬虫都需要的，记录日志但不终止程序
            logger.warning(f"初始化高级组件时出错: {e}")
            self._post_analyzer = None
            self._comment_extractor = None
            self._sentiment_analyzer = None
            self._keyword_analyzer = None
    
    def close_browser(self):
        """关闭浏览器及相关资源"""
        try:
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
            
            # 重置资源引用
            self.browser = None
            self.context = None
            self.page = None
            self.playwright = None
            self.navigator = None
            
            # 重置组件
            self._comment_extractor = None
            self._post_analyzer = None
            self._sentiment_analyzer = None
            self._keyword_analyzer = None
        except Exception as e:
            log_error(logger, "关闭浏览器时出错", e, self.debug)
    
    def set_browser(self, browser):
        """设置浏览器实例"""
        self.browser = browser
        
    def set_page(self, page):
        """设置页面实例"""
        self.page = page
        self.navigator = BaseNavigator(self.page, self.base_url, self.debug)
        self._init_components()
            
    def navigate_to_site(self) -> bool:
        """
        导航到网站首页
        
        Returns:
            bool: 是否成功导航
        """
        if not self._ensure_browser_ready():
            return False
            
        try:
            logger.info(f"正在导航到{self.base_url}...")
            return self.navigator.navigate_to_url(self.base_url)
        except Exception as e:
            log_error(logger, "导航到网站时出错", e, self.debug)
            return False
    
    def _ensure_browser_ready(self) -> bool:
        """确保浏览器已准备好"""
        if not self.page or not self.navigator:
            logger.error("浏览器未初始化，请先调用start_browser")
            return False
        return True
            
    def navigate_to_section(self, main_section: str, sub_section: Optional[str] = None) -> bool:
        """
        导航到指定板块
        
        Args:
            main_section: 主板块名称
            sub_section: 子板块名称（可选）
            
        Returns:
            bool: 是否成功导航
        """
        if not self._ensure_browser_ready() or not self.navigate_to_site():
            return False
            
        return self._navigate_to_section_internal(main_section, sub_section)
    
    def _navigate_to_section_internal(self, main_section: str, sub_section: Optional[str] = None) -> bool:
        """
        内部导航方法，实现导航到板块的具体逻辑
        
        Args:
            main_section: 主板块名称
            sub_section: 子板块名称（可选）
            
        Returns:
            bool: 是否成功导航
        """
        try:
            logger.info(f"正在导航到'{main_section}'板块...")
            
            # 尝试定位主版块的选择器
            main_selectors = [
                f"text='{main_section}'",
                f"text={main_section}",
                f"[class*='nav'] >> text={main_section}",
                f"[class*='menu'] >> text={main_section}",
                f"[class*='tab'] >> text={main_section}",
                f"a >> text={main_section}"
            ]
            
            if not self.navigator.try_multiple_selectors(main_selectors):
                logger.error(f"无法找到'{main_section}'主板块")
                return False
                
            # 如果有子板块，继续导航
            if sub_section:
                return self._navigate_to_subsection(sub_section)
                
            logger.info(f"已成功导航到'{main_section}'板块")
            return True
                
        except Exception as e:
            log_error(logger, f"导航到板块时出错", e, self.debug)
            return False
    
    def _navigate_to_subsection(self, sub_section: str) -> bool:
        """
        导航到子板块
        
        Args:
            sub_section: 子板块名称
            
        Returns:
            bool: 是否成功导航
        """
        try:
            logger.info(f"正在导航到'{sub_section}'子板块...")
            
            # 子板块选择器
            sub_selectors = [
                f"text='{sub_section}'",
                f"text={sub_section}",
                f"[class*='sub-nav'] >> text={sub_section}",
                f"[class*='tab'] >> text={sub_section}",
                f"[class*='submenu'] >> text={sub_section}",
                f"[class*='category'] >> text={sub_section}",
                f"a >> text={sub_section}"
            ]
            
            if not self.navigator.try_multiple_selectors(sub_selectors):
                logger.error(f"无法找到'{sub_section}'子板块")
                return False
                
            logger.info(f"已成功导航到'{sub_section}'子板块")
            return True
                
        except Exception as e:
            log_error(logger, f"导航到子板块时出错", e, self.debug)
            return False
    
    def load_more_content(self, max_attempts: int = 3) -> bool:
        """
        加载更多内容
        
        Args:
            max_attempts: 最大尝试次数
            
        Returns:
            bool: 是否成功加载更多内容
        """
        if not self._ensure_browser_ready():
            return False
            
        return self.navigator.load_more_content(max_attempts)
    
    # === 添加 TelegraphScraper 的功能 ===
    
    def navigate_to_telegraph_section(self, section_name: str) -> bool:
        """导航到Telegraph的特定版块"""
        if not self.navigator:
            logger.error("未设置导航工具，无法导航")
            return False
            
        return self.navigator.navigate_to_telegraph_section(section_name)
    
    def verify_section_content(self, section_name: str) -> bool:
        """验证当前页面是否为指定版块内容"""
        if not self.navigator:
            return False
            
        return self.navigator.verify_section_content(section_name)
    
    def get_comments(self, post_element, max_comments: int = 50) -> List[str]:
        """从帖子元素中提取评论"""
        if self._comment_extractor:
            return self._comment_extractor.extract_comments(post_element, max_comments)
        return []
    
    def extract_post_info(self, post_element) -> Dict[str, Any]:
        """从帖子元素中提取信息"""
        # 导入选择器
        try:
            from chose_one_agent.modules.sections_config import get_selector
            
            title_selector = get_selector("post_title")
            date_selector = get_selector("post_date")
            
            logger.info(f"使用标题选择器: '{title_selector}', 时间选择器: '{date_selector}'")
        except ImportError:
            logger.warning("无法导入 sections_config，将使用基本提取方法")
            title_selector = "strong"
            date_selector = ".f-l.l-h-13636.f-w-b.c-de0422.telegraph-time-box, .telegraph-time-box"
        
        result = {
            "title": "未知标题",
            "date": datetime.datetime.now().strftime("%Y.%m.%d"),
            "time": datetime.datetime.now().strftime("%H:%M")
        }
        
        try:
            # 只在调试模式下输出元素HTML
            if self.debug:
                logger.debug("处理帖子元素")
            
            # 提取标题 - 在财联社电报中，标题通常位于<strong>标签中
            title_el = post_element.query_selector(title_selector)
            if title_el:
                title_text = title_el.inner_text().strip()
                # 只输出标题的前30个字符，避免日志过长
                truncated_title = (title_text[:27] + "...") if len(title_text) > 30 else title_text
                result["title"] = title_text
                logger.info(f"提取到标题: {truncated_title}")
            else:
                logger.warning(f"未找到标题元素，选择器: '{title_selector}'")
            
            # 提取日期和时间
            try:
                # 1. 提取时间 - 从时间元素中获取
                date_el = post_element.query_selector(date_selector)
                if date_el:
                    time_text = date_el.inner_text().strip()
                    logger.info(f"提取到时间文本: {time_text}")
                    
                    # 尝试提取时间 (如 04:00:52)
                    time_match = re.search(r'(\d{2}:\d{2}(?::\d{2})?)', time_text)
                    if time_match:
                        result["time"] = time_match.group(1)
                        logger.info(f"解析出时间: {result['time']}")
                    else:
                        logger.warning(f"未能从时间文本中解析出时间: {time_text}")
                else:
                    logger.warning(f"未找到时间元素，选择器: '{date_selector}'")
                
                # 2. 提取日期 - 直接查找日期元素
                date_div_selector = "div.f-s-12.f-w-b.c-de0422, div.f-w-b.c-de0422"
                
                # 先直接在帖子元素中查找日期元素
                date_div = post_element.query_selector(date_div_selector)
                
                # 如果帖子元素中没有，再尝试在容器附近查找
                if not date_div:
                    # 检查post_element是否为ElementHandle对象，有evaluate方法
                    if hasattr(post_element, 'evaluate'):
                        try:
                            content_box = post_element.evaluate("el => el.closest('.clearfix.m-b-15.f-s-16.telegraph-content-box') || el.closest('.clearfix.p-r.l-h-26p.o-h.telegraph-content')")
                            # 确保content_box不是None且有evaluate方法
                            if content_box and hasattr(content_box, 'evaluate'):
                                parent_container = content_box.evaluate("el => el.parentElement")
                                if parent_container:
                                    date_div = parent_container.query_selector(date_div_selector)
                        except Exception as e:
                            logger.debug(f"在容器查找日期元素时出错: {e}")
                
                # 如果找到日期元素，提取并设置日期
                if date_div:
                    date_text = date_div.inner_text().strip()
                    logger.info(f"找到日期元素，文本为: {date_text}")
                    
                    # 提取日期（格式如 "2025.04.17 星期四"）
                    date_match = re.search(r'(\d{4}\.\d{1,2}\.\d{1,2})', date_text)
                    if date_match:
                        result["date"] = date_match.group(1)
                        logger.info(f"成功解析日期: {result['date']}")
                    else:
                        logger.warning(f"无法从文本 '{date_text}' 中提取日期")
                        result["date"] = datetime.datetime.now().strftime("%Y.%m.%d")
                else:
                    # 如果找不到日期元素，表示是当天的帖子
                    result["date"] = datetime.datetime.now().strftime("%Y.%m.%d")
                    logger.info(f"未找到日期元素，使用当天日期: {result['date']}")
                
            except Exception as e:
                logger.warning(f"提取日期和时间时出错: {e}")
                if self.debug:
                    logger.debug(traceback.format_exc())
            
            # 标记为有效帖子 - 只检查标题是否有效，不再考虑内容
            result["is_valid_post"] = bool(result["title"] != "未知标题")
            
            return result
        except Exception as e:
            log_error(logger, f"提取帖子信息时出错: {e}", e, self.debug)
            return result
    
    def scrape_section(self, section: str, max_posts: int = 20, cutoff_time: str = None) -> List[Dict[str, Any]]:
        """从指定版块获取帖子列表并分析"""
        if not self.navigator or not self.page:
            logger.error("未设置浏览器实例，无法爬取")
            return []
            
        try:
            # 导入选择器
            try:
                from chose_one_agent.modules.sections_config import get_selector
                post_selector = get_selector("post_items")
            except ImportError:
                logger.warning("无法导入sections_config，使用默认选择器")
                post_selector = ".post, article, .article, .item"
            
            posts = self.navigator.scrape_section(
                section, 
                post_selector, 
                self.extract_post_info,
                max_posts,
                cutoff_time
            )
            
            # 处理帖子和评论
            results = []
            for post_info in posts:
                try:
                    # 提取评论
                    comments = post_info.get("comments", [])
                    comment_count = len(comments)
                    
                    # 构建帖子信息
                    has_comments = comment_count > 0
                    post_result = {
                        "title": post_info.get("title", "未知标题"),
                        "date": post_info.get("date", ""),
                        "time": post_info.get("time", ""),
                        "section": section,
                        "comments": comments,
                        "comment_count": comment_count,
                        "has_comments": has_comments
                    }
                    
                    # 添加情感分析结果（如果有评论且分析器可用）
                    if has_comments and self._post_analyzer:
                        # 使用评论分析工具分析评论
                        sentiment_analysis = self._post_analyzer.analyze_post_data(post_result, comments)
                        post_result["sentiment_score"] = sentiment_analysis.get("sentiment_score", 0)
                        post_result["sentiment_label"] = sentiment_analysis.get("sentiment_label", "无评论")
                        post_result["sentiment_analysis"] = sentiment_analysis.get("insight", "")
                        
                        # 清理评论列表，只保留文本内容
                        post_result["comments"] = comments
                    else:
                        post_result["sentiment_score"] = 3  # 默认为中性
                        post_result["sentiment_label"] = "无评论"
                        
                    results.append(post_result)
                    
                except Exception as e:
                    logger.error(f"处理帖子 '{post_info.get('title', '未知标题')}' 时出错: {e}")
                    if self.debug:
                        logger.error(traceback.format_exc())
                        
            return results
            
        except Exception as e:
            log_error(logger, f"爬取 '{section}' 版块时出错", e, self.debug)
            return []
    
    def analyze_post(self, post_data: Dict[str, Any]) -> Dict[str, Any]:
        """分析帖子及其评论"""
        if not self._post_analyzer:
            logger.error("未设置分析工具，无法分析")
            return post_data
            
        # 使用注入的分析器实例
        try:
            analysis_results = self._post_analyzer.analyze_post_data(
                post_data, 
                post_data.get("comments", [])
            )
            # 将分析结果合并到原始数据中
            post_data.update(analysis_results)
            return post_data
        except Exception as e:
            log_error(logger, "分析帖子时出错", e, self.debug)
            return post_data
    
    def wait_for_network_idle(self, timeout: int = 5000):
        """等待网络请求完成"""
        self.page.wait_for_load_state("networkidle", timeout=timeout)
    
    def _navigate_to_telegraph(self) -> bool:
        """导航到Telegraph主页"""
        try:
            # 使用常量替换硬编码的财联社电报URL
            telegraph_url = BASE_URLS["telegraph"]
            
            # 导航到Telegraph主页
            logger.info(f"正在导航到电报: {telegraph_url}")
            success = self.navigator.navigate_to_url(telegraph_url)
            
            if success:
                logger.info("成功导航到电报主页")
                
                # 等待页面加载完成
                self.wait_for_network_idle()
                
                # 导入选择器
                try:
                    from chose_one_agent.modules.sections_config import get_selector
                    post_container_selector = get_selector("post_items")
                except ImportError:
                    logger.warning("无法导入选择器配置，使用默认选择器")
                    post_container_selector = ".b-c-e6e7ea.telegraph-list"
                
                logger.info(f"使用帖子容器选择器: '{post_container_selector}'")
                
                # 检查页面是否有内容元素
                post_containers = self.page.query_selector_all(post_container_selector)
                if post_containers:
                    logger.info(f"找到 {len(post_containers)} 个帖子容器")
                    
                    # 输出第一个容器的部分HTML用于调试
                    if self.debug and post_containers:
                        first_container_html = post_containers[0].inner_html()
                        logger.debug(f"第一个帖子容器HTML前150字符: {first_container_html[:150]}...")
                else:
                    logger.warning(f"未找到任何帖子容器，选择器: '{post_container_selector}'")
                    
                    # 在调试模式下，输出部分HTML用于调试
                    if self.debug:
                        html = self.page.content()
                        logger.debug(f"页面HTML前300字符: {html[:300]}...")
                    
            return success
        except Exception as e:
            log_error(logger, "导航到电报主页时出错", e, self.debug)
            return False
    
    def _scrape_section(self, section_name: str) -> List[Dict[str, Any]]:
        """
        爬取特定板块的内容
        
        Args:
            section_name: 板块名称
            
        Returns:
            板块内容列表
        """
        try:
            # 导航到指定板块
            if not self.navigate_to_telegraph_section(section_name):
                logger.error(f"导航到 '{section_name}' 板块失败")
                return []
            
            # 等待页面加载
            self.wait_for_network_idle()
            
            # 获取帖子容器选择器
            try:
                from chose_one_agent.modules.sections_config import get_selector
                post_container_selector = get_selector("post_items")
                logger.info(f"使用帖子容器选择器: '{post_container_selector}'")
            except ImportError:
                logger.warning("无法导入选择器配置，使用默认选择器")
                post_container_selector = ".b-c-e6e7ea.telegraph-list"
            
            # 爬取板块内容 - 传递截止日期
            logger.info(f"开始爬取 '{section_name}' 板块内容")
            return self.navigator.scrape_section(
                section_name,
                post_container_selector, 
                self.extract_post_info,
                30,
                self.cutoff_date
            )
            
        except Exception as e:
            log_error(logger, f"爬取 '{section_name}' 板块时出错", e, self.debug)
            return []
    
    def run_telegraph_scraper(self, sections: List[str] = None) -> List[Dict[str, Any]]:
        """
        运行Telegraph爬虫，从指定板块获取内容
        
        Args:
            sections: 要爬取的板块列表，如["看盘", "公司"]
            
        Returns:
            分析结果列表
        """
        # 设置默认板块
        if not sections:
            sections = ["看盘", "公司"]
        
        # 启动浏览器
        try:
            self.start_browser()
        except Exception as e:
            logger.error("启动浏览器失败，无法继续")
            return []
            
        # 导航到Telegraph页面
        if not self._navigate_to_telegraph():
            logger.warning("导航到Telegraph网站失败，将尝试直接访问各板块")
        
        results = []
        
        try:
            # 依次处理每个板块
            for section in sections:
                try:
                    logger.info(f"=== 开始爬取 '{section}' 板块 ===")
                    section_results = self._scrape_section(section)
                    results.extend(section_results)
                except Exception as e:
                    log_error(logger, f"爬取'{section}'板块时出错", e, self.debug)
                logger.info(f"=== 完成爬取 '{section}' 板块 ===")
                
            # 如果没有结果，记录警告
            if not results:
                logger.warning("未找到任何电报内容")
                
            return results
                
        except Exception as e:
            log_error(logger, "运行电报爬虫时出错", e, self.debug)
            return []
        finally:
            # 确保关闭浏览器
            self.close_browser()
    
    def run(self) -> List[Dict[str, Any]]:
        """
        执行爬取和分析过程，子类需要重写此方法
        
        Returns:
            包含所有分析结果的列表
        """
        raise NotImplementedError("子类必须实现run方法") 