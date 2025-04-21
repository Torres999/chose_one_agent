# -*- coding: utf-8 -*-
"""
基础爬虫类，所有爬虫继承自此类
"""
import os
import datetime
import logging
import re
import time
import random
import traceback
from typing import List, Dict, Any, Optional
from urllib.parse import quote, urlparse, urljoin

from playwright.sync_api import sync_playwright, Browser, Page, TimeoutError as PlaywrightTimeoutError, ElementHandle

from chose_one_agent.utils.datetime_utils import convert_relative_time, get_current_datetime, is_before_cutoff, parse_datetime
from chose_one_agent.utils.constants import SCRAPER_CONSTANTS, BASE_URLS
from chose_one_agent.utils.logging_utils import get_logger, log_error
from chose_one_agent.utils.extraction import extract_post_content, clean_text
from chose_one_agent.scrapers.base_navigator import BaseNavigator

# 设置日志
logger = get_logger(__name__)

class BaseScraper:
    """
    基础爬虫类，供各功能模块继承使用
    """
    
    def __init__(self, cutoff_date: datetime.datetime = None, headless: bool = True, debug: bool = False):
        """
        初始化爬虫基础类
        
        Args:
            cutoff_date: 截止日期，早于此日期的内容将被忽略
            headless: 是否使用无头模式运行浏览器
            debug: 是否启用调试模式
        """
        self.cutoff_date = cutoff_date
        self.headless = headless
        self.debug = debug
        self.base_url = BASE_URLS["main"]
        
        # 初始化浏览器相关属性
        self.playwright = None
        self.browser = None
        self.page = None
        
        # 记录断开连接状态
        self.is_connected = False
        
        # 截取屏幕截图的序号
        self.screenshot_count = 0
        
        # 初始化日志
        self.logger = logger
        
        # 以下组件将在需要时初始化
        self._comment_extractor = None
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
            
            # 创建浏览器启动选项
            browser_options = {
                "headless": self.headless
            }
            
            # 创建浏览器上下文选项
            context_options = {
                "viewport": SCRAPER_CONSTANTS["viewport"],
                # JavaScript默认已启用，无需设置
                "bypass_csp": True,
                # 设置权限
                "permissions": ["geolocation", "notifications"],
            }
            
            # 启动浏览器
            self.browser = self.playwright.chromium.launch(**browser_options)
            
            # 创建上下文
            self.context = self.browser.new_context(**context_options)
            
            # 设置路由，拦截图片请求
            self.context.route("**/*.{png,jpg,jpeg,webp,svg,gif,ico}", lambda route: route.abort())
            
            # 创建页面
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
            
            # 创建评论提取器实例
            self._comment_extractor = CommentExtractor(self.page, self.debug)
            
        except ImportError as e:
            # 这些组件可能不是所有爬虫都需要的，记录日志但不终止程序
            logger.warning(f"初始化组件时出错: {e}")
            self._comment_extractor = None
    
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
    
    def extract_post_info(self, post_element) -> Dict[str, Any]:
        """从帖子元素中提取信息"""
        # 导入选择器
        try:
            from chose_one_agent.utils.datetime_utils import is_before_cutoff, parse_datetime
            from chose_one_agent.modules.sections_config import get_selector
            
            title_selector = get_selector("post_title")
            date_selector = get_selector("post_date")
            content_selector = get_selector("post_content") or ".post-content, .telegraph-content-text, .text, .content, .telegraph-text, p"
            
            logger.info(f"使用标题选择器: '{title_selector}', 时间选择器: '{date_selector}', 内容选择器: '{content_selector}'")
        except ImportError:
            logger.warning("无法导入 sections_config，将使用基本提取方法")
            title_selector = "strong"
            date_selector = ".f-l.l-h-13636.f-w-b.c-de0422.telegraph-time-box, .telegraph-time-box"
            content_selector = ".post-content, .telegraph-content-text, .text, .content, .telegraph-text, p"
        
        result = {
            "title": "未知标题",
            "date": datetime.datetime.now().strftime("%Y.%m.%d"),
            "time": datetime.datetime.now().strftime("%H:%M"),
            "comments": [],
            "comment_count": 0,
            "is_valid_post": False
        }
        
        try:
            # 只在调试模式下输出元素HTML
            if self.debug:
                html = post_element.inner_html()
                logger.debug(f"处理帖子元素HTML: {html[:200]}...")
            
            # 提取标题 - 标题通常位于<strong>标签中
            title_el = post_element.query_selector(title_selector)
            if title_el:
                title_text = title_el.inner_text().strip()
                # 只输出标题的前30个字符，避免日志过长
                truncated_title = (title_text[:27] + "...") if len(title_text) > 30 else title_text
                result["title"] = title_text
                logger.info(f"提取到标题: {truncated_title}")
            else:
                logger.warning(f"未找到标题元素，选择器: '{title_selector}'")
                
                # 如果未找到标题，尝试从正文中提取前20个字符作为标题
                content_el = post_element.query_selector(content_selector)
                if content_el:
                    content_text = content_el.inner_text().strip()
                    if content_text:
                        # 提取前20个字符，如果有限制的话
                        content_title = content_text[:20] + "..." if len(content_text) > 20 else content_text
                        result["title"] = content_title
                        logger.info(f"从正文提取标题: {content_title}")
                        
                        # 存储完整内容，用于后续处理
                        result["content"] = content_text
                else:
                    # 如果也未找到内容元素，尝试直接从帖子元素提取文本
                    full_text = post_element.inner_text().strip()
                    if full_text:
                        # 清理文本，移除可能的日期和时间信息
                        clean_text = re.sub(r'\d{2}:\d{2}(:\d{2})?', '', full_text)
                        clean_text = re.sub(r'\d{4}[.-]\d{2}[.-]\d{2}', '', clean_text).strip()
                        
                        if clean_text:
                            # 提取前20个字符作为标题
                            content_title = clean_text[:20] + "..." if len(clean_text) > 20 else clean_text
                            result["title"] = content_title
                            logger.info(f"从帖子文本提取标题: {content_title}")
                            
                            # 存储完整内容
                            result["content"] = clean_text
            
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
                
                # ======= 检查帖子日期是否符合截止日期要求 =======
                if self.cutoff_date:
                    # 构建日期时间对象
                    post_date_str = f"{result['date']} {result['time']}"
                    post_datetime = None
                    try:
                        # 尝试不同的日期格式解析
                        formats = [
                            "%Y.%m.%d %H:%M:%S",
                            "%Y.%m.%d %H:%M",
                            "%Y-%m-%d %H:%M:%S",
                            "%Y-%m-%d %H:%M"
                        ]
                        for date_format in formats:
                            try:
                                post_datetime = datetime.datetime.strptime(post_date_str, date_format)
                                break
                            except ValueError:
                                continue
                        
                        # 如果所有格式都失败，尝试使用parse_datetime函数
                        if not post_datetime:
                            post_datetime = parse_datetime(post_date_str)
                        
                        # 检查是否早于截止日期
                        if post_datetime and is_before_cutoff(post_datetime, self.cutoff_date):
                            logger.info(f"帖子日期 {post_date_str} 早于截止日期 {self.cutoff_date}，标记为无效帖子")
                            # 标记为无效帖子，但标题仍然可能有效
                            result["is_valid_post"] = result["title"] != "未知标题"
                            result["is_before_cutoff"] = True
                            return result  # 提前返回，不处理评论
                    except Exception as e:
                        logger.warning(f"检查帖子日期时出错: {e}")
                        if self.debug:
                            logger.debug(traceback.format_exc())
                
                # 3. 查找评论链接和评论数量 - 只有在帖子符合日期要求时才执行
                try:
                    detail_link = None
                    comment_count = 0
                    
                    logger.info("开始查找评论数和评论链接...")
                    
                    # 记录当前帖子的HTML结构，用于调试
                    if self.debug:
                        post_html = post_element.inner_html()
                        logger.debug(f"帖子元素HTML前500个字符: {post_html[:500]}...")
                    
                    # ======= 方法1: 在最近的父级DOM中查找评论链接 =======
                    logger.info("方法1: 在父级DOM结构中查找评论链接")
                    
                    # 在帖子元素中先找兄弟元素
                    try:
                        # 先查找.subject-bottom-box容器，它通常包含评论链接
                        parent_el_obj = post_element.evaluate("""(element) => {
                            // 先尝试获取自身所在的item容器
                            const parent = element.closest('.telegraph-content-box');
                            return parent;
                        }""")
                        
                        if parent_el_obj:
                            logger.debug("找到父级容器telegraph-content-box")
                            
                            # 将JavaScript对象转换为ElementHandle对象
                            parent_el = None
                            try:
                                # 使用JavaScript获取父元素的选择器路径
                                selector_path = post_element.evaluate("""(element) => {
                                    // 获取父容器
                                    const parent = element.closest('.telegraph-content-box');
                                    if (!parent) return null;
                                    
                                    // 生成唯一选择器
                                    let path = '';
                                    if (parent.id) {
                                        path = '#' + parent.id;
                                    } else if (parent.className) {
                                        path = '.' + parent.className.split(' ')[0];
                                    } else {
                                        path = parent.tagName.toLowerCase();
                                    }
                                    return path;
                                }""")
                                
                                if selector_path:
                                    # 使用选择器路径在页面中查找元素
                                    parent_el = self.page.query_selector(selector_path)
                                    logger.info(f"使用选择器路径 '{selector_path}' 找到父元素")
                            except Exception as inner_e:
                                logger.warning(f"转换为ElementHandle时出错: {inner_e}")
                            
                            # 在父容器中直接查找评论链接
                            if parent_el:
                                comment_links = parent_el.query_selector_all("a[href*='/detail/']")
                                
                                for link in comment_links:
                                    href = link.get_attribute("href") or ""
                                    text = link.inner_text().strip()
                                    
                                    # 检查是否包含"评论"文本
                                    if "评论" in text:
                                        logger.info(f"在父容器中找到评论链接: {href}, 文本='{text}'")
                                        
                                        # 提取评论数
                                        count_match = re.search(r'评论.*?(\d+)', text) or re.search(r'\((\d+)\)', text)
                                        if count_match:
                                            found_count = int(count_match.group(1))
                                            logger.info(f"从链接文本中提取到评论数: {found_count}")
                                            
                                            if found_count > 0:
                                                comment_count = found_count
                                                detail_link = link
                                                break
                            else:
                                logger.warning("无法获取父元素的ElementHandle对象")
                    except Exception as e:
                        logger.warning(f"在父容器中查找评论链接时出错: {e}")
                        if self.debug:
                            logger.debug(traceback.format_exc())
                    
                    # ======= 方法2: 直接在页面中查找与当前帖子关联的评论链接 =======
                    if not detail_link:
                        logger.info("方法2: 在页面中查找与当前帖子相关的评论链接")
                        
                        try:
                            # 获取帖子标题，用于标识
                            post_title = "未知标题"
                            title_el = post_element.query_selector("strong")
                            if title_el:
                                post_title = title_el.inner_text().strip()
                                post_title = post_title[:30] if len(post_title) > 30 else post_title
                                logger.info(f"帖子标题: {post_title}")
                            
                            # 获取帖子在页面中的位置
                            post_pos = post_element.evaluate("""(element) => {
                                const rect = element.getBoundingClientRect();
                                return {top: rect.top, bottom: rect.bottom, left: rect.left, right: rect.right};
                            }""")
                            
                            # 查找所有评论链接
                            comment_links = self.page.query_selector_all("a[href*='/detail/']")
                            logger.info(f"在页面中找到 {len(comment_links)} 个包含'/detail/'的链接")
                            
                            # 筛选含有"评论"文本的链接
                            valid_links = []
                            for link in comment_links:
                                text = link.inner_text().strip()
                                if "评论" in text and ("(" in text or "（" in text):
                                    valid_links.append(link)
                            
                            logger.info(f"其中 {len(valid_links)} 个链接包含'评论'文本")
                            
                            # 如果有多个链接，选择位置最接近当前帖子的一个
                            if valid_links:
                                best_link = None
                                min_distance = float('inf')
                                
                                for link in valid_links:
                                    try:
                                        # 获取链接在页面中的位置
                                        link_pos = link.evaluate("""(element) => {
                                            const rect = element.getBoundingClientRect();
                                            return {top: rect.top, bottom: rect.bottom, left: rect.left, right: rect.right};
                                        }""")
                                        
                                        # 计算与帖子的垂直距离
                                        v_distance = abs(link_pos['top'] - post_pos['bottom'])
                                        
                                        # 链接应该在帖子下方且不太远
                                        if link_pos['top'] >= post_pos['top'] and v_distance < min_distance:
                                            best_link = link
                                            min_distance = v_distance
                                    except Exception as e:
                                        logger.warning(f"计算链接位置时出错: {e}")
                                
                                # 如果找到最接近的链接
                                if best_link:
                                    href = best_link.get_attribute("href") or ""
                                    text = best_link.inner_text().strip()
                                    logger.info(f"找到最匹配的评论链接: {href}, 文本='{text}'")
                                    
                                    # 提取评论数
                                    count_match = re.search(r'评论.*?(\d+)', text) or re.search(r'\((\d+)\)', text)
                                    if count_match:
                                        found_count = int(count_match.group(1))
                                        logger.info(f"从链接文本中提取到评论数: {found_count}")
                                        
                                        if found_count > 0:
                                            comment_count = found_count
                                            detail_link = best_link
                                            logger.info(f"找到与帖子'{post_title}'匹配的评论链接，评论数={found_count}")
                        except Exception as e:
                            logger.warning(f"在页面中查找评论链接时出错: {e}")
                            if self.debug:
                                logger.debug(traceback.format_exc())
                    
                    # 设置评论数量
                    result["comment_count"] = comment_count
                    
                    # 只有当评论数大于0且找到链接时才获取评论
                    if detail_link and comment_count > 0:
                        # 获取详情页URL
                        detail_url = detail_link.get_attribute("href")
                        if not detail_url:
                            logger.warning("链接没有href属性")
                            return result
                        
                        # 处理相对URL
                        if not detail_url.startswith("http"):
                            detail_url = urljoin(self.base_url, detail_url)
                            logger.info(f"转换为绝对URL: {detail_url}")
                        
                        logger.info(f"评论数 > 0 ({comment_count})，导航到详情页获取评论: {detail_url}")
                        
                        # 导航到详情页并提取评论 - 使用新页面避免导航问题
                        comments = self.extract_comments_for_post(detail_url)
                        result["comments"] = comments
                        logger.info(f"获取到 {len(comments)} 条评论")
                        
                    else:
                        # 没有评论或找不到链接时设置空评论列表
                        result["comments"] = []
                        if comment_count > 0:
                            logger.warning(f"找到 {comment_count} 条评论但未找到详情链接")
                        else:
                            logger.info("评论数为0或未找到评论数，跳过详情页访问")
                except Exception as e:
                    logger.warning(f"处理评论时出错: {e}")
                    result["comments"] = []
                    result["comment_count"] = 0
                    if self.debug:
                        logger.error(traceback.format_exc())
            
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
    
    def extract_comments_for_post(self, post_url: str) -> List[Dict[str, Any]]:
        """从帖子详情页提取评论，使用新页面避免导航问题"""
        logger.info(f"提取帖子评论，URL: {post_url}")
        
        # 创建新页面打开评论详情
        new_page = None
        comments = []
        
        try:
            # 创建新页面
            new_page = self.context.new_page()
            
            # 在新页面中打开评论详情
            response = new_page.goto(post_url, wait_until="domcontentloaded", timeout=30000)
            if not response:
                logger.error(f"导航到详情页失败: {post_url}")
                return []
            
            status = response.status
            logger.info(f"页面响应状态码: {status}")
            
            # 等待页面加载完成
            new_page.wait_for_load_state("networkidle", timeout=30000)
            logger.info("页面加载完成")
            
            # 调试模式下输出页面内容，但限制内容长度
            if self.debug:
                html = new_page.content()
                logger.debug(f"详情页HTML片段: {html[:500]}...")
            
            # ===================== 查找评论区域 =====================
            logger.info("查找评论区域...")
            
            # 1. 首先尝试定位整个评论容器
            comment_container = None
            comment_container_selectors = [
                "div.new-comment",  # 根据截图提供的源码
                "div.evaluate-container", 
                "div.comment-container"
            ]
            
            for selector in comment_container_selectors:
                try:
                    container = new_page.query_selector(selector)
                    if container:
                        logger.debug(f"找到评论容器: '{selector}'")
                        comment_container = container
                        break
                except Exception as e:
                    logger.warning(f"查找评论容器出错: {e}")
            
            # 2. 在评论容器内查找评论标题
            comment_title = None
            if comment_container:
                comment_title_selectors = [
                    "div.new-comment-header",  # 根据截图提供的源码
                    "div.f-l.f-s-18.f-w-b",
                    "div:has-text('评论')"
                ]
                
                for selector in comment_title_selectors:
                    try:
                        title_el = comment_container.query_selector(selector)
                        if title_el:
                            title_text = title_el.inner_text().strip()
                            # 验证标题是否符合"评论 (数字)"格式
                            if "评论" in title_text:
                                comment_title = title_el
                                # 截断日志内容，避免输出过长
                                max_title_length = 30
                                truncated_title = (title_text[:max_title_length] + "...") if len(title_text) > max_title_length else title_text
                                logger.info(f"找到评论区标题: '{truncated_title}'")
                                break
                    except Exception as e:
                        logger.warning(f"查找评论标题出错: {e}")
            
            # 3. 如果无法找到评论容器或标题，尝试直接在主内容区域查找
            if not comment_container:
                logger.info("未找到评论容器，尝试在主内容区域查找")
                
                # 尝试定位主内容区域
                main_content_selectors = [
                    "div.article-detail", 
                    "div.detail-container", 
                    "div.main-content"
                ]
                
                main_content = None
                for selector in main_content_selectors:
                    try:
                        content = new_page.query_selector(selector)
                        if content:
                            main_content = content
                            logger.info(f"找到主内容区域: '{selector}'")
                            break
                    except Exception as e:
                        logger.warning(f"查找主内容区域出错: {e}")
                
                # 在主内容区域中查找评论标题
                if main_content:
                    comment_title_selectors = [
                        "div:has-text('评论') >> nth=0",
                        "h2:has-text('评论')",
                        ".comment-title",
                        ".evaluate-title"
                    ]
                    
                    for selector in comment_title_selectors:
                        try:
                            title_el = main_content.query_selector(selector)
                            if title_el:
                                title_text = title_el.inner_text().strip()
                                if "评论" in title_text and len(title_text) < 50:  # 避免匹配到导航文本
                                    comment_title = title_el
                                    logger.info(f"在主内容区域找到评论区标题: '{title_text}'")
                                    break
                        except Exception as e:
                            logger.warning(f"在主内容区域查找评论标题出错: {e}")
            
            # 4. 直接查找评论项列表 - 根据截图中的新DOM结构
            comment_items = []
            
            # 根据截图提供的DOM结构查找评论项
            comment_body_selectors = [
                "div.clearfix.b-c-e6e7ea.new-comment-body",  # 根据截图提供的源码
                "div[class*='new-comment-body']",
                "div[class*='comment-body']",
                "div[class*='comment-detail']"
            ]
            
            # 4.1 如果找到了评论容器，在容器内查找评论项
            if comment_container:
                for selector in comment_body_selectors:
                    try:
                        items = comment_container.query_selector_all(selector)
                        if items and len(items) > 0:
                            logger.info(f"在评论容器中使用选择器 '{selector}' 找到 {len(items)} 条评论")
                            comment_items = items
                            break
                    except Exception as e:
                        logger.warning(f"在评论容器中查找评论项出错: {e}")
            
            # 4.2 如果在评论容器中未找到评论项，在整个页面中查找
            if not comment_items:
                logger.info("在评论容器中未找到评论项，尝试在整个页面查找")
                for selector in comment_body_selectors:
                    try:
                        items = new_page.query_selector_all(selector)
                        if items and len(items) > 0:
                            logger.info(f"在页面中使用选择器 '{selector}' 找到 {len(items)} 条评论")
                            comment_items = items
                            break
                    except Exception as e:
                        logger.warning(f"在页面中查找评论项出错: {e}")
            
            # 5. 如果没有找到评论项，尝试根据评论内容选择器查找
            if not comment_items:
                logger.info("未找到评论body，尝试根据评论内容选择器查找")
                content_selectors = [
                    "div.m-b-15.f-s-14.c-383838.new-comment-content",  # 根据截图提供的源码
                    ".c-383838.new-comment-content",
                    "div[class*='comment-content']"
                ]
                
                for selector in content_selectors:
                    try:
                        items = new_page.query_selector_all(selector)
                        if items and len(items) > 0:
                            # 获取每个内容元素的父元素作为评论项
                            parent_items = []
                            for item in items:
                                parent = item.evaluate("el => el.parentElement")
                                if parent:
                                    parent_items.append(parent)
                            
                            if parent_items:
                                logger.info(f"通过内容选择器 '{selector}' 找到 {len(parent_items)} 条评论")
                                comment_items = parent_items
                                break
                    except Exception as e:
                        logger.warning(f"使用内容选择器 '{selector}' 查找评论项出错: {e}")
            
            # 6. 如果仍然找不到评论项，使用用户头像查找
            if not comment_items:
                logger.info("尝试通过用户头像查找评论")
                avatar_selectors = [
                    "div.f-l.p-r.observer-photo",  # 根据截图提供的源码
                    "div[class*='observer-photo']",
                    "div[style*='background-image']",
                    ".avatar"
                ]
                
                for selector in avatar_selectors:
                    try:
                        avatars = new_page.query_selector_all(selector)
                        if avatars and len(avatars) > 0:
                            logger.info(f"使用选择器 '{selector}' 找到 {len(avatars)} 个用户头像")
                            
                            # 对于每个头像，尝试获取其父元素的父元素作为评论项
                            parent_items = []
                            for avatar in avatars:
                                # 获取父元素的父元素，因为通常结构是 avatar -> name/user container -> comment item
                                container = avatar.evaluate("el => el.parentElement && el.parentElement.parentElement")
                                if container:
                                    parent_items.append(container)
                            
                            if parent_items:
                                logger.info(f"从用户头像找到 {len(parent_items)} 条评论项")
                                comment_items = parent_items
                                break
                    except Exception as e:
                        logger.warning(f"通过用户头像查找评论项出错: {e}")
            
            # ===================== 提取评论内容 =====================
            comments = []
            for i, item in enumerate(comment_items):
                try:
                    # 输出评论项HTML用于调试，限制长度
                    if self.debug:
                        item_html = item.inner_html()
                        logger.debug(f"评论项 #{i+1} HTML片段: {item_html[:200]}...")
                    
                    # 提取用户名 - 根据截图中的DOM结构
                    username = "未知用户"
                    username_selectors = [
                        "div.w-100p.o-h.new-comment-name-box",  # 根据截图提供的源码
                        ".new-comment-name-box",
                        ".username",
                        ".user-name",
                        "div[class*='user']",
                        "div[class*='name']"
                    ]
                    
                    for selector in username_selectors:
                        try:
                            el = item.query_selector(selector)
                            if el:
                                text = el.inner_text().strip()
                                if text and len(text) > 0:
                                    # 清理用户名文本，去除时间和地区信息
                                    # 移除包含"小时前"、"分钟前"、"天前"的部分
                                    time_patterns = [r'\d+\s*小时前', r'\d+\s*分钟前', r'\d+\s*天前']
                                    for pattern in time_patterns:
                                        text = re.sub(pattern, '', text).strip()
                                    
                                    # 如果有"·"符号，只取前面部分作为用户名
                                    if '·' in text:
                                        text = text.split('·')[0].strip()
                                    
                                    username = text
                                    if self.debug:
                                        logger.debug(f"找到用户名: {username}")
                                    break
                        except Exception as e:
                            if self.debug:
                                logger.debug(f"提取用户名时出错: {e}")
                    
                    # 提取评论内容 - 根据截图中的DOM结构
                    content = ""
                    content_selectors = [
                        "div.m-b-15.f-s-14.c-383838.new-comment-content",  # 根据截图提供的源码
                        ".new-comment-content",
                        ".comment-content",
                        "div[class*='content']",
                        "div[class*='text']"
                    ]
                    
                    for selector in content_selectors:
                        try:
                            el = item.query_selector(selector)
                            if el:
                                text = el.inner_text().strip()
                                if text and len(text) > 0:
                                    content = text
                                    # 截断日志输出避免过长，只在debug模式下输出
                                    if self.debug:
                                        content_preview = content[:30] + "..." if len(content) > 30 else content
                                        logger.debug(f"找到评论内容: {content_preview}")
                                    break
                        except Exception as e:
                            if self.debug:
                                logger.debug(f"提取评论内容时出错: {e}")
                    
                    # 如果没找到内容，使用整个评论项的文本
                    if not content:
                        content = item.inner_text().strip()
                        # 移除用户名，避免重复
                        if username != "未知用户" and content.startswith(username):
                            content = content[len(username):].strip()
                        # 截断日志输出避免过长，只在debug模式下输出
                        if self.debug:
                            content_preview = content[:30] + "..." if len(content) > 30 else content
                            logger.debug(f"使用整体文本作为内容: {content_preview}")
                    
                    # 提取评论时间和地点信息 - 根据截图提供的源码
                    time_text = ""
                    location_text = ""
                    
                    # 尝试找到时间和地点信息
                    info_selectors = [
                        "span:has-text('分钟前')",
                        "span:has-text('小时前')",
                        "span:has-text('天前')",
                        "span:has-text(':')",
                        "span[class*='time']"
                    ]
                    
                    for selector in info_selectors:
                        try:
                            el = item.query_selector(selector)
                            if el:
                                text = el.inner_text().strip()
                                if text and (any(keyword in text for keyword in ['分钟前', '小时前', '天前']) or ':' in text):
                                    time_text = text
                                    if self.debug:
                                        logger.debug(f"找到时间信息: {time_text}")
                                    break
                        except Exception as e:
                            if self.debug:
                                logger.debug(f"提取时间信息时出错: {e}")
                    
                    # 尝试找到地区信息
                    location_selectors = [
                        "span:has-text('·')",
                        "span[class*='location']"
                    ]
                    
                    for selector in location_selectors:
                        try:
                            el = item.query_selector(selector)
                            if el:
                                text = el.inner_text().strip()
                                if text and "·" in text:
                                    parts = text.split("·")
                                    if len(parts) > 1:
                                        location_text = parts[1].strip()
                                        if self.debug:
                                            logger.debug(f"找到地区信息: {location_text}")
                                        break
                        except Exception as e:
                            if self.debug:
                                logger.debug(f"提取地区信息时出错: {e}")
                    
                    # 解析时间文本
                    from datetime import datetime, timedelta
                    
                    now = datetime.now()
                    date_str = now.strftime("%Y-%m-%d")
                    time_str = now.strftime("%H:%M:%S")
                    
                    if time_text:
                        try:
                            # 匹配相对时间表达式
                            minutes_ago = re.search(r'(\d+)\s*分钟前', time_text)
                            hours_ago = re.search(r'(\d+)\s*小时前', time_text)
                            days_ago = re.search(r'(\d+)\s*天前', time_text)
                            
                            if minutes_ago:
                                mins = int(minutes_ago.group(1))
                                comment_time = now - timedelta(minutes=mins)
                                date_str = comment_time.strftime("%Y-%m-%d")
                                time_str = comment_time.strftime("%H:%M:%S")
                            elif hours_ago:
                                hrs = int(hours_ago.group(1))
                                comment_time = now - timedelta(hours=hrs)
                                date_str = comment_time.strftime("%Y-%m-%d")
                                time_str = comment_time.strftime("%H:%M:%S")
                            elif days_ago:
                                days = int(days_ago.group(1))
                                comment_time = now - timedelta(days=days)
                                date_str = comment_time.strftime("%Y-%m-%d")
                                time_str = comment_time.strftime("%H:%M:%S")
                            else:
                                # 尝试提取具体时间
                                time_match = re.search(r'(\d{1,2}:\d{1,2})', time_text)
                                if time_match:
                                    time_str = time_match.group(1)
                        except Exception as e:
                            if self.debug:
                                logger.debug(f"解析时间文本出错: {e}")
                    
                    # 创建评论对象
                    comment = {
                        "username": username,
                        "content": content,
                        "date": date_str,
                        "time": time_str,
                        "location": location_text,
                        "raw_time_text": time_text
                    }
                    
                    comments.append(comment)
                    logger.info(f"提取评论 #{i+1}: 用户={username}, 日期={date_str}, 时间={time_str}")
                
                except Exception as e:
                    logger.warning(f"提取评论 #{i+1} 时出错: {e}")
                    if self.debug:
                        logger.debug(traceback.format_exc())
            
            if not comments:
                logger.warning("未能从详情页提取到任何评论内容")
            
            return comments
        
        except Exception as e:
            log_error(logger, f"提取评论时出错: {e}", e, self.debug)
            return []
        finally:
            # 确保无论如何都关闭新页面
            try:
                if new_page:
                    new_page.close()
                    logger.info("关闭评论详情页")
            except Exception as e:
                logger.warning(f"关闭评论详情页时出错: {e}")
    
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
                    # 跳过不符合日期要求的帖子的详细处理
                    if post_info.get("is_before_cutoff", False):
                        logger.info(f"帖子 '{post_info.get('title', '未知标题')[:30]}...' 早于截止日期，跳过详细处理")
                        post_result = {
                            "title": post_info.get("title", "未知标题"),
                            "date": post_info.get("date", ""),
                            "time": post_info.get("time", ""),
                            "section": section,
                            "comments": [],
                            "comment_count": 0,
                            "has_comments": False,
                            "is_before_cutoff": True
                        }
                        results.append(post_result)
                        continue
                    
                    # 获取评论信息
                    comments = post_info.get("comments", [])
                    comment_count = post_info.get("comment_count", 0)
                    
                    # 构建帖子信息
                    has_comments = len(comments) > 0
                    post_result = {
                        "title": post_info.get("title", "未知标题"),
                        "date": post_info.get("date", ""),
                        "time": post_info.get("time", ""),
                        "section": section,
                        "comments": comments,
                        "comment_count": comment_count,
                        "has_comments": has_comments
                    }
                    
                    results.append(post_result)
                    
                except Exception as e:
                    logger.error(f"处理帖子 '{post_info.get('title', '未知标题')}' 时出错: {e}")
                    if self.debug:
                        logger.error(traceback.format_exc())
                        
            return results
            
        except Exception as e:
            log_error(logger, f"爬取 '{section}' 版块时出错", e, self.debug)
            return []
    
    def wait_for_network_idle(self, timeout: int = 5000):
        """等待网络请求完成"""
        self.page.wait_for_load_state("networkidle", timeout=timeout)
    
    def _navigate_to_telegraph(self) -> bool:
        """导航到Telegraph主页"""
        try:
            # 使用常量替换硬编码的电报URL
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

    def extract_comments_for_post_element(self, post_element, post_data):
        """
        提取帖子的评论信息
        
        Args:
            post_element: 帖子元素
            post_data: 帖子数据字典
            
        Returns:
            List[str]: 评论列表
        """
        # 检查帖子日期是否符合要求，不符合则跳过评论提取
        if not self.is_valid_post_date(post_data.get('date')):
            post_data['comments_data'] = []
            logger.debug(f"帖子 '{post_data.get('title', '未知标题')}' 日期 '{post_data.get('date', '未知日期')}' 不符合要求，跳过评论提取")
            return []

        # 如果已经有评论数据，直接返回
        if post_data.get('comments_data') is not None:
            logger.debug(f"帖子 '{post_data.get('title', '未知标题')}' 已有评论数据，跳过再次提取")
            return [comment.get('content', '') for comment in post_data.get('comments_data', [])]
        
        comments = []
        comment_link = None
        
        try:
            # 查找评论链接
            comment_link = self.find_comment_link(post_element)
            
            if not comment_link:
                post_data['comments_data'] = []
                logger.debug(f"未找到评论链接，帖子：'{post_data.get('title', '未知标题')}'")
                return []
            
            logger.info(f"找到评论链接: {comment_link}")
            
            # 创建新页面打开评论详情
            new_page = None
            try:
                context = self.page.context
                new_page = context.new_page()
                
                # 设置超时并访问评论页面
                new_page.set_default_timeout(30000)
                new_page.goto(comment_link, wait_until="domcontentloaded")
                
                # 等待页面完全加载
                new_page.wait_for_load_state("networkidle", timeout=10000)
                
                # 等待页面渲染完成
                new_page.wait_for_timeout(2000)
                
                # 查找评论部分标题
                comment_title_selectors = [
                    "//div[contains(text(), '评论') and contains(@class, 'title')]",
                    "//h2[contains(text(), '评论')]",
                    "//h3[contains(text(), '评论')]",
                    "//div[contains(text(), '评论')]"
                ]
                
                comment_title = None
                for selector in comment_title_selectors:
                    if new_page.query_selector(selector):
                        comment_title = new_page.query_selector(selector)
                        break
                
                if comment_title:
                    logger.debug(f"找到评论标题: {comment_title.inner_text()}")
                else:
                    logger.debug("未找到评论标题")
                
                # 尝试多种方法查找评论列表
                comments_data = []
                
                # 方法1: 通过用户头像查找评论
                avatar_selectors = [
                    "//div[contains(@class, 'avatar')]",
                    "//img[contains(@class, 'avatar')]",
                    "//div[contains(@class, 'user')]/img"
                ]
                
                found_avatars = False
                for selector in avatar_selectors:
                    avatar_elements = new_page.query_selector_all(selector)
                    if avatar_elements and len(avatar_elements) > 0:
                        logger.debug(f"通过头像找到 {len(avatar_elements)} 个评论元素")
                        found_avatars = True
                        
                        for avatar in avatar_elements:
                            try:
                                # 查找用户名和评论内容
                                parent = avatar.evaluate("node => node.parentElement")
                                if not parent:
                                    parent = avatar
                                    
                                # 寻找用户名
                                username_element = parent.query_selector("//span[contains(@class, 'name')] | //div[contains(@class, 'name')]")
                                username = username_element.inner_text().strip() if username_element else "未知用户"
                                
                                # 清理用户名
                                username = self.clean_username(username)
                                
                                # 寻找评论内容 - 在用户名元素的兄弟元素中查找
                                comment_content_element = parent.query_selector("//div[contains(@class, 'content')] | //div[contains(@class, 'text')]")
                                comment_content = comment_content_element.inner_text().strip() if comment_content_element else ""
                                
                                if comment_content:
                                    comments.append(comment_content)
                                    comments_data.append({
                                        "username": username,
                                        "content": comment_content
                                    })
                                    logger.debug(f"提取到用户 '{username}' 的评论: {comment_content[:30]}...")
                            except Exception as e:
                                logger.debug(f"处理单个评论时出错: {str(e)}")
                        
                        break  # 如果成功找到一种方法，就不再尝试其他方法
                
                # 方法2: 直接查找评论容器
                if not found_avatars:
                    comment_selectors = [
                        "//div[contains(@class, 'comment-item')]",
                        "//div[contains(@class, 'comment') and contains(@class, 'item')]",
                        "//li[contains(@class, 'comment')]"
                    ]
                    
                    for selector in comment_selectors:
                        comment_elements = new_page.query_selector_all(selector)
                        if comment_elements and len(comment_elements) > 0:
                            logger.debug(f"通过评论容器找到 {len(comment_elements)} 个评论元素")
                            
                            for comment_el in comment_elements:
                                try:
                                    # 尝试提取用户名
                                    username_element = comment_el.query_selector(".name, .user, .username")
                                    username = username_element.inner_text().strip() if username_element else "未知用户"
                                    
                                    # 清理用户名
                                    username = self.clean_username(username)
                                    
                                    # 尝试提取评论内容
                                    content_element = comment_el.query_selector(".content, .text, .comment-text")
                                    comment_content = content_element.inner_text().strip() if content_element else comment_el.inner_text().strip()
                                    
                                    if comment_content:
                                        comments.append(comment_content)
                                        comments_data.append({
                                            "username": username,
                                            "content": comment_content
                                        })
                                        logger.debug(f"提取到用户 '{username}' 的评论: {comment_content[:30]}...")
                                except Exception as e:
                                    logger.debug(f"处理单个评论容器时出错: {str(e)}")
                            
                            break  # 找到有效的评论后退出循环
                
                # 方法3: 提取所有文本内容作为评论
                if not comments and comment_title:
                    try:
                        # 获取评论标题后面的所有文本
                        comment_section = comment_title.evaluate("node => {" +
                            "let nextElement = node.nextElementSibling;" +
                            "let text = '';" +
                            "while (nextElement) {" +
                            "  text += nextElement.innerText + '\\n';" +
                            "  nextElement = nextElement.nextElementSibling;" +
                            "}" +
                            "return text;" +
                        "}")
                        
                        if comment_section and len(comment_section.strip()) > 0:
                            # 简单按行分割
                            comment_lines = [line.strip() for line in comment_section.split('\n') if line.strip()]
                            
                            # 过滤掉太短的行
                            valid_comments = [line for line in comment_lines if len(line) > 5]
                            
                            if valid_comments:
                                logger.debug(f"通过文本提取找到 {len(valid_comments)} 个可能的评论")
                                
                                # 简单假设: 第一行是用户名，第二行是评论内容，以此类推
                                for i in range(0, len(valid_comments), 2):
                                    if i + 1 < len(valid_comments):
                                        username = self.clean_username(valid_comments[i])
                                        comment_content = valid_comments[i + 1]
                                        
                                        comments.append(comment_content)
                                        comments_data.append({
                                            "username": username,
                                            "content": comment_content
                                        })
                                        logger.debug(f"提取到用户 '{username}' 的评论: {comment_content[:30]}...")
                    except Exception as e:
                        logger.debug(f"尝试通过文本提取评论时出错: {str(e)}")
                
                if comments:
                    logger.info(f"成功提取 {len(comments)} 条评论")
                    
                # 保存评论数据到帖子中
                post_data['comments_data'] = comments_data
                
            except Exception as e:
                logger.error(f"提取评论详情时出错: {str(e)}")
            finally:
                # 确保关闭新页面
                if new_page:
                    try:
                        new_page.close()
                        logger.debug("已关闭评论详情页面")
                    except Exception as e:
                        logger.error(f"关闭评论页面时出错: {str(e)}")
                    
        except Exception as e:
            logger.error(f"提取评论过程中出错: {str(e)}")
            post_data['comments_data'] = []
        
        return comments

    def clean_username(self, username):
        """清理用户名文本"""
        if not username:
            return "未知用户"
        
        # 移除特殊字符
        username = re.sub(r'[^\w\s\u4e00-\u9fff]', '', username)
        
        # 移除可能的常见标签或状态文本
        remove_patterns = ['发布者', '作者', '创建', '回复', '用户']
        for pattern in remove_patterns:
            username = username.replace(pattern, '')
        
        # 移除多余空格
        username = ' '.join(username.split())
        
        # 限制长度
        if len(username) > 20:
            username = username[:20]
        
        # 如果清理后为空，返回默认用户名
        return username.strip() if username.strip() else "未知用户"

    def is_valid_post_date(self, post_date):
        """
        检查帖子日期是否在有效范围内
        
        Args:
            post_date: 帖子日期字符串
            
        Returns:
            bool: 是否是有效日期
        """
        if not post_date or not self.cutoff_date:
            return True
        
        try:
            # 转换帖子日期字符串为datetime对象
            if isinstance(post_date, str):
                # 处理常见的日期格式
                formats = [
                    '%Y-%m-%d %H:%M:%S',
                    '%Y-%m-%d %H:%M',
                    '%Y/%m/%d %H:%M:%S',
                    '%Y/%m/%d %H:%M',
                    '%Y-%m-%d',
                    '%Y/%m/%d'
                ]
                
                post_datetime = None
                for fmt in formats:
                    try:
                        post_datetime = datetime.strptime(post_date, fmt)
                        break
                    except ValueError:
                        continue
                    
                if not post_datetime:
                    logger.warning(f"无法解析帖子日期: {post_date}")
                    return True  # 如果无法解析，默认为有效
            else:
                post_datetime = post_date
            
            # 比较日期
            return post_datetime >= self.cutoff_date
        except Exception as e:
            logger.error(f"检查帖子日期有效性时出错: {str(e)}")
            return True  # 如果出错，默认为有效 

    def _extract_comments(self, post_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        从帖子结果中提取评论
        
        Args:
            post_result: 帖子数据
            
        Returns:
            评论列表
        """
        # 如果帖子数据中已有评论，直接返回
        if "comments" in post_result and post_result["comments"]:
            return post_result["comments"]
        
        # 如果有评论数量但没有评论内容，尝试从评论链接获取
        if post_result.get("comment_count", 0) > 0 and post_result.get("url"):
            try:
                comments = self.extract_comments_for_post(post_result["url"])
                return comments
            except Exception as e:
                logger.warning(f"提取评论失败: {e}")
                return []
        
        # 默认返回空列表
        return []

    def _init_analyzers(self):
        """
        初始化需要的各种分析器实例
        """
        pass

    def _process_post_result(self, post_result: Dict[str, Any], is_expired: bool = False) -> Dict[str, Any]:
        """
        处理帖子结果，添加评论
        
        Args:
            post_result: 帖子数据
            is_expired: 是否已过期
            
        Returns:
            处理后的帖子数据
        """
        # 如果已过期，则设置为过期
        if is_expired:
            post_result["has_comments"] = False
            post_result["comments"] = []
            
            if self.debug:
                self.logger.info(f"帖子已过期，标题：{post_result.get('title', '未知')}")
            
            return post_result
        
        # 获取评论（如果可能）
        comments = self._extract_comments(post_result)
        post_result["has_comments"] = len(comments) > 0
        post_result["comments"] = comments
        
        return post_result