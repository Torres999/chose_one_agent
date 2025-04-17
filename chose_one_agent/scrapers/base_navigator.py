"""
爬虫基础导航类，提供通用的页面导航功能
"""
import logging
import time
import traceback
import re
from typing import List, Optional, Dict, Any, Callable
from urllib.parse import urljoin

from playwright.sync_api import Page, ElementHandle

from chose_one_agent.utils.constants import SCRAPER_CONSTANTS, COMMON_SELECTORS
from chose_one_agent.utils.logging_utils import get_logger, log_error
from chose_one_agent.utils.config import BASE_URL

# 获取日志记录器
logger = get_logger(__name__)

class BaseNavigator:
    """基础导航类，提供通用的页面导航功能"""
    
    def __init__(self, page: Page, base_url: str = None, debug: bool = False):
        """
        初始化导航器
        
        Args:
            page: Playwright页面对象
            base_url: 基础URL
            debug: 是否开启调试模式
        """
        self.page = page
        self.base_url = base_url or BASE_URL
        self.debug = debug
        self.last_url = None
    
    def navigate_to_url(self, url: str, wait_until: str = "networkidle", 
                       timeout: int = None) -> bool:
        """
        导航到指定URL
        
        Args:
            url: 目标URL
            wait_until: 等待页面加载的条件
            timeout: 超时时间(毫秒)
            
        Returns:
            bool: 是否成功导航
        """
        if timeout is None:
            timeout = SCRAPER_CONSTANTS["default_timeout"]
            
        if not self.page:
            logger.error("未设置页面实例，无法导航")
            return False
            
        try:
            logger.info(f"导航到: {url}")
            response = self.page.goto(url, wait_until=wait_until, timeout=timeout)
            
            if response and response.ok:
                self.last_url = url
                logger.info(f"导航成功: {url}")
                return True
            else:
                logger.warning(f"导航失败: {url}, 状态码: {response.status if response else 'unknown'}")
                return False
        except Exception as e:
            log_error(logger, f"导航到 {url} 出错", e, self.debug)
            return False
    
    def click_element(self, selector: str, timeout: int = None) -> bool:
        """
        点击元素
        
        Args:
            selector: 元素选择器
            timeout: 超时时间(毫秒)
            
        Returns:
            bool: 是否成功点击
        """
        if timeout is None:
            timeout = SCRAPER_CONSTANTS["short_timeout"]
            
        try:
            self.page.click(selector, timeout=timeout)
            # 等待页面加载
            self.page.wait_for_load_state("networkidle", timeout=timeout)
            time.sleep(SCRAPER_CONSTANTS["element_wait"])
            return True
        except Exception as e:
            log_error(logger, f"点击元素 {selector} 出错", e, self.debug)
            return False
    
    def try_multiple_selectors(self, selectors: List[str], action: str = "click", 
                              timeout: int = None) -> bool:
        """
        尝试多个选择器执行操作
        
        Args:
            selectors: 选择器列表
            action: 要执行的操作，'click'或'hover'
            timeout: 超时时间(毫秒)
            
        Returns:
            bool: 是否操作成功
        """
        if timeout is None:
            timeout = SCRAPER_CONSTANTS["short_timeout"]
            
        for selector in selectors:
            try:
                # 先检查元素是否存在
                element = self.page.query_selector(selector)
                if not element:
                    continue
                    
                # 执行指定操作
                if action == "click":
                    element.click(timeout=timeout)
                elif action == "hover":
                    element.hover(timeout=timeout)
                else:
                    return False
                    
                # 等待页面加载
                self.page.wait_for_load_state("networkidle", timeout=timeout)
                time.sleep(SCRAPER_CONSTANTS["element_wait"])
                return True
            except Exception:
                continue
                
        return False
    
    def load_more_content(self, max_attempts: int = 3) -> bool:
        """
        加载更多内容
        
        Args:
            max_attempts: 最大尝试次数
            
        Returns:
            bool: 是否成功加载更多内容
        """
        try:
            # 首先尝试点击"加载更多"按钮
            if self.try_multiple_selectors(COMMON_SELECTORS["load_more"]):
                logger.info("点击加载更多按钮成功")
                return True
                
            # 然后尝试滚动页面
            previous_height = self.page.evaluate("document.body.scrollHeight")
            self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            logger.info("尝试滚动页面加载更多内容")
            
            # 等待页面加载
            time.sleep(SCRAPER_CONSTANTS["page_load_wait"])
            
            # 检查是否有新内容加载
            current_height = self.page.evaluate("document.body.scrollHeight")
            if current_height > previous_height:
                return True
                
            return False
        except Exception as e:
            log_error(logger, "加载更多内容出错", e, self.debug)
            return False
    
    def find_elements(self, selector: str) -> List[Any]:
        """
        查找所有匹配的元素
        
        Args:
            selector: 元素选择器
            
        Returns:
            List[Any]: 找到的元素列表
        """
        try:
            return self.page.query_selector_all(selector)
        except Exception as e:
            log_error(logger, f"查找元素 {selector} 出错", e, self.debug)
            return []
    
    def get_element_text(self, element_or_selector) -> str:
        """
        获取元素文本内容
        
        Args:
            element_or_selector: 元素对象或选择器字符串
            
        Returns:
            str: 元素文本内容
        """
        try:
            if isinstance(element_or_selector, str):
                element = self.page.query_selector(element_or_selector)
                if not element:
                    return ""
            else:
                element = element_or_selector
                
            text = element.inner_text().strip()
            return text
        except Exception as e:
            log_error(logger, "获取元素文本出错", e, self.debug)
            return ""
    
    def get_element_attribute(self, element_or_selector, attribute: str) -> str:
        """
        获取元素属性值
        
        Args:
            element_or_selector: 元素对象或选择器字符串
            attribute: 属性名
            
        Returns:
            str: 属性值
        """
        try:
            if isinstance(element_or_selector, str):
                element = self.page.query_selector(element_or_selector)
                if not element:
                    return ""
            else:
                element = element_or_selector
                
            value = element.get_attribute(attribute) or ""
            return value.strip()
        except Exception as e:
            log_error(logger, f"获取元素属性 {attribute} 出错", e, self.debug)
            return ""
    
    def wait_for_selector(self, selector: str, timeout: int = None) -> bool:
        """
        等待选择器出现
        
        Args:
            selector: 选择器
            timeout: 超时时间(毫秒)
            
        Returns:
            bool: 是否找到选择器
        """
        if timeout is None:
            timeout = SCRAPER_CONSTANTS["short_timeout"]
            
        try:
            self.page.wait_for_selector(selector, timeout=timeout)
            return True
        except Exception as e:
            log_error(logger, f"等待选择器 {selector} 超时", e, self.debug)
            return False
    
    def wait_for_navigation(self, timeout: int = None) -> bool:
        """
        等待页面导航完成
        
        Args:
            timeout: 超时时间(毫秒)
            
        Returns:
            bool: 是否成功等待
        """
        if timeout is None:
            timeout = SCRAPER_CONSTANTS["default_timeout"]
            
        try:
            self.page.wait_for_load_state("networkidle", timeout=timeout)
            return True
        except Exception as e:
            log_error(logger, "等待页面导航超时", e, self.debug)
            return False
    
    def execute_script(self, script: str) -> Any:
        """
        执行JavaScript
        
        Args:
            script: JavaScript代码
            
        Returns:
            Any: 脚本执行结果
        """
        try:
            return self.page.evaluate(script)
        except Exception as e:
            log_error(logger, "执行脚本出错", e, self.debug)
            return None
    
    def go_back(self) -> bool:
        """
        返回上一页
        
        Returns:
            bool: 是否成功返回
        """
        try:
            self.page.go_back()
            self.wait_for_navigation()
            return True
        except Exception as e:
            log_error(logger, "返回上一页出错", e, self.debug)
            return False
    
    # === 添加 TelegraphNavigator 类的功能 ===
    
    def navigate_to_telegraph_section(self, section_name: str) -> bool:
        """
        导航到Telegraph的特定版块
        
        Args:
            section_name: 版块名称，如"看盘"，"公司"等
            
        Returns:
            导航是否成功
        """
        # 从 navigation.py 导入
        from chose_one_agent.modules.sections_config import SECTION_URLS
        
        # 首先尝试直接使用URL导航
        if section_name in SECTION_URLS:
            url = SECTION_URLS[section_name]
            if self.navigate_to_url(url):
                time.sleep(2)  # 等待页面加载
                # 确认是否导航到正确的版块
                if self.verify_section_content(section_name):
                    return True
                else:
                    logger.warning(f"无法验证 '{section_name}' 版块内容")
        
        # 如果直接导航失败，尝试从主页导航
        logger.info(f"直接导航失败，尝试从主页导航到 '{section_name}' 版块")
        
        # 导航到主站
        telegraph_url = urljoin(self.base_url, "/telegraph")
        if not self.navigate_to_url(telegraph_url):
            logger.error(f"无法导航到Telegraph主页: {telegraph_url}")
            return False
            
        # 等待加载
        time.sleep(2)
            
        # 尝试点击相应的版块链接
        try:
            # 定义可能的选择器
            selectors = [
                f"text='{section_name}'", 
                f"a:has-text('{section_name}')",
                f"[class*='tab']:has-text('{section_name}')"
            ]
            
            # 尝试点击每个可能的选择器
            if self._try_click_selectors(selectors):
                time.sleep(2)  # 等待页面加载
                if self.verify_section_content(section_name):
                    return True
                
            # 尝试使用可能的URL路径
            if self._try_possible_urls(section_name):
                return True
                
            logger.error(f"无法找到 '{section_name}' 版块")
            return False
            
        except Exception as e:
            log_error(logger, f"导航到 '{section_name}' 版块时出错", e, self.debug)
            return False
    
    def _try_click_selectors(self, selectors: List[str]) -> bool:
        """尝试点击多个可能的选择器"""
        for selector in selectors:
            try:
                element = self.page.query_selector(selector)
                if element and element.is_visible():
                    element.click()
                    logger.info(f"已点击元素: {selector}")
                    time.sleep(2)  # 等待导航完成
                    return True
            except Exception as e:
                if self.debug:
                    logger.debug(f"点击 {selector} 失败: {e}")
        return False
        
    def _try_possible_urls(self, section_name: str) -> bool:
        """尝试可能的URL路径"""
        # 尝试多种URL路径格式
        url_formats = [
            "/telegraph/{}",
            "/telegraph/{}s",
            "/telegraph/channel/{}",
            "/telegraph/section/{}"
        ]
        
        for url_format in url_formats:
            url_path = url_format.format(section_name.lower())
            full_url = urljoin(self.base_url, url_path)
            
            logger.info(f"尝试导航到: {full_url}")
            if self.navigate_to_url(full_url):
                time.sleep(2)
                if self.verify_section_content(section_name):
                    return True
                    
        return False
        
    def verify_section_content(self, section_name: str) -> bool:
        """
        验证当前页面是否为指定版块内容
        
        Args:
            section_name: 版块名称
            
        Returns:
            是否为指定版块
        """
        try:
            # 检查URL中是否包含版块名称或相关关键词
            current_url = self.page.url.lower()
            section_lower = section_name.lower()
            
            # 直接检查URL
            if section_lower in current_url:
                logger.info(f"URL包含 '{section_name}', 确认导航成功")
                return True
                
            # 检查页面标题或面包屑
            title_element = self.page.query_selector("title, h1, .breadcrumb")
            if title_element:
                title_text = title_element.inner_text().lower()
                if section_lower in title_text:
                    logger.info(f"页面标题包含 '{section_name}', 确认导航成功")
                    return True
            
            # 检查是否有帖子内容
            # 从 navigation.py 导入
            from chose_one_agent.modules.sections_config import get_selector
            post_selector = get_selector("post_items")
            posts = self.page.query_selector_all(post_selector)
            if posts:
                logger.info(f"找到 {len(posts)} 个帖子，假定导航成功")
                return True
                
            logger.warning(f"无法确认当前页面是 '{section_name}' 版块")
            return False
            
        except Exception as e:
            log_error(logger, f"验证 '{section_name}' 版块内容时出错", e, self.debug)
            return False
            
    def scrape_section(self, section: str, post_container_selector: str, 
                      extract_post_info_func: Callable, max_posts: int = 50,
                      cutoff_time: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        从指定版块获取帖子列表
        
        Args:
            section: 版块名称
            post_container_selector: 帖子容器的CSS选择器
            extract_post_info_func: 提取帖子信息的函数
            max_posts: 最大获取帖子数
            cutoff_time: 截止时间，早于此时间的帖子将被忽略
            
        Returns:
            帖子信息列表
        """
        # 初始化结果和已处理的帖子ID集合
        results = []
        processed_ids = set()
        
        # 检查是否在正确的版块页面
        if not self.verify_section_content(section):
            logger.warning(f"可能不在 '{section}' 版块页面，继续尝试获取内容")
        
        logger.info(f"开始从 '{section}' 版块获取帖子")
        
        # 首次处理当前页面的帖子
        posts = self._get_and_process_posts(post_container_selector, extract_post_info_func, 
                                          cutoff_time, processed_ids, results)
        
        # 加载更多帖子，直到达到目标数量或没有更多帖子
        while len(results) < max_posts:
            logger.info(f"已获取 {len(results)}/{max_posts} 个帖子，尝试加载更多")
            
            # 尝试加载更多帖子
            if not self._load_more_posts():
                logger.info("没有更多帖子可加载，停止加载")
                break
                
            # 处理新加载的帖子
            new_posts = self._get_and_process_posts(post_container_selector, extract_post_info_func, 
                                                 cutoff_time, processed_ids, results)
            
            # 如果没有获取到新帖子，停止加载
            if not new_posts:
                logger.info("没有获取到新帖子，停止加载")
                break
                
            # 如果已达到目标数量，停止加载
            if len(results) >= max_posts:
                logger.info(f"已达到目标数量: {max_posts}，停止加载")
                break
                
        logger.info(f"从 '{section}' 版块共获取了 {len(results)} 个帖子")
        return results
        
    def _get_and_process_posts(self, post_container_selector: str, extract_post_info_func: Callable,
                              cutoff_time: Optional[str], processed_ids: set, results: list) -> List[Any]:
        """获取并处理帖子"""
        try:
            # 获取帖子元素
            posts = self.page.query_selector_all(post_container_selector)
            
            if not posts:
                logger.warning(f"未找到帖子元素，选择器: {post_container_selector}")
                return []
                
            logger.info(f"找到 {len(posts)} 个帖子元素")
            
            # 处理帖子
            processed_posts = []
            for post in posts:
                # 提取帖子ID或使用元素内容哈希作为ID
                post_id = post.get_attribute("id") or hash(post.inner_html())
                
                # 如果已处理过该帖子，跳过
                if post_id in processed_ids:
                    continue
                    
                # 提取帖子信息
                post_info = extract_post_info_func(post)
                post_info["section"] = post_info.get("section", "") or section
                
                # 检查是否在截止时间之前
                if cutoff_time and post_info.get("time", "") < cutoff_time:
                    logger.info(f"帖子时间 {post_info.get('time')} 早于截止时间 {cutoff_time}，跳过")
                    continue
                    
                # 添加到结果
                results.append(post_info)
                processed_ids.add(post_id)
                processed_posts.append(post)
                
            return processed_posts
            
        except Exception as e:
            log_error(logger, "获取和处理帖子时出错", e, self.debug)
            return []
            
    def _load_more_posts(self) -> bool:
        """加载更多帖子"""
        try:
            # 尝试点击"加载更多"按钮
            more_button = self.page.query_selector("text='加载更多', .load-more, button:has-text('加载更多')")
            if more_button and more_button.is_visible():
                logger.info("找到'加载更多'按钮，点击加载")
                more_button.click()
                time.sleep(2)  # 等待加载完成
                return True
                
            # 尝试滚动到页面底部触发加载
            logger.info("未找到'加载更多'按钮，尝试滚动加载")
            current_height = self.page.evaluate("document.body.scrollHeight")
            self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)
            
            # 检查是否滚动触发了加载
            new_height = self.page.evaluate("document.body.scrollHeight")
            if new_height > current_height:
                logger.info("滚动触发了加载")
                return True
                
            logger.info("滚动未触发加载，可能已加载全部内容")
            return False
            
        except Exception as e:
            log_error(logger, "加载更多帖子时出错", e, self.debug)
            return False 