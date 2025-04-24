"""
爬虫基础导航类，提供通用的页面导航功能
"""
import logging
import time
import traceback
import re
from typing import List, Optional, Dict, Any, Callable
from urllib.parse import urljoin
import datetime

from playwright.sync_api import Page, ElementHandle

from chose_one_agent.utils.constants import SCRAPER_CONSTANTS, COMMON_SELECTORS, BASE_URLS
from chose_one_agent.utils.logging_utils import get_logger, log_error
from chose_one_agent.utils.config import BASE_URL
from chose_one_agent.utils.datetime_utils import is_time_after_cutoff, parse_datetime, parse_cutoff_date

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
            section_name: 版块名称，如"公司"，"看盘"等
            
        Returns:
            导航是否成功
        """
        # 首先确保在Telegraph主页
        telegraph_url = BASE_URLS["telegraph"]
        if not self.navigate_to_url(telegraph_url):
            logger.error(f"无法导航到Telegraph主页: {telegraph_url}")
            return False
            
        # 等待页面加载
        time.sleep(SCRAPER_CONSTANTS["page_load_wait"])
            
        # 尝试根据文本内容找到并点击相应的导航项
        try:
            logger.info(f"尝试在页面上查找并点击 '{section_name}' 导航项")
            
            # 尝试不同的选择器策略来找到导航元素
            selectors = [
                f"a:text('{section_name}')",
                f"a:has-text('{section_name}')",
                f"text='{section_name}'",
                f".nav a:has-text('{section_name}')",
                f"li:has-text('{section_name}')"
            ]
            
            # 尝试点击每个可能的选择器
            for selector in selectors:
                try:
                    logger.info(f"尝试选择器: {selector}")
                    elements = self.page.query_selector_all(selector)
                    
                    for element in elements:
                        if element and element.is_visible():
                            element.click()
                            logger.info(f"已点击 '{section_name}' 导航项")
                            time.sleep(SCRAPER_CONSTANTS["page_load_wait"])  # 等待导航完成
                            return True
                except Exception as e:
                    if self.debug:
                        logger.debug(f"使用选择器 {selector} 点击失败: {str(e)}")
                    continue
            
            logger.warning(f"无法在页面上找到 '{section_name}' 导航项")
            return False
            
        except Exception as e:
            log_error(logger, f"导航到 '{section_name}' 版块时出错", e, self.debug)
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
            # 检查页面内容是否包含板块名称
            page_content = self.page.content()
            if section_name in page_content:
                logger.info(f"页面内容包含 '{section_name}', 确认导航成功")
                return True
                
            # 检查是否有帖子容器
            from chose_one_agent.modules.sections_config import get_selector
            post_selector = get_selector("post_items")
            logger.info(f"尝试查找帖子容器，使用选择器: '{post_selector}'")
            post_containers = self.page.query_selector_all(post_selector)
            if post_containers and len(post_containers) > 0:
                logger.info(f"找到 {len(post_containers)} 个帖子容器，确认导航成功")
                return True
                
            logger.warning(f"无法确认当前页面是 '{section_name}' 版块")
            return False
            
        except Exception as e:
            log_error(logger, f"验证 '{section_name}' 版块内容时出错", e, self.debug)
            return False
            
    def scrape_section(self, section: str, post_container_selector: str, 
                      extract_post_info_func: Callable, max_posts: int = 50,
                      cutoff_datetime: Optional[datetime.datetime] = None,
                      end_datetime: Optional[datetime.datetime] = None) -> List[Dict[str, Any]]:
        """
        从指定版块获取帖子列表
        
        Args:
            section: 版块名称
            post_container_selector: 帖子容器的CSS选择器
            extract_post_info_func: 提取帖子信息的函数
            max_posts: 最大获取帖子数
            cutoff_datetime: 开始日期时间对象，早于此时间的帖子将被忽略
            end_datetime: 结束日期时间对象，晚于此时间的帖子将被忽略
            
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
        
        # 导入选择器
        try:
            from chose_one_agent.modules.sections_config import get_selector
            content_box_selector = get_selector("post_content_box")
            logger.info(f"使用内容盒子选择器: '{content_box_selector}'")
        except ImportError:
            logger.warning("无法导入选择器配置，使用默认内容盒子选择器")
            content_box_selector = ".clearfix.m-b-15.f-s-16.telegraph-content-box"
        
        # 爬取帖子
        posts = self._scrape_posts(post_container_selector, content_box_selector, 
                                  extract_post_info_func, cutoff_datetime, end_datetime,
                                  processed_ids, results, section, max_posts)
        
        logger.info(f"从 '{section}' 版块共获取了 {len(results)} 个帖子")
        return results
        
    def _scrape_posts(self, post_container_selector: str, content_box_selector: str,
                     extract_post_info_func: Callable, cutoff_datetime: Optional[datetime.datetime],
                     end_datetime: Optional[datetime.datetime],
                     processed_ids: set, results: list, section: str, max_posts: int) -> List[Dict[str, Any]]:
        """爬取帖子"""
        try:
            import datetime
            
            # 记录截止日期时间
            if cutoff_datetime:
                logger.info(f"使用开始日期时间: {cutoff_datetime}")
            if end_datetime:
                logger.info(f"使用结束日期时间: {end_datetime}")
            
            # 获取帖子容器元素
            logger.info(f"查找帖子容器，使用选择器: '{post_container_selector}'")
            containers = self.page.query_selector_all(post_container_selector)
            
            if not containers:
                logger.error(f"未找到帖子容器，选择器: '{post_container_selector}'")
                # 输出部分DOM结构以便调试
                if self.debug:
                    try:
                        html = self.page.content()
                        logger.debug(f"页面HTML前200字符: {html[:200]}...")
                    except Exception:
                        pass
                return []
                
            logger.info(f"找到 {len(containers)} 个帖子容器")
            
            # 在容器中查找内容盒子
            all_processed_posts = []
            early_post_found = False  # 新增: 早期帖子标志，用于提前终止处理
            
            for i, container in enumerate(containers):
                if len(results) >= max_posts:
                    logger.info(f"已达到目标帖子数 {max_posts}，停止处理")
                    break
                    
                logger.info(f"处理容器 #{i+1}")
                
                # 查找内容盒子
                content_boxes = container.query_selector_all(content_box_selector)
                if not content_boxes:
                    logger.warning(f"在容器 #{i+1} 中未找到内容盒子，选择器: '{content_box_selector}'")
                    continue
                    
                logger.info(f"在容器 #{i+1} 中找到 {len(content_boxes)} 个内容盒子")
                
                for box in content_boxes:
                    # 提取帖子ID
                    post_id = box.get_attribute("id") or hash(box.inner_html())
                    
                    # 如果已处理过该帖子，跳过
                    if post_id in processed_ids:
                        continue
                        
                    # 提取帖子信息
                    post_info = extract_post_info_func(box)
                    post_info["section"] = section
                    
                    # 检查是否在截止时间之后
                    if cutoff_datetime:
                        post_date = post_info.get("date", datetime.datetime.now().strftime("%Y.%m.%d"))
                        post_time = post_info.get("time", "")
                        try:
                            # 确保时间格式统一，添加秒数如果没有
                            if post_time and post_time.count(':') == 1:
                                post_time += ':00'
                            
                            # 构建帖子的完整日期时间对象
                            post_datetime = datetime.datetime.strptime(f"{post_date} {post_time}", "%Y.%m.%d %H:%M:%S")
                            
                            # 验证帖子时间是否在有效范围内
                            valid_post = True
                            
                            # 检查是否晚于开始日期
                            if cutoff_datetime and post_datetime < cutoff_datetime:
                                logger.info(f"帖子时间 {post_datetime} 早于或等于开始时间 {cutoff_datetime}，丢弃")
                                valid_post = False
                                early_post_found = True
                            
                            # 检查是否早于结束日期
                            if valid_post and end_datetime and post_datetime > end_datetime:
                                logger.info(f"帖子时间 {post_datetime} 晚于结束时间 {end_datetime}，丢弃")
                                valid_post = False
                                # 不设置early_post_found标志，这里不应该中断爬取
                            
                            # 如果帖子有效，添加到结果
                            if valid_post:
                                logger.info(f"帖子时间 {post_datetime} 在有效时间范围内，保留")
                                results.append(post_info)
                                processed_ids.add(post_id)
                                all_processed_posts.append(post_info)
                        except ValueError as e:
                            logger.warning(f"解析帖子时间出错: {post_date} {post_time}, {e}")
                    else:
                        # 如果没有截止时间限制，直接添加到结果
                        results.append(post_info)
                        processed_ids.add(post_id)
                        all_processed_posts.append(post_info)
                    
                    if len(results) >= max_posts:
                        break
                
                # 如果已发现早于截止时间的帖子，终止容器处理
                if early_post_found:
                    logger.info(f"发现早于截止时间的帖子，跳过后续容器处理")
                    break
            
            # 如果已发现早于截止时间的帖子，不再加载更多内容
            if early_post_found:
                logger.info(f"已找到早于截止时间的帖子，不再加载更多内容，返回已收集的结果")
                return all_processed_posts
                
            # 尝试加载更多帖子，直到达到目标数量
            attempts = 0
            while len(results) < max_posts and attempts < 3:
                attempts += 1
                logger.info(f"已获取 {len(results)}/{max_posts} 个帖子，尝试加载更多 (尝试 {attempts}/3)")
                
                # 尝试加载更多帖子
                if not self._load_more_posts():
                    logger.info("没有更多帖子可加载，停止加载")
                    break
                    
                # 获取新容器
                new_containers = self.page.query_selector_all(post_container_selector)
                if len(new_containers) <= len(containers):
                    logger.info("加载更多后未发现新帖子，停止加载")
                    break
                    
                logger.info(f"加载更多后，帖子容器数从 {len(containers)} 增加到 {len(new_containers)}")
                
                # 处理新增的容器
                for i in range(len(containers), len(new_containers)):
                    if len(results) >= max_posts:
                        break
                        
                    container = new_containers[i]
                    logger.info(f"处理新容器 #{i+1}")
                    
                    # 查找内容盒子
                    content_boxes = container.query_selector_all(content_box_selector)
                    if not content_boxes:
                        continue
                        
                    logger.info(f"在新容器 #{i+1} 中找到 {len(content_boxes)} 个内容盒子")
                    
                    for box in content_boxes:
                        # 提取帖子ID
                        post_id = box.get_attribute("id") or hash(box.inner_html())
                        
                        # 如果已处理过该帖子，跳过
                        if post_id in processed_ids:
                            continue
                            
                        # 提取帖子信息
                        post_info = extract_post_info_func(box)
                        post_info["section"] = section
                        
                        # 检查是否在截止时间之后
                        if cutoff_datetime:
                            post_date = post_info.get("date", datetime.datetime.now().strftime("%Y.%m.%d"))
                            post_time = post_info.get("time", "")
                            try:
                                # 确保时间格式统一，添加秒数如果没有
                                if post_time and post_time.count(':') == 1:
                                    post_time += ':00'
                                
                                # 构建帖子的完整日期时间对象
                                post_datetime = datetime.datetime.strptime(f"{post_date} {post_time}", "%Y.%m.%d %H:%M:%S")
                                
                                # 验证帖子时间是否在有效范围内
                                valid_post = True
                                
                                # 检查是否晚于开始日期
                                if cutoff_datetime and post_datetime < cutoff_datetime:
                                    logger.info(f"帖子时间 {post_datetime} 早于或等于开始时间 {cutoff_datetime}，丢弃")
                                    valid_post = False
                                    early_post_found = True
                                
                                # 检查是否早于结束日期
                                if valid_post and end_datetime and post_datetime > end_datetime:
                                    logger.info(f"帖子时间 {post_datetime} 晚于结束时间 {end_datetime}，丢弃")
                                    valid_post = False
                                    # 不设置early_post_found标志，这里不应该中断爬取
                                
                                # 如果帖子有效，添加到结果
                                if valid_post:
                                    logger.info(f"帖子时间 {post_datetime} 在有效时间范围内，保留")
                                    results.append(post_info)
                                    processed_ids.add(post_id)
                                    all_processed_posts.append(post_info)
                            except ValueError as e:
                                logger.warning(f"解析帖子时间出错: {post_date} {post_time}, {e}")
                        else:
                            # 如果没有截止时间限制，直接添加到结果
                            results.append(post_info)
                            processed_ids.add(post_id)
                            all_processed_posts.append(post_info)
                        
                        if len(results) >= max_posts:
                            break
                    
                    # 如果已发现早于截止时间的帖子，终止容器处理
                    if early_post_found:
                        logger.info(f"发现早于截止时间的帖子，跳过后续容器处理")
                        break
                
                # 如果已发现早于截止时间的帖子，不再继续加载更多内容
                if early_post_found:
                    logger.info(f"已找到早于截止时间的帖子，不再加载更多内容")
                    break
                
                # 更新容器列表
                containers = new_containers
                
            return all_processed_posts
            
        except Exception as e:
            log_error(logger, "爬取帖子时出错", e, self.debug)
            return []
            
    def _load_more_posts(self) -> bool:
        """加载更多帖子"""
        try:
            # 导入加载更多按钮选择器
            try:
                from chose_one_agent.modules.sections_config import get_selector
                load_more_selector = get_selector("load_more")
                logger.info(f"使用加载更多按钮选择器: '{load_more_selector}'")
            except ImportError:
                logger.warning("无法导入选择器配置，使用默认加载更多按钮选择器")
                load_more_selector = "div.f-s-14.list-more-button.more-button"
            
            # 尝试点击"加载更多"按钮 - 增加多种尝试方法
            # 第一种：使用配置选择器
            more_button = self.page.query_selector(load_more_selector)
            if more_button and more_button.is_visible():
                logger.info("找到'加载更多'按钮，点击加载")
                more_button.click()
                time.sleep(SCRAPER_CONSTANTS["page_load_wait"] * 2)  # 增加等待时间
                return True
            
            # 第二种：尝试使用文本内容查找
            more_button_by_text = self.page.query_selector("div:has-text('加载更多')")
            if more_button_by_text and more_button_by_text.is_visible():
                logger.info("通过文本内容找到'加载更多'按钮，点击加载")
                more_button_by_text.click()
                time.sleep(SCRAPER_CONSTANTS["page_load_wait"] * 2)
                return True
                
            # 第三种：使用XPath尝试查找
            try:
                more_button_xpath = self.page.query_selector("//div[contains(text(), '加载更多')]")
                if more_button_xpath and more_button_xpath.is_visible():
                    logger.info("通过XPath找到'加载更多'按钮，点击加载")
                    more_button_xpath.click()
                    time.sleep(SCRAPER_CONSTANTS["page_load_wait"] * 2)
                    return True
            except Exception as e:
                logger.warning(f"使用XPath查找按钮出错: {e}")
                
            # 尝试滚动到页面底部触发加载
            logger.info("未找到'加载更多'按钮，尝试滚动加载")
            
            # 记录滚动前高度
            current_height = self.page.evaluate("document.body.scrollHeight")
            
            # 先滚动到页面3/4处
            self.page.evaluate("window.scrollTo(0, document.body.scrollHeight * 0.75)")
            time.sleep(SCRAPER_CONSTANTS["page_load_wait"])
            
            # 再滚动到底部
            self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(SCRAPER_CONSTANTS["page_load_wait"] * 2)
            
            # 额外尝试点击可能延迟加载的按钮
            more_button_delayed = self.page.query_selector(load_more_selector)
            if more_button_delayed and more_button_delayed.is_visible():
                logger.info("滚动后找到'加载更多'按钮，点击加载")
                more_button_delayed.click()
                time.sleep(SCRAPER_CONSTANTS["page_load_wait"] * 2)
                return True
            
            # 检查是否滚动触发了加载
            new_height = self.page.evaluate("document.body.scrollHeight")
            if new_height > current_height:
                logger.info("滚动触发了加载，高度从 {} 增加到 {}".format(current_height, new_height))
                return True
                
            logger.info("滚动未触发加载，可能已加载全部内容")
            return False
            
        except Exception as e:
            log_error(logger, "加载更多帖子时出错", e, self.debug)
            return False 