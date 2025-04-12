# -*- coding: utf-8 -*-
import logging
import time
import datetime
import os
from typing import List, Dict, Any, Tuple
import re

from chose_one_agent.scrapers.base_scraper import BaseScraper
from chose_one_agent.utils.helpers import parse_datetime, is_before_cutoff, extract_date_time, is_in_date_range
from chose_one_agent.analyzers.sentiment_analyzer import SentimentAnalyzer

# 配置日志
logger = logging.getLogger(__name__)


class TelegraphScraper(BaseScraper):
    """
    财经网站的电报爬虫类，用于抓取和分析电报内容
    """

    def __init__(self, cutoff_date, headless=True, debug=False, section="看盘"):
        """
        初始化电报爬虫

        Args:
            cutoff_date: 截止日期，爬虫只会获取该日期到当前时间范围内的电报，早于或晚于此范围的电报将被忽略
            headless: 是否使用无头模式运行浏览器
            debug: 是否启用调试模式
            section: 默认抓取的板块，如"看盘"或"公司"
        """
        super().__init__(cutoff_date, headless)
        self.sentiment_analyzer = SentimentAnalyzer()
        self.debug = debug
        self.section = section
        # 创建调试目录
        os.makedirs("debug", exist_ok=True)

    def get_comments(self, post_element) -> List[str]:
        """
        获取帖子的评论

        Args:
            post_element: 帖子的DOM元素

        Returns:
            评论内容列表
        """
        comments = []

        # 检查元素是否为None
        if post_element is None:
            logger.warning("无法获取评论：帖子元素为None")
            return comments

        try:
            # 根据截图中的结构，找到评论按钮并点击
            comment_selectors = [
                "span.comment", "div.comment", ".comment", "[class*='comment']",
                "span[class*='comment']", "div[class*='comment']", ".comments-count"
            ]

            comment_btn = None
            for selector in comment_selectors:
                comment_btn = post_element.query_selector(selector)
                if comment_btn:
                    logger.debug(f"找到评论按钮，使用选择器: {selector}")
                    break

            if comment_btn:
                # 点击评论按钮进入评论页面
                comment_btn.click()
                self.page.wait_for_load_state("networkidle")
                time.sleep(2)

                # 根据截图中可能的评论区结构提取评论内容
                comment_content_selectors = [
                    ".comment-item", ".comment-content", ".comment-text",
                    "[class*='comment-item']", "[class*='comment-content']",
                    "[class*='comment-text']", ".comment-body", ".comment p"
                ]

                for selector in comment_content_selectors:
                    comment_elements = self.page.query_selector_all(selector)
                    if comment_elements and len(comment_elements) > 0:
                        logger.info(
                            f"找到{len(comment_elements)}个评论元素，使用选择器: {selector}")

                        for element in comment_elements:
                            comment_text = element.inner_text().strip()
                            if comment_text:
                                # 过滤掉可能的日期、用户名等信息
                                if len(comment_text) > 2 and not re.match(r'^\d{1,2}:\d{2}$', comment_text):
                                    comments.append(comment_text)
                                    logger.debug(f"提取的评论: {comment_text}")

                        if comments:
                            break

                # 返回到列表页面
                self.page.go_back()
                self.page.wait_for_load_state("networkidle")
                time.sleep(1)
            else:
                logger.info("未找到评论按钮")
        except Exception as e:
            logger.error(f"获取评论时出错: {e}")
            logger.error(traceback.format_exc())

        logger.info(f"共获取到{len(comments)}条评论")
        return comments

    def analyze_post(self, post_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        分析帖子信息，提取评论并进行情感分析

        Args:
            post_info: 包含帖子信息的字典

        Returns:
            添加了情感分析结果的帖子信息字典
        """
        result = {
            "title": post_info["title"],
            "date": post_info["date"],
            "time": post_info["time"],
            "comment_count": post_info["comment_count"]
        }

        # 如果评论数为0或元素为None，只记录标题内容
        if post_info["comment_count"] == 0 or post_info["element"] is None:
            logger.info(
                f"帖子 '{post_info['title']}' 评论数为{post_info['comment_count']}或没有关联元素，记录标题内容")
            result["sentiment"] = "中性"  # 默认情感为中性
            result["comments"] = []
        else:
            # 如果评论数不为0且有元素，获取评论并进行情感分析
            logger.info(
                f"帖子 '{post_info['title']}' 评论数为{post_info['comment_count']}，获取评论并进行情感分析")

            try:
                comments = self.get_comments(post_info["element"])

                if comments:
                    # 进行情感分析
                    sentiment = self.sentiment_analyzer.analyze_comments(
                        comments)
                    logger.info(f"评论情感分析结果: {sentiment}")

                    result["sentiment"] = sentiment
                    result["comments"] = comments
                else:
                    # 如果实际获取不到评论，也设为中性
                    logger.warning(
                        f"帖子声称有{post_info['comment_count']}条评论，但实际获取不到评论内容")
                    result["sentiment"] = "中性"
                    result["comments"] = []
            except Exception as e:
                logger.error(f"获取或分析评论时出错: {e}")
                logger.error(traceback.format_exc())
                result["sentiment"] = "中性"
                result["comments"] = []

        return result

    def navigate_to_telegraph_section(self, section: str) -> bool:
        """
        导航到电报下的特定板块

        Args:
            section: 要导航到的板块，如"公司"或"看盘"

        Returns:
            是否成功导航到指定板块
        """
        try:
            # 第一步：导航到首页
            logger.info("导航到网站首页")
            self.page.goto(self.base_url)
            self.page.wait_for_load_state("networkidle")
            time.sleep(2)

            # 第二步：点击顶部导航栏中的"电报"按钮
            logger.info("尝试点击顶部导航栏中的'电报'按钮")

            # 尝试多种选择器定位顶部导航栏中的"电报"按钮
            telegraph_selectors = [
                "header a:has-text('电报')",
                "nav a:has-text('电报')",
                ".header a:has-text('电报')",
                ".nav a:has-text('电报')",
                "a.nav-item:has-text('电报')",
                "a:has-text('电报')"
            ]

            clicked = False
            for selector in telegraph_selectors:
                try:
                    # 查找电报按钮
                    elements = self.page.query_selector_all(selector)
                    logger.info(
                        f"使用选择器 '{selector}' 找到 {len(elements)} 个可能的电报导航元素")

                    for element in elements:
                        # 确认是顶部导航中的电报按钮
                        text = element.inner_text().strip()
                        if text == "电报":
                            # 尝试判断是否是首页顶部导航栏中的元素
                            # 可以检查父元素或位置信息来确认
                            is_top_nav = element.evaluate(
                                "el => { const rect = el.getBoundingClientRect(); return rect.top < 100; }")
                            if is_top_nav:
                                element.click()
                                logger.info("成功点击顶部导航栏中的'电报'按钮")
                                self.page.wait_for_load_state("networkidle")
                                time.sleep(2)
                                clicked = True
                                break
                except Exception as e:
                    logger.debug(f"使用选择器'{selector}'点击电报导航时出错: {e}")
                    continue

                if clicked:
                    break

            if not clicked:
                # 如果上述方法都失败，尝试更直接的方法
                try:
                    logger.warning("常规方法未能点击'电报'，尝试更直接的点击方法")

                    # 保存当前页面源码用于调试
                    with open("debug/before_click_telegraph.html", "w", encoding="utf-8") as f:
                        f.write(self.page.content())

                    # 直接使用evaluateHandle执行JavaScript查找并点击
                    self.page.evaluate("""
                        () => {
                            // 尝试查找所有导航链接
                            const links = Array.from(document.querySelectorAll('a'));
                            // 查找包含"电报"文本的链接
                            const telegraphLink = links.find(link => link.textContent.trim() === '电报');
                            if (telegraphLink) {
                                // 模拟点击
                                telegraphLink.click();
                                return true;
                            }
                            return false;
                        }
                    """)

                    time.sleep(2)
                    self.page.wait_for_load_state("networkidle")

                    # 检查导航是否成功
                    current_url = self.page.url
                    if "telegraph" in current_url.lower():
                        logger.info("通过JavaScript成功导航到电报页面")
                        clicked = True
                    else:
                        logger.warning(
                            f"尝试点击电报后，URL为 {current_url}，可能未成功导航到电报页面")
                except Exception as e:
                    logger.error(f"直接点击'电报'失败: {e}")

            if not clicked:
                # 如果还是失败，尝试直接导航到电报页面
                logger.warning("无法通过点击导航到电报页面，尝试直接访问电报URL")
                try:
                    telegraph_url = f"{self.base_url}/telegraph"
                    self.page.goto(telegraph_url)
                    self.page.wait_for_load_state("networkidle")
                    time.sleep(2)
                    logger.info(f"直接导航到电报页面URL: {telegraph_url}")
                    clicked = True
                except Exception as e:
                    logger.error(f"直接导航到电报URL失败: {e}")
                    return False

            # 保存电报页面截图
            self.page.screenshot(path="debug/telegraph_page.png")

            # 第三步：在电报页面上点击子导航（如"公司"或"看盘"）
            logger.info(f"尝试在电报页面上点击'{section}'子导航")

            # 尝试多种选择器定位子导航
            sub_section_selectors = [
                f".sub-nav a:has-text('{section}')",
                f"nav.secondary-nav a:has-text('{section}')",
                f".tabs a:has-text('{section}')",
                f"[role='tablist'] a:has-text('{section}')",
                f"a.tab:has-text('{section}')",
                f"a:has-text('{section}')"
            ]

            clicked = False
            for selector in sub_section_selectors:
                try:
                    elements = self.page.query_selector_all(selector)
                    logger.info(
                        f"使用选择器 '{selector}' 找到 {len(elements)} 个可能的'{section}'子导航元素")

                    for element in elements:
                        text = element.inner_text().strip()
                        if text == section:
                            # 尝试确认这是电报页面下的子导航
                            element.click()
                            logger.info(f"成功点击电报页面下的'{section}'子导航")
                            self.page.wait_for_load_state("networkidle")
                            time.sleep(2)
                            clicked = True
                            break
                except Exception as e:
                    logger.debug(f"使用选择器'{selector}'点击'{section}'子导航时出错: {e}")
                    continue

                if clicked:
                    break

            if not clicked:
                # 如果上述方法都失败，尝试更直接的方法
                try:
                    logger.warning(f"常规方法未能点击'{section}'子导航，尝试更直接的点击方法")

                    # 保存当前页面源码用于调试
                    with open(f"debug/before_click_{section}.html", "w", encoding="utf-8") as f:
                        f.write(self.page.content())

                    # 直接使用evaluateHandle执行JavaScript查找并点击
                    self.page.evaluate(f"""
                        () => {{
                            // 尝试查找所有导航链接
                            const links = Array.from(document.querySelectorAll('a'));
                            // 查找包含"{section}"文本的链接
                            const sectionLink = links.find(link => link.textContent.trim() === '{section}');
                            if (sectionLink) {{
                                // 模拟点击
                                sectionLink.click();
                                return true;
                            }}
                            return false;
                        }}
                    """)

                    time.sleep(2)
                    self.page.wait_for_load_state("networkidle")
                    logger.info(f"尝试通过JavaScript点击'{section}'子导航")
                    clicked = True
                except Exception as e:
                    logger.error(f"直接点击'{section}'子导航失败: {e}")

            # 保存子导航页面截图
            self.page.screenshot(path=f"debug/telegraph_{section}_page.png")

            return clicked

        except Exception as e:
            logger.error(f"导航到电报{section}板块时出错: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    def extract_post_info(self, post_element) -> Dict[str, Any]:
        """
        从帖子元素中提取信息

        Args:
            post_element: 帖子的DOM元素

        Returns:
            包含帖子信息的字典
        """
        try:
            # 获取元素的HTML和文本，用于调试
            html = post_element.inner_html()
            element_text = post_element.inner_text()
            
            # 首先从文本内容中提取【】包围的标题，适合财联社电报格式
            title = "无标题"
            title_match = re.search(r'【(.*?)】', element_text)
            if title_match:
                title = title_match.group(1)
                logger.debug(f"从内容中提取到的标题: {title}")
            
            # 提取日期和时间
            date_str = "未知日期"
            time_str = "未知时间"
            
            # 匹配日期格式：2025.04.11 星期五
            date_match = re.search(r'(\d{4}\.\d{2}\.\d{2})\s*星期[一二三四五六日]', element_text)
            if date_match:
                date_str = date_match.group(1)
            
            # 匹配时间格式：14:05:39 或 14:05
            time_match = re.search(r'(\d{2}:\d{2}(:\d{2})?)', element_text)
            if time_match:
                time_str = time_match.group(1)
            
            # 提取评论数
            comment_count = 0
            comment_match = re.search(r'评论\((\d+)\)', element_text)
            if comment_match:
                try:
                    comment_count = int(comment_match.group(1))
                except ValueError:
                    comment_count = 0
            
            # 如果没有匹配到标题但有内容，使用内容的前30个字符作为标题
            if title == "无标题" and len(element_text.strip()) > 30:
                # 去除可能的日期时间
                cleaned_text = re.sub(r'\d{4}\.\d{2}\.\d{2}\s*星期[一二三四五六日]', '', element_text)
                cleaned_text = re.sub(r'\d{2}:\d{2}(:\d{2})?', '', cleaned_text)
                # 取前30个字符
                title = cleaned_text.strip()[:30].strip() + "..."
            
            return {
                "title": title,
                "date": date_str,
                "time": time_str,
                "comment_count": comment_count,
                "element": post_element  # 保存原始元素，以便后续处理
            }
            
        except Exception as e:
            logger.error(f"提取帖子信息时出错: {e}")
            return {
                "title": "错误",
                "date": "未知日期",
                "time": "未知时间",
                "comment_count": 0,
                "element": None
            }

    def extract_posts_from_page(self) -> List[Dict[str, Any]]:
        """
        从当前页面提取所有帖子信息
        
        Returns:
            帖子信息列表和是否达到截止日期的标志
        """
        posts = []
        seen_titles = set()  # 用于去重，避免同一帖子被多个选择器重复添加
        reached_cutoff = False
        try:
            # 根据网站结构找到真正的电报帖子列表容器
            # 只选择class为b-c-e6e7ea telegraph-list的元素，这是真正的帖子
            telegraph_containers = [
                ".b-c-e6e7ea.telegraph-list",  # 财联社电报列表容器（精确匹配）
                "div.b-c-e6e7ea.telegraph-list",  # 带div标签的精确匹配
                ".telegraph-list",  # 更广泛的匹配，但可能误匹配
                "[class='b-c-e6e7ea telegraph-list']"  # 精确匹配完整class
            ]
            
            # 明确排除的选择器
            exclude_selectors = [
                ".telegraph-content-left", 
                "[class*='telegraph-content-left']",
                "div.telegraph-content-left",
                ".clearfix.content-main-box",  # 排除页面顶部的内容
                "div:has-text('电报持续更新中')"  # 排除包含此文本的元素
            ]
            
            # 先获取需要排除的元素
            exclude_elements = []
            for selector in exclude_selectors:
                try:
                    elements = self.page.query_selector_all(selector)
                    logger.info(f"找到 {len(elements)} 个需要排除的元素，使用选择器 '{selector}'")
                    exclude_elements.extend(elements)
                except Exception as e:
                    logger.debug(f"使用选择器'{selector}'查找需排除元素时出错: {e}")
            
            for container_selector in telegraph_containers:
                try:
                    containers = self.page.query_selector_all(container_selector)
                    logger.info(f"使用选择器 '{container_selector}' 找到 {len(containers)} 个电报容器")
                    
                    if not containers or len(containers) == 0:
                        continue
                    
                    # 在容器内寻找真正的帖子元素
                    for container in containers:
                        # 检查是否是需要排除的元素
                        is_excluded = False
                        for exclude_el in exclude_elements:
                            # 比较元素是否相同
                            try:
                                is_same = container.evaluate("(el, excludeEl) => el === excludeEl", exclude_el)
                                if is_same:
                                    is_excluded = True
                                    break
                            except Exception:
                                pass
                        
                        if is_excluded:
                            logger.info("跳过需要排除的元素")
                            continue
                        
                        # 排除页面顶部的日期时间区域（红框区域）
                        # 检查是否包含"电报持续更新中"文本
                        container_text = container.inner_text()
                        if "电报持续更新中" in container_text or "电报持续更新" in container_text:
                            logger.info("跳过页面顶部的更新提示区域")
                            continue
                        
                        # 检查是否包含标题指示符【】
                        has_title_indicator = re.search(r'【.*?】', container_text)
                        
                        # 提取帖子信息
                        post_info = self.extract_post_info(container)
                        
                        # 只保留具有有效标题和日期的帖子
                        if (post_info["title"] and post_info["title"] != "无标题" and post_info["title"] != "错误") or has_title_indicator:
                            # 如果没有提取出标题但有标题指示符，尝试从文本中提取标题
                            if post_info["title"] == "无标题" and has_title_indicator:
                                title_match = re.search(r'【(.*?)】', container_text)
                                if title_match:
                                    post_info["title"] = title_match.group(1)
                                    logger.info(f"从内容中提取标题: {post_info['title']}")
                            
                            # 检查标题是否已处理过（避免重复）
                            if post_info["title"] in seen_titles:
                                continue
                            
                            # 检查日期是否在截止日期和当前时间范围内
                            if post_info["date"] and post_info["time"]:
                                try:
                                    post_date = parse_datetime(post_info["date"], post_info["time"])
                                    # 如果帖子时间早于截止日期，则标记已达到截止日期，不保存此帖子并停止提取
                                    if post_date < self.cutoff_date:
                                        logger.info(f"帖子日期 {post_info['date']} {post_info['time']} 早于截止日期 {self.cutoff_date}，停止爬取")
                                        reached_cutoff = True
                                        break
                                    
                                    # 只保存在截止日期之后的帖子
                                    # 验证是否是真正的帖子元素
                                    # 1. 检查是否包含真实内容
                                    content_length = len(container_text.strip())
                                    # 2. 确保不是页面导航元素
                                    is_navigation = any(nav_text in container_text.lower() for nav_text in ["首页", "菜单", "导航", "全部"])
                                    
                                    if content_length > 50 and not is_navigation:  # 有足够内容且不是导航元素
                                        posts.append(post_info)
                                        seen_titles.add(post_info["title"])  # 添加到已处理标题集合
                                        logger.info(f"找到帖子: {post_info['title']}")
                                except Exception as e:
                                    logger.error(f"检查日期时出错: {e}")
                        
                        # 如果已达到截止日期，不再继续处理后面的容器
                        if reached_cutoff:
                            break
                except Exception as e:
                    logger.error(f"使用选择器'{container_selector}'提取帖子时出错: {e}")
                    continue
            
            # 如果上述方法没有找到帖子，回退到原来的查找方法
            if not posts:
                logger.warning("未找到电报列表容器，尝试直接查找帖子元素")
                
                # 根据观察到的电报帖子结构，修改选择器
                post_selectors = [
                    ".telegraph-content-box",
                    ".telegraph-list div.clearfix",
                    "[class*='telegraph-content']",
                    ".news-item",
                    "[class*='news-item']",
                    "div.clearfix.m-b-15"  # 根据网站实际结构调整
                ]
                
                for selector in post_selectors:
                    try:
                        post_elements = self.page.query_selector_all(selector)
                        logger.info(f"使用选择器 '{selector}' 找到 {len(post_elements)} 个可能的帖子元素")
                        
                        for element in post_elements:
                            # 跳过页面顶部的更新提示
                            element_text = element.inner_text()
                            if "电报持续更新中" in element_text or "电报持续更新" in element_text:
                                logger.info("跳过页面顶部的更新提示区域")
                                continue
                            
                            # 检查是否包含时间格式（如"23:48:20"或"16:50:47"）
                            if re.search(r'\d{2}:\d{2}(:\d{2})?', element_text):
                                # 提取帖子信息
                                post_info = self.extract_post_info(element)
                                
                                # 尝试从内容中提取标题，如果没有标题
                                if post_info["title"] == "无标题":
                                    title_match = re.search(r'【(.*?)】', element_text)
                                    if title_match:
                                        post_info["title"] = title_match.group(1)
                                
                                # 如果仍然没有标题，使用内容前30个字符
                                if post_info["title"] == "无标题" and len(element_text.strip()) > 30:
                                    post_info["title"] = element_text.strip()[:30].strip() + "..."
                                
                                # 检查标题是否已处理过（避免重复）
                                if post_info["title"] in seen_titles:
                                    continue
                                
                                # 检查日期是否在截止日期和当前时间范围内
                                if post_info["date"] and post_info["time"]:
                                    try:
                                        post_date = parse_datetime(post_info["date"], post_info["time"])
                                        # 如果帖子时间早于截止日期，则标记已达到截止日期，不保存此帖子并停止提取
                                        if post_date < self.cutoff_date:
                                            logger.info(f"帖子日期 {post_info['date']} {post_info['time']} 早于截止日期 {self.cutoff_date}，停止爬取")
                                            reached_cutoff = True
                                            break
                                            
                                        # 添加符合日期条件的帖子
                                        posts.append(post_info)
                                        seen_titles.add(post_info["title"])  # 添加到已处理标题集合
                                        logger.info(f"找到帖子: {post_info['title']}")
                                    except Exception as e:
                                        logger.error(f"检查日期时出错: {e}")
                            
                            # 如果已达到截止日期，不再继续处理
                            if reached_cutoff:
                                break
                    except Exception as e:
                        logger.error(f"使用选择器'{selector}'提取帖子时出错: {e}")
                        continue
            
            # 如果上述方法仍未找到帖子，尝试最后的回退方法
            if not posts:
                logger.warning("未找到电报帖子，尝试使用最通用的选择器")
                
                # 使用最通用的选择器，可能包含更多噪声
                generic_selectors = [
                    "div.clearfix",
                    ".clearfix",
                    "div[class*='content']",
                    "[class*='item']"
                ]
                
                for selector in generic_selectors:
                    try:
                        elements = self.page.query_selector_all(selector)
                        logger.info(f"使用选择器 '{selector}' 找到 {len(elements)} 个可能的元素")
                        
                        for element in elements:
                            element_text = element.inner_text()
                            
                            # 检查是否包含日期和时间格式
                            date_match = re.search(r'\d{4}\.\d{2}\.\d{2}', element_text)
                            time_match = re.search(r'\d{2}:\d{2}(:\d{2})?', element_text)
                            
                            if date_match and time_match:
                                date_str = date_match.group(0)
                                time_str = time_match.group(0)
                                
                                # 尝试检查日期是否在范围内
                                try:
                                    post_date = parse_datetime(date_str, time_str)
                                    # 如果帖子时间早于截止日期，则标记已达到截止日期，不保存此帖子并停止提取
                                    if post_date < self.cutoff_date:
                                        logger.info(f"帖子日期 {date_str} {time_str} 早于截止日期 {self.cutoff_date}，停止爬取")
                                        reached_cutoff = True
                                        break
                                    
                                    # 尝试提取标题
                                    title = "无标题"
                                    title_match = re.search(r'【(.*?)】', element_text)
                                    if title_match:
                                        title = title_match.group(1)
                                    elif len(element_text) > 30:
                                        # 去除日期和时间
                                        clean_text = re.sub(r'\d{4}\.\d{2}\.\d{2}|\d{2}:\d{2}(:\d{2})?', '', element_text)
                                        title = clean_text.strip()[:30] + "..."
                                    
                                    # 检查标题是否已处理过（避免重复）
                                    if title in seen_titles:
                                        continue
                                    
                                    # 构造帖子信息
                                    post_info = {
                                        "title": title,
                                        "date": date_str,
                                        "time": time_str,
                                        "comment_count": 0,
                                        "element": element
                                    }
                                    
                                    # 添加到结果中
                                    posts.append(post_info)
                                    seen_titles.add(title)  # 添加到已处理标题集合
                                    logger.info(f"找到帖子: {title}")
                                except Exception as e:
                                    logger.error(f"处理日期时出错: {e}")
                            
                            # 如果已达到截止日期，不再继续处理
                            if reached_cutoff:
                                break
                    except Exception as e:
                        logger.error(f"使用选择器'{selector}'查找元素时出错: {e}")
                        continue
                    
                    # 如果找到了足够的帖子，就不再尝试其他选择器
                    if len(posts) > 0:
                        break
            
            logger.info(f"总共找到 {len(posts)} 条帖子")
            return posts, reached_cutoff
        
        except Exception as e:
            logger.error(f"提取帖子时出错: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return [], reached_cutoff

    def load_more_posts(self) -> bool:
        """
        点击加载更多按钮，加载更多帖子
        
        Returns:
            是否成功加载更多
        """
        try:
            # 寻找"加载更多"按钮
            load_more_selectors = [
                "button:has-text('加载更多')",
                "a:has-text('加载更多')",
                "[class*='load-more']",
                "[class*='loadMore']",
                ".load-more",
                ".loadMore",
                "button.load-more",
                "button.loadMore",
                "a.load-more",
                "a.loadMore"
            ]
            
            # 尝试点击加载更多按钮
            clicked = False
            for selector in load_more_selectors:
                try:
                    load_more_btn = self.page.query_selector(selector)
                    if load_more_btn:
                        # 判断按钮是否可见和可点击
                        is_visible = load_more_btn.is_visible()
                        if is_visible:
                            logger.info(f"找到加载更多按钮，使用选择器: {selector}")
                            load_more_btn.click()
                            clicked = True
                            # 等待页面加载
                            self.page.wait_for_load_state("networkidle")
                            time.sleep(2)
                            break
                except Exception as e:
                    logger.debug(f"点击加载更多按钮'{selector}'时出错: {e}")
                    continue
            
            # 如果没有找到加载更多按钮，尝试使用JavaScript滚动页面到底部
            if not clicked:
                logger.info("未找到加载更多按钮，尝试滚动到页面底部")
                self.page.evaluate("""
                    window.scrollTo({
                        top: document.body.scrollHeight,
                        behavior: 'smooth'
                    });
                """)
                time.sleep(2)
                
                # 检查加载的内容是否增加
                old_height = self.page.evaluate("document.body.scrollHeight")
                time.sleep(2)
                new_height = self.page.evaluate("document.body.scrollHeight")
                
                if new_height > old_height:
                    logger.info(f"页面高度从 {old_height} 增加到 {new_height}，内容已加载更多")
                    clicked = True
            
            return clicked
            
        except Exception as e:
            logger.error(f"加载更多帖子时出错: {e}")
            return False

    def scrape_section(self, section: str) -> List[Dict[str, Any]]:
        """
        爬取指定板块的电报内容
        
        Args:
            section: 要爬取的板块名称，如"看盘"或"公司"
            
        Returns:
            处理后的电报内容列表
        """
        section_results = []
        processed_titles = set()  # 用于跟踪已处理的帖子标题，避免重复
        
        try:
            load_more_attempts = 0
            
            while True:
                # 提取当前页面的帖子
                posts, reached_cutoff = self.extract_posts_from_page()
                
                # 处理帖子
                for post in posts:
                    # 跳过已处理的标题相同的帖子
                    if post["title"] in processed_titles:
                        logger.info(f"跳过重复帖子: '{post['title']}'")
                        continue
                    
                    # 检查帖子日期是否早于截止日期
                    try:
                        post_date = parse_datetime(post["date"], post["time"])
                        
                        # 如果帖子时间早于截止日期，则跳过处理
                        if post_date < self.cutoff_date:
                            logger.info(f"帖子日期 {post['date']} {post['time']} 早于截止日期 {self.cutoff_date}，跳过处理")
                            continue
                            
                        # 把标题加入已处理集合
                        processed_titles.add(post["title"])
                    except Exception as e:
                        logger.error(f"检查日期时出错: {e}")
                        continue  # 如果日期处理出错，跳过该帖子

                    # 分析帖子
                    result = self.analyze_post(post)
                    result["section"] = section  # 添加板块信息

                    # 添加到结果列表
                    section_results.append(result)
                    logger.info(f"处理完成帖子: '{post['title']}', 情感: {result.get('sentiment', '未知')}")

                # 如果已达到截止日期，停止加载更多
                if reached_cutoff:
                    logger.info("已达到截止日期，停止爬取")
                    break

                # 尝试加载更多
                if not self.load_more_posts():
                    logger.info("无法加载更多帖子，结束处理")
                    break

                load_more_attempts += 1
                logger.info(f"已尝试加载更多 {load_more_attempts} 次")

                # 短暂暂停，避免请求过于频繁
                time.sleep(1)

        except Exception as e:
            logger.error(f"爬取'{section}'板块时出错: {e}")
            import traceback
            logger.error(traceback.format_exc())

        logger.info(f"'{section}'板块爬取完成，共获取 {len(section_results)} 条结果")
        return section_results

    def run(self, sections: List[str] = None) -> List[Dict[str, Any]]:
        """
        执行爬取和分析过程

        Args:
            sections: 要爬取的电报子板块列表，默认为["看盘", "公司"]

        Returns:
            包含所有分析结果的列表，仅包含cutoff_date到当前时间范围内的电报
        """
        try:
            # 如果没有指定板块，默认爬取"看盘"和"公司"
            if sections is None:
                sections = ["看盘", "公司"]

            # 首先直接导航到电报页面
            logger.info("直接导航到电报页面")
            try:
                telegraph_url = f"{self.base_url}/telegraph"
                self.page.goto(telegraph_url)
                self.page.wait_for_load_state("networkidle")
                time.sleep(2)
                logger.info(f"直接导航到电报页面URL: {telegraph_url}")
            except Exception as e:
                logger.error(f"直接导航到电报页面失败: {e}")
                # 如果直接导航失败，尝试从首页导航
                logger.info("尝试从首页导航到电报")
                self.navigate_to_site()

                # 点击电报链接
                try:
                    self.page.click("text=电报")
                    self.page.wait_for_load_state("networkidle")
                    time.sleep(2)
                    logger.info("从首页点击导航到电报页面")
                except Exception as e:
                    logger.error(f"从首页点击导航到电报页面失败: {e}")
                    return []

            # 根据指定的板块列表爬取内容
            logger.info(f"开始爬取电报，子板块: {sections}")

            for section in sections:
                try:
                    logger.info(f"开始爬取'{section}'板块...")

                    # 点击电报页面中的子导航
                    logger.info(f"尝试点击电报页面中的'{section}'子导航")
                    try:
                        # 首先确保我们在电报主页面
                        if "telegraph" not in self.page.url:
                            telegraph_url = f"{self.base_url}/telegraph"
                            self.page.goto(telegraph_url)
                            self.page.wait_for_load_state("networkidle")
                            time.sleep(2)

                        # 尝试点击子导航
                        clicked = False

                        # 使用更简单直接的方式点击子导航
                        sub_nav_selectors = [
                            f"a:has-text('{section}')",
                            f"[class*='nav'] a:has-text('{section}')",
                            f"[class*='tab'] a:has-text('{section}')"
                        ]

                        for selector in sub_nav_selectors:
                            try:
                                elements = self.page.query_selector_all(selector)
                                for element in elements:
                                    text = element.inner_text().strip()
                                    if text == section:
                                        element.click()
                                        logger.info(f"成功点击'{section}'子导航")
                                        self.page.wait_for_load_state("networkidle")
                                        time.sleep(2)
                                        clicked = True
                                        break

                                if clicked:
                                    break
                            except Exception as e:
                                logger.debug(f"使用选择器'{selector}'点击子导航时出错: {e}")
                                continue

                        if not clicked:
                            # 使用JavaScript尝试点击
                            self.page.evaluate(f"""
                                () => {{
                                    const links = Array.from(document.querySelectorAll('a'));
                                    for (const link of links) {{
                                        if (link.textContent.trim() === '{section}') {{
                                            link.click();
                                            return true;
                                        }}
                                    }}
                                    return false;
                                }}
                            """)
                            logger.info(f"尝试使用JavaScript点击'{section}'子导航")
                            time.sleep(2)
                            self.page.wait_for_load_state("networkidle")

                    except Exception as e:
                        logger.error(f"点击'{section}'子导航失败: {e}")
                        # 如果点击失败，尝试重新加载电报页面
                        continue

                    # 爬取当前板块内容
                    section_results = self.scrape_section(section)
                    self.results.extend(section_results)
                    logger.info(f"'{section}'板块爬取完成，获取到{len(section_results)}条电报")
                except Exception as e:
                    logger.error(f"爬取'{section}'板块时出错: {e}")
                    import traceback
                    logger.error(traceback.format_exc())

            return self.results

        except Exception as e:
            logger.error(f"运行电报爬虫时出错: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return self.results 