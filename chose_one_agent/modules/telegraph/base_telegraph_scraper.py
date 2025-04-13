# -*- coding: utf-8 -*-
import logging
import time
import datetime
import os
from typing import List, Dict, Any, Tuple
import re
import random

from chose_one_agent.scrapers.base_scraper import BaseScraper
from chose_one_agent.utils.helpers import parse_datetime, is_before_cutoff, extract_date_time, is_in_date_range
from chose_one_agent.analyzers.sentiment_analyzer import SentimentAnalyzer

# 配置日志
logger = logging.getLogger(__name__)


class BaseTelegraphScraper(BaseScraper):
    """
    财经网站的电报爬虫基类，用于抓取和分析电报内容，包含基础的电报爬取功能
    该类提供了通用的方法，特定板块的爬虫类应该继承此类并实现特定的处理逻辑
    """

    def __init__(self, cutoff_date, headless=True, debug=False):
        """
        初始化电报爬虫基类

        Args:
            cutoff_date: 截止日期，爬虫只会获取该日期到当前时间范围内的电报，早于或晚于此范围的电报将被忽略
            headless: 是否使用无头模式运行浏览器
            debug: 是否启用调试模式
        """
        super().__init__(cutoff_date, headless)
        self.sentiment_analyzer = SentimentAnalyzer()
        self.debug = debug

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
            import traceback
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
                import traceback
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

            return clicked

        except Exception as e:
            logger.error(f"导航到电报{section}板块时出错: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False 