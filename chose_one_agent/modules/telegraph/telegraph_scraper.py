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
            
            # 记录提取的原始文本内容
            logger.debug(f"提取帖子原始文本内容: {element_text[:100]}...")
            
            # 排除非真实帖子内容
            if "桌面通知" in element_text or "声音提醒" in element_text:
                return {
                    "title": "非帖子内容",
                    "date": "",
                    "time": "",
                    "comment_count": 0,
                    "element": None,
                    "is_valid_post": False
                }
            
            # 从文本内容中提取【】包围的标题
            title = "无标题"
            title_match = re.search(r'【(.*?)】', element_text)
            if title_match:
                title = title_match.group(1)
                logger.debug(f"从内容中提取到的标题: {title}")
            
            # 提取日期和时间
            date_str = "未知日期"
            time_str = "未知时间"
            
            # 匹配多种日期格式
            # 1. 标准格式: 2025.04.11 星期五
            date_match = re.search(r'(\d{4}\.\d{2}\.\d{2})\s*星期[一二三四五六日]', element_text)
            if date_match:
                date_str = date_match.group(1)
            
            # 2. 尝试其他常见日期格式
            if date_str == "未知日期":
                date_patterns = [
                    r'(\d{4}\.\d{2}\.\d{2})',  # 2025.04.11
                    r'(\d{4}-\d{2}-\d{2})',     # 2025-04-11
                    r'(\d{4}/\d{2}/\d{2})',     # 2025/04/11
                ]
                
                for pattern in date_patterns:
                    date_match = re.search(pattern, element_text)
                    if date_match:
                        date_str = date_match.group(1).replace('-', '.').replace('/', '.')
                        break
                
                # 如果还是没找到，尝试提取月日格式
                if date_str == "未知日期":
                    month_day_match = re.search(r'(\d{1,2})月(\d{1,2})日', element_text)
                    if month_day_match:
                        month, day = month_day_match.groups()
                        year = datetime.datetime.now().year
                        date_str = f"{year}.{int(month):02d}.{int(day):02d}"
            
            # 匹配时间格式：14:05:39 或 14:05
            time_match = re.search(r'(\d{2}:\d{2}(:\d{2})?)', element_text)
            if time_match:
                time_str = time_match.group(1)
            
            # 如果仍然没有找到日期和时间，尝试找到一个连续的数字和冒号组合
            if date_str == "未知日期" and time_str == "未知时间":
                datetime_match = re.search(r'(\d{1,4}[/\-\.]\d{1,2}[/\-\.]\d{1,4}[\s\S]+?\d{1,2}:\d{1,2})', element_text)
                if datetime_match:
                    dt_str = datetime_match.group(1)
                    logger.debug(f"找到日期时间组合: {dt_str}")
                    
                    # 提取日期部分
                    date_part = re.search(r'(\d{1,4}[/\-\.]\d{1,2}[/\-\.]\d{1,4})', dt_str)
                    if date_part:
                        date_parts = re.split(r'[/\-\.]', date_part.group(1))
                        if len(date_parts) == 3:
                            # 确保年份是4位数
                            if len(date_parts[0]) != 4 and len(date_parts[2]) == 4:
                                # 假设格式是DD/MM/YYYY
                                date_str = f"{date_parts[2]}.{int(date_parts[1]):02d}.{int(date_parts[0]):02d}"
                            else:
                                # 假设格式是YYYY/MM/DD
                                date_str = f"{date_parts[0]}.{int(date_parts[1]):02d}.{int(date_parts[2]):02d}"
                    
                    # 提取时间部分
                    time_part = re.search(r'(\d{1,2}:\d{1,2}(:\d{1,2})?)', dt_str)
                    if time_part:
                        time_str = time_part.group(1)
            
            # 提取评论数
            comment_count = 0
            comment_match = re.search(r'评论\((\d+)\)', element_text)
            if comment_match:
                try:
                    comment_count = int(comment_match.group(1))
                except ValueError:
                    comment_count = 0
            
            # 如果仍然没找到评论数，尝试其他格式
            if comment_count == 0:
                comment_match2 = re.search(r'评论[：:]\s*(\d+)', element_text)
                if comment_match2:
                    try:
                        comment_count = int(comment_match2.group(1))
                    except ValueError:
                        comment_count = 0
            
            # 如果没有匹配到标题但有内容，使用内容的前30个字符作为标题
            if title == "无标题" and len(element_text.strip()) > 30:
                # 去除可能的日期时间
                cleaned_text = re.sub(r'\d{4}\.\d{2}\.\d{2}\s*星期[一二三四五六日]', '', element_text)
                cleaned_text = re.sub(r'\d{2}:\d{2}(:\d{2})?', '', cleaned_text)
                # 取前30个字符
                title = cleaned_text.strip()[:30].strip() + "..."
            
            # 记录提取到的信息
            logger.debug(f"提取到的帖子信息 - 标题: {title}, 日期: {date_str}, 时间: {time_str}, 评论数: {comment_count}")
            
            return {
                "title": title,
                "date": date_str,
                "time": time_str,
                "comment_count": comment_count,
                "element": post_element,  # 保存原始元素，以便后续处理
                "is_valid_post": True
            }
            
        except Exception as e:
            logger.error(f"提取帖子信息时出错: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                "title": "错误",
                "date": "未知日期",
                "time": "未知时间",
                "comment_count": 0,
                "element": None,
                "is_valid_post": False
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
            # 优化选择器，专注于WEB版本
            telegraph_item_selectors = [
                ".telegraph-item",
                "[class*='telegraph-item']",
                ".article-item",
                "[class*='article-item']",
                ".post-item",
                "[class*='post-item']",
                ".telegraph-content-box",
                ".m-b-15",
                "div.m-b-15",
                "article",
                ".item"
            ]
            
            items_found = False
            
            for selector in telegraph_item_selectors:
                try:
                    items = self.page.query_selector_all(selector)
                    logger.info(f"使用选择器 '{selector}' 找到 {len(items)} 个可能的帖子元素")
                    
                    if items and len(items) > 0:
                        items_found = True
                        
                        # 提取帖子信息
                        for item in items:
                            # 获取元素文本内容
                            element_text = item.inner_text().strip()
                            
                            # 如果元素内容太少，可能不是有效帖子
                            if len(element_text) < 10:
                                continue
                                
                            # 排除页面顶部的提示信息
                            if "电报持续更新" in element_text:
                                continue
                                
                            # 提取帖子信息
                            post_info = self.extract_post_info(item)
                            
                            # 跳过无效的帖子
                            if not post_info.get("is_valid_post", False):
                                continue
                            
                            # 如果标题已经处理过，跳过
                            if post_info["title"] in seen_titles:
                                continue
                                
                            # 检查日期是否在截止日期之后
                            if post_info["date"] and post_info["time"]:
                                try:
                                    post_date = parse_datetime(post_info["date"], post_info["time"])
                                    # 如果帖子时间早于截止日期，标记已达到截止日期
                                    if post_date < self.cutoff_date:
                                        logger.info(f"帖子日期 {post_info['date']} {post_info['time']} 早于截止日期 {self.cutoff_date}")
                                        reached_cutoff = True
                                    else:
                                        # 保存符合日期要求的帖子
                                        posts.append(post_info)
                                        seen_titles.add(post_info["title"])
                                        logger.info(f"找到符合条件的帖子: {post_info['title']}, 日期: {post_info['date']} {post_info['time']}")
                                except Exception as e:
                                    logger.error(f"检查日期时出错: {e}")
                                    # 如果无法解析日期，仍将帖子添加到结果中
                                    posts.append(post_info)
                                    seen_titles.add(post_info["title"])
                                    logger.info(f"找到帖子(无法解析日期): {post_info['title']}")
                
                except Exception as e:
                    logger.error(f"使用选择器'{selector}'提取帖子时出错: {e}")
                    continue
                
                # 如果找到了足够的帖子，不再尝试其他选择器
                if len(posts) > 0:
                    break
                    
            # 如果没有找到任何帖子元素，尝试直接解析页面内容
            if not items_found or len(posts) == 0:
                logger.warning("未能通过常规选择器找到帖子，尝试直接解析页面内容")
                
                # 使用JavaScript直接分析页面结构
                try:
                    page_posts = self.page.evaluate("""
                        () => {
                            // 查找所有可能的帖子元素
                            const possibleItems = Array.from(document.querySelectorAll('div, article'))
                                .filter(el => {
                                    // 尝试识别可能的帖子元素特征
                                    const text = el.textContent;
                                    const hasTitle = text.includes('【') && text.includes('】');
                                    const hasDateTime = /\\d{2}:\\d{2}/.test(text);
                                    const isReasonableSize = el.offsetHeight > 50 && el.offsetWidth > 200;
                                    
                                    return (hasTitle || hasDateTime) && isReasonableSize;
                                });
                            
                            return possibleItems.map(el => {
                                return {
                                    html: el.outerHTML,
                                    text: el.textContent.trim(),
                                    rect: el.getBoundingClientRect()
                                };
                            });
                        }
                    """)
                    
                    logger.info(f"JavaScript分析找到 {len(page_posts)} 个可能的帖子元素")
                    
                    # 根据JavaScript分析结果，直接构建帖子信息
                    for post_data in page_posts:
                        post_text = post_data["text"]
                        
                        # 提取标题
                        title = "无标题"
                        title_match = re.search(r'【(.*?)】', post_text)
                        if title_match:
                            title = title_match.group(1)
                        
                        # 提取日期和时间
                        date_str = "未知日期"
                        time_str = "未知时间"
                        
                        date_match = re.search(r'(\d{4}\.\d{2}\.\d{2})', post_text)
                        if date_match:
                            date_str = date_match.group(1)
                            
                        time_match = re.search(r'(\d{2}:\d{2}(:\d{2})?)', post_text)
                        if time_match:
                            time_str = time_match.group(1)
                            
                        # 跳过已处理的标题
                        if title in seen_titles:
                            continue
                            
                        # 创建帖子信息
                        post_info = {
                            "title": title,
                            "date": date_str,
                            "time": time_str,
                            "comment_count": 0,
                            "element": None,  # JS分析模式下没有DOM元素
                            "is_valid_post": True
                        }
                        
                        # 检查日期是否在截止日期之后
                        if date_str != "未知日期" and time_str != "未知时间":
                            try:
                                post_date = parse_datetime(date_str, time_str)
                                # 如果帖子时间早于截止日期
                                if post_date < self.cutoff_date:
                                    logger.info(f"帖子日期 {date_str} {time_str} 早于截止日期 {self.cutoff_date}")
                                    reached_cutoff = True
                                else:
                                    # 保存符合日期要求的帖子
                                    posts.append(post_info)
                                    seen_titles.add(title)
                                    logger.info(f"JS分析找到符合条件的帖子: {title}, 日期: {date_str} {time_str}")
                            except Exception as e:
                                logger.error(f"JS分析检查日期时出错: {e}")
                                # 如果无法解析日期，仍将帖子添加到结果中
                                posts.append(post_info)
                                seen_titles.add(title)
                                logger.info(f"JS分析找到帖子(无法解析日期): {title}")
                except Exception as e:
                    logger.error(f"执行JavaScript分析页面结构时出错: {e}")
            
            logger.info(f"总共找到 {len(posts)} 条符合条件的帖子")
            
            return posts, reached_cutoff
        
        except Exception as e:
            logger.error(f"提取帖子时出错: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return [], reached_cutoff

    def load_more_posts(self) -> bool:
        """
        加载更多帖子，专注于WEB版本的加载逻辑：
        1. 点击"加载更多"按钮
        2. 模拟滚动到页面底部触发自动加载
        3. 注入JS分析页面结构并调用加载函数

        Returns:
            是否成功加载更多
        """
        try:
            # 获取当前页面高度和内容数量作为基准
            old_height = self.page.evaluate("document.body.scrollHeight")
            old_content_count = len(self.page.query_selector_all(".telegraph-item, [class*='telegraph-item'], .article-item, [class*='article-item']"))
            logger.info(f"当前页面高度: {old_height}px, 内容数量: {old_content_count}")
            
            # 首先尝试点击"加载更多"按钮
            logger.info("尝试点击'加载更多'按钮")
            load_more_selectors = [
                "button:has-text('加载更多')",
                "a:has-text('加载更多')",
                "div:has-text('加载更多')",
                "span:has-text('加载更多')",
                "button:has-text('更多')",
                "a:has-text('更多')",
                "div:has-text('更多')",
                "[class*='load-more']",
                "[class*='loadMore']",
                "[class*='more-btn']",
                "[class*='moreBtn']",
                "[class*='load_more']",
                "[id*='load-more']",
                "[id*='loadMore']",
                ".load-more", 
                ".loadMore",
                ".more"
            ]
            
            # 尝试点击加载更多按钮
            for selector in load_more_selectors:
                try:
                    load_more_btns = self.page.query_selector_all(selector)
                    if load_more_btns and len(load_more_btns) > 0:
                        for btn in load_more_btns:
                            # 判断按钮是否可见和可点击
                            if btn.is_visible():
                                logger.info(f"找到加载更多按钮，使用选择器: {selector}")
                                # 确保按钮在视图中
                                btn.scroll_into_view_if_needed()
                                time.sleep(0.5)
                                btn.click()
                                # 等待页面加载
                                time.sleep(2)
                                
                                # 检查内容是否增加
                                new_height = self.page.evaluate("document.body.scrollHeight")
                                new_content_count = len(self.page.query_selector_all(".telegraph-item, [class*='telegraph-item'], .article-item, [class*='article-item']"))
                                
                                if new_height > old_height + 5 or new_content_count > old_content_count:
                                    logger.info(f"点击加载更多按钮成功: 内容从 {old_content_count} 增加到 {new_content_count} 个元素")
                                    return True
                except Exception as e:
                    logger.debug(f"点击加载更多按钮'{selector}'时出错: {e}")
                    continue

            # 如果没有找到加载更多按钮，尝试直接滚动页面
            logger.info("尝试滚动页面触发加载更多")
            
            # 直接滚动到页面底部
            self.page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            
            # 检查内容是否增加
            new_height = self.page.evaluate("document.body.scrollHeight")
            new_content_count = len(self.page.query_selector_all(".telegraph-item, [class*='telegraph-item'], .article-item, [class*='article-item']"))
            
            if new_height > old_height + 5 or new_content_count > old_content_count:
                logger.info(f"滚动页面成功: 内容从 {old_content_count} 增加到 {new_content_count} 个元素")
                return True
                
            # 尝试更高级的JavaScript解决方案
            logger.info("尝试使用JavaScript分析页面结构并触发加载更多")
            success = self.page.evaluate("""
                () => {
                    // 定义可能的加载更多按钮选择器
                    const loadMoreSelectors = [
                        '.load-more', '.loadMore', '.more-btn', '.moreBtn',
                        '[class*="load-more"]', '[class*="loadMore"]',
                        'button:contains("加载更多")', 'a:contains("加载更多")',
                        'div:contains("加载更多")', 'span:contains("加载更多")',
                        'button:contains("更多")', 'a:contains("更多")',
                        '[class*="more"]'
                    ];
                    
                    // 尝试找到并点击加载更多按钮
                    for (const selector of loadMoreSelectors) {
                        const elements = document.querySelectorAll(selector);
                        for (const element of elements) {
                            if (element.offsetParent !== null) {  // 检查元素是否可见
                                console.log('找到加载更多按钮:', element);
                                element.scrollIntoView({behavior: 'smooth', block: 'center'});
                                setTimeout(() => element.click(), 500);
                                return true;
                            }
                        }
                    }
                    
                    // 如果找不到按钮，尝试滚动页面
                    window.scrollTo({
                        top: document.body.scrollHeight,
                        behavior: 'smooth'
                    });
                    
                    // 尝试触发常见的滚动事件
                    window.dispatchEvent(new Event('scroll'));
                    document.dispatchEvent(new Event('scroll'));
                    
                    // 查找并调用可能的加载更多函数
                    const possibleFunctions = [
                        'loadMore', 'loadMoreData', 'appendMore', 'nextPage',
                        'moreData', 'getMore', 'fetchMore', 'loadmoreHandle'
                    ];
                    
                    // 在全局范围内查找
                    for (const fnName of possibleFunctions) {
                        if (typeof window[fnName] === 'function') {
                            try {
                                console.log(`尝试调用全局函数: ${fnName}`);
                                window[fnName]();
                                return true;
                            } catch (e) {
                                console.log(`调用函数 ${fnName} 失败:`, e);
                            }
                        }
                    }
                    
                    // 尝试查找可能的加载更多元素并模拟点击
                    const possibleLoadMoreElements = Array.from(document.querySelectorAll('*'))
                        .filter(el => {
                            // 尝试匹配可能的加载更多元素
                            if (!el.textContent) return false;
                            const text = el.textContent.toLowerCase();
                            const classAttr = (el.className || '').toLowerCase();
                            const idAttr = (el.id || '').toLowerCase();
                            
                            return (text.includes('更多') || text.includes('加载') ||
                                   classAttr.includes('more') || classAttr.includes('load') ||
                                   idAttr.includes('more') || idAttr.includes('load')) &&
                                   el.offsetParent !== null;  // 确保元素可见
                        });
                    
                    if (possibleLoadMoreElements.length > 0) {
                        console.log('找到可能的加载更多元素:', possibleLoadMoreElements.length);
                        for (const el of possibleLoadMoreElements) {
                            try {
                                el.scrollIntoView({behavior: 'smooth', block: 'center'});
                                setTimeout(() => el.click(), 500);
                                return true;
                            } catch (e) {
                                console.log('点击元素失败:', e);
                            }
                        }
                    }
                    
                    return false;
                }
            """)
            
            if success:
                logger.info("JavaScript分析触发加载更多可能成功")
                time.sleep(3)  # 给足够的时间加载
                
                # 检查内容是否增加
                new_height = self.page.evaluate("document.body.scrollHeight")
                new_content_count = len(self.page.query_selector_all(".telegraph-item, [class*='telegraph-item'], .article-item, [class*='article-item']"))
                
                if new_height > old_height + 5 or new_content_count > old_content_count:
                    logger.info(f"JavaScript分析成功: 内容从 {old_content_count} 增加到 {new_content_count} 个元素")
                    return True
            
            # 尝试更复杂的分步滚动
            logger.info("尝试分步滚动页面")
            heights = [old_height // 4, old_height // 2, (old_height * 3) // 4, old_height]
            
            for height in heights:
                self.page.evaluate(f"window.scrollTo(0, {height});")
                time.sleep(1)
            
            # 最终再次检查内容是否增加
            final_height = self.page.evaluate("document.body.scrollHeight")
            final_content_count = len(self.page.query_selector_all(".telegraph-item, [class*='telegraph-item'], .article-item, [class*='article-item']"))
            
            if final_height > old_height + 5 or final_content_count > old_content_count:
                logger.info(f"分步滚动成功: 内容从 {old_content_count} 增加到 {final_content_count} 个元素")
                return True
            
            logger.info("所有加载更多尝试均失败")
            return False
            
        except Exception as e:
            logger.error(f"加载更多帖子时出错: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    def scrape_section(self, section: str) -> List[Dict[str, Any]]:
        """
        抓取指定板块的电报内容

        Args:
            section: 要抓取的板块名称，如"看盘"或"公司"

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
            logger.info(f"确保当前页面是 '{section}' 板块")
            
            try:
                current_url = self.page.url
                current_content = self.page.content()
                
                if section == "看盘" and "kanpan" not in current_url.lower() and "看盘" not in current_content:
                    logger.info(f"当前页面不是看盘板块，尝试导航")
                    self.navigate_to_telegraph_section("看盘")
                elif section == "公司" and "company" not in current_url.lower() and "公司" not in current_content:
                    logger.info(f"当前页面不是公司板块，尝试导航")
                    self.navigate_to_telegraph_section("公司")
                
                # 等待页面完全加载
                time.sleep(2)
                self.page.wait_for_load_state("networkidle")
            except Exception as e:
                logger.error(f"确认和导航到正确板块时出错: {e}")
            
            # 立即提取第一页数据
            logger.info("立即提取第一页数据")
            posts, reached_cutoff = self.extract_posts_from_page()
            
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
                    
                    # 把标题加入已处理集合
                    processed_titles.add(post["title"])
                    
                    # 分析帖子
                    result = self.analyze_post(post)
                    result["section"] = section  # 添加板块信息
                    
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
                if not self.load_more_posts():
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
                new_posts, reached_cutoff = self.extract_posts_from_page()
                
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
                    result["section"] = section  # 添加板块信息
                    
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
            logger.info(f"'{section}'板块爬取完成，经过 {load_more_attempts} 次翻页尝试，获取 {len(section_results)} 条结果")

        except Exception as e:
            logger.error(f"爬取'{section}'板块时出错: {e}")
            import traceback
            logger.error(traceback.format_exc())

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
            total_posts_found = 0  # 跟踪找到的符合条件的帖子总数

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
                    
                    # 如果该板块没有符合条件的帖子，记录并继续下一个板块
                    if len(section_results) == 0:
                        logger.warning(f"在'{section}'板块未找到符合截止日期 {self.cutoff_date} 之后的帖子")
                        continue
                        
                    total_posts_found += len(section_results)
                    self.results.extend(section_results)
                    logger.info(f"'{section}'板块爬取完成，获取到{len(section_results)}条电报")
                    
                except Exception as e:
                    logger.error(f"爬取'{section}'板块时出错: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
            
            # 结果汇总
            if total_posts_found == 0:
                logger.warning(f"未找到任何符合截止日期 {self.cutoff_date} 之后的帖子，请考虑调整日期范围或检查网站结构")
            else:
                logger.info(f"共找到 {total_posts_found} 条符合截止日期 {self.cutoff_date} 之后的帖子")

            return self.results

        except Exception as e:
            logger.error(f"运行电报爬虫时出错: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return self.results 