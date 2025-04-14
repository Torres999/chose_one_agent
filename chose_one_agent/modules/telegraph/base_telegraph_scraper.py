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
        self.selectors = []  # 可由子类覆盖的选择器列表
        self.results = []    # 存储爬取结果

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
            "comment_count": post_info["comment_count"],
            "section": post_info.get("section", "未知板块")  # 确保板块信息被保留
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
        导航到电报的某个子板块
        
        Args:
            section: 要导航到的子板块，如"看盘"或"公司"
            
        Returns:
            是否成功导航到指定板块
        """
        clicked = False
        max_retries = 3
        current_retry = 0
        
        try:
            # 设置更长的超时时间，处理网络慢的情况
            page_timeout = 60000  # 60秒超时
            
            # 首先导航到网站首页
            logger.info("导航到网站首页")
            try:
                # 尝试使用更长的超时时间导航到网站
                self.page.goto(self.base_url, timeout=page_timeout, wait_until="domcontentloaded")
                
                # 等待页面加载完成
                self.page.wait_for_load_state("networkidle", timeout=page_timeout)
                logger.info("网站首页加载完成")
            except Exception as e:
                logger.warning(f"导航到网站首页时出现异常: {e}，尝试直接操作当前页面")
                # 即使导航失败，也继续尝试操作页面上的元素
            
            # 尝试点击顶部导航栏中的"电报"按钮
            logger.info("尝试点击顶部导航栏中的'电报'按钮")
            
            # 直接访问电报页面
            try:
                self.page.goto(f"{self.base_url}/telegraph", timeout=page_timeout, wait_until="domcontentloaded")
                self.page.wait_for_load_state("networkidle", timeout=30000)
                logger.info("直接访问电报页面成功")
            except Exception as e:
                logger.warning(f"直接访问电报页面失败: {e}，尝试通过点击导航")
                # 如果直接访问失败，尝试通过点击导航
                clicked = False
                
                # 增加更多选择器，尝试找到电报导航元素
                selectors = [
                    "a:has-text('电报')",
                    "a.telegraph-link",
                    "a[href*='telegraph']",
                    "a.nav-link:has-text('电报')",
                    "li.nav-item a:has-text('电报')"
                ]
                
                for selector in selectors:
                    try:
                        logger.info(f"使用选择器 '{selector}' 查找电报导航元素")
                        elements = self.page.query_selector_all(selector)
                        logger.info(f"使用选择器 '{selector}' 找到 {len(elements)} 个可能的电报导航元素")
                        
                        if elements and len(elements) > 0:
                            # 点击第一个匹配的元素
                            elements[0].click(timeout=10000)
                            self.page.wait_for_load_state("networkidle", timeout=10000)
                            clicked = True
                            logger.info("成功点击顶部导航栏中的'电报'按钮")
                            break
                    except Exception as e:
                        logger.debug(f"使用选择器 '{selector}' 点击电报导航元素失败: {e}")
                
                # 如果所有选择器都失败，尝试使用JavaScript点击
                if not clicked:
                    try:
                        logger.info("尝试通过JavaScript点击'电报'导航")
                        self.page.evaluate("""
                            () => {
                                // 尝试各种方法找到电报导航元素
                                const links = Array.from(document.querySelectorAll('a')).filter(a => 
                                    a.textContent.includes('电报') || 
                                    a.href.includes('telegraph')
                                );
                                if (links.length > 0) {
                                    links[0].click();
                                    return true;
                                }
                                return false;
                            }
                        """)
                        self.page.wait_for_timeout(2000)
                        clicked = True
                    except Exception as e:
                        logger.warning(f"通过JavaScript点击'电报'导航失败: {e}")
            
            # 检查是否在电报页面
            current_url = self.page.url
            if "telegraph" in current_url or "电报" in current_url:
                logger.info(f"已经在电报页面: {current_url}")
            else:
                logger.warning(f"可能未能导航到电报页面，当前URL: {current_url}")
            
            # 在电报页面上尝试点击子导航（如看盘、公司等）
            logger.info(f"尝试在电报页面上点击'{section}'子导航")
            clicked = False
            
            # 直接处理从截图看到的页面结构
            selectors = [
                f"a:has-text('{section}')",
                f".tabs a:has-text('{section}')",
                f".sub-nav a:has-text('{section}')",
                f"nav.secondary-nav a:has-text('{section}')",
                f"[role='tablist'] a:has-text('{section}')",
                f"a.tab:has-text('{section}')"
            ]
            
            for selector in selectors:
                try:
                    elements = self.page.query_selector_all(selector)
                    if elements and len(elements) > 0:
                        # 尝试点击第一个匹配的元素
                        try:
                            elements[0].click()
                            self.page.wait_for_load_state("networkidle", timeout=5000)
                            clicked = True
                            logger.info(f"成功点击电报页面下的'{section}'子导航")
                            
                            # 确认是否成功切换到该板块
                            active_tabs = self.page.query_selector_all("[role='tab'][aria-selected='true'], .tab.active, .selected-tab")
                            for tab in active_tabs:
                                tab_text = tab.inner_text().strip()
                                if tab_text == section:
                                    logger.info(f"确认已切换到'{section}'板块")
                                    return True
                            break
                        except Exception as e:
                            logger.debug(f"点击'{section}'选项卡时出错: {e}")
                except Exception as e:
                    logger.debug(f"使用选择器查找'{section}'选项卡时出错: {e}")
            
            # 如果常规方法未能点击，尝试更直接的点击方法
            if not clicked:
                logger.warning(f"常规方法未能点击'{section}'子导航，尝试更直接的点击方法")
                
                # 尝试通过JavaScript点击子导航
                logger.info(f"尝试通过JavaScript点击'{section}'子导航")
                try:
                    js_result = self.page.evaluate(f"""
                        () => {{
                            const sectionText = '{section}';
                            // 尝试查找各种可能的导航元素
                            const elements = Array.from(document.querySelectorAll('a, div[role="tab"], .tab, button')).filter(el => 
                                el.textContent.trim() === sectionText ||
                                el.textContent.trim().includes(sectionText)
                            );
                            
                            if (elements.length > 0) {{
                                // 点击第一个匹配的元素
                                elements[0].click();
                                return true;
                            }}
                            return false;
                        }}
                    """)
                    
                    if js_result:
                        clicked = True
                        logger.info(f"通过JavaScript成功点击'{section}'子导航")
                        self.page.wait_for_timeout(2000)  # 等待页面响应
                except Exception as e:
                    logger.error(f"JavaScript点击'{section}'子导航失败: {e}")
            
            # 如果还是无法点击，但我们已经在电报页面，可以考虑直接解析页面内容
            if not clicked and (("telegraph" in self.page.url) or ("电报" in self.page.url)):
                logger.warning(f"未能点击'{section}'子导航，但已在电报页面，将直接解析页面内容")
                return True  # 返回True，让程序继续尝试解析页面内容
            
            return clicked

        except Exception as e:
            logger.error(f"导航到电报{section}板块时出错: {e}")
            import traceback
            logger.error(traceback.format_exc())
            
            # 如果是最后一次重试失败，但我们已经加载了某个页面，仍然返回True
            # 让程序继续尝试解析可能存在的内容
            if current_retry >= max_retries - 1 and self.page.url and len(self.page.url) > 0:
                logger.warning(f"导航失败但已加载页面，将尝试解析当前页面内容: {self.page.url}")
                return True
                
            return False

    def extract_post_info(self, element) -> Dict[str, Any]:
        """
        从电报项元素中提取信息，可由子类覆盖以实现特定逻辑

        Args:
            element: 电报项网页元素

        Returns:
            包含帖子信息的字典
        """
        try:
            element_text = element.inner_text()
            
            # 初始化结果
            result = {
                "title": "未知标题",
                "date": "未知日期",
                "time": "未知时间",
                "comment_count": 0,
                "element": element,
                "is_valid_post": False,
                "section": "未知板块"  # 添加板块字段
            }
            
            # 首先提取时间，判断是否是有效的帖子
            time_match = re.search(r'(\d{2}:\d{2}:\d{2})', element_text)
            if time_match:
                result["time"] = time_match.group(1)
            else:
                # 如果没有时间，可能不是有效帖子
                return {"is_valid_post": False, "section": "未知板块"}
            
            # 提取日期 (YYYY.MM.DD)
            date_match = re.search(r'(\d{4}\.\d{2}\.\d{2})', element_text)
            if date_match:
                result["date"] = date_match.group(1)
            else:
                # 如果没有找到日期，默认使用当天日期，因为帖子可能是今天发布的
                today = datetime.datetime.now().strftime("%Y.%m.%d")
                result["date"] = today
                logger.debug(f"未找到日期，默认使用当天日期: {today}")
            
            # 尝试从标题格式判断是否为帖子
            is_likely_post = False
            
            # 提取标题
            title_patterns = [
                r'【([^】]+)】',  # 尖括号格式
                r'\[([^\]]+)\]',  # 方括号格式
            ]
            
            for pattern in title_patterns:
                match = re.search(pattern, element_text)
                if match:
                    result["title"] = match.group(1)
                    is_likely_post = True
                    break
            
            # 提取评论数
            comment_patterns = [
                r'评论\s*[(\[](\d+)[)\]]',  # 评论(N) 或 评论[N]
                r'评论[：:]\s*(\d+)'        # 评论: N 或 评论：N
            ]
            
            for pattern in comment_patterns:
                match = re.search(pattern, element_text)
                if match:
                    try:
                        result["comment_count"] = int(match.group(1))
                        is_likely_post = True  # 有评论计数，更可能是帖子
                        break
                    except ValueError:
                        pass
            
            # 如果有日期和时间但没有标题，可能需要进一步处理
            if result["time"] != "未知时间" and result["title"] == "未知标题":
                # 尝试提取时间后的第一行文本作为标题
                time_str = result["time"]
                time_content_match = re.search(re.escape(time_str) + r'\s+(.+?)(?=\s*\d|\s*$)', element_text)
                if time_content_match:
                    result["title"] = time_content_match.group(1).strip()
                    is_likely_post = True
                # 如果还没提取到标题，尝试其他方法
                elif "：" in element_text:
                    # 查找冒号后面的内容作为标题
                    colon_match = re.search(r'[：:]\s*(.+?)(?=\s*\d|\s*$)', element_text)
                    if colon_match:
                        result["title"] = colon_match.group(1).strip()
                        is_likely_post = True
            
            # 如果元素包含"阅读"或"分享"，更可能是帖子
            if "阅读" in element_text or "分享" in element_text:
                is_likely_post = True
                
            # 验证有效性 - 即使没有日期，只要有时间和标题，也认为是有效帖子
            if is_likely_post and result["time"] != "未知时间" and result["title"] != "未知标题":
                result["is_valid_post"] = True
                
            return result
            
        except Exception as e:
            logger.error(f"提取帖子信息时出错: {e}")
            return {"is_valid_post": False, "section": "未知板块"}
    
    def scrape_section(self, section_name: str) -> List[Dict[str, Any]]:
        """
        通用的板块爬取方法，子类可以复用或覆盖

        Args:
            section_name: 要爬取的板块名称

        Returns:
            处理后的电报内容列表
        """
        from chose_one_agent.modules.telegraph.post_extractor import PostExtractor
        
        section_results = []
        processed_titles = set()  # 用于跟踪已处理的帖子标题，避免重复
        post_extractor = PostExtractor()
        
        # 用于跟踪不符合日期条件的帖子数量
        outdated_posts_count = 0
        # 连续出现不符合条件的帖子的最大次数，超过此值则停止加载
        max_outdated_posts = 5
        
        try:
            # 获取第一页数据
            posts, _ = post_extractor.extract_posts_from_page(self.page)
            
            # 如果第一页没有数据，直接返回
            if not posts:
                return section_results
                
            # 处理第一页数据
            for post in posts:
                # 添加板块信息
                post["section"] = section_name
                
                # 跳过重复帖子
                if post["title"] in processed_titles:
                    continue
                
                # 检查日期是否在有效范围内
                if post["date"] != "未知日期":
                    try:
                        post_date = parse_datetime(post["date"], post["time"])
                        # 添加日志，帮助调试日期比较问题
                        if not is_in_date_range(post_date, self.cutoff_date):
                            outdated_posts_count += 1
                            logger.debug(f"跳过不符合日期条件的帖子: {post['title']}, 日期: {post['date']} {post['time']}, 截止日期: {self.cutoff_date}")
                            continue
                        else:
                            logger.debug(f"符合日期条件的帖子: {post['title']}, 日期: {post['date']} {post['time']}, 截止日期: {self.cutoff_date}")
                    except Exception as e:
                        # 日期解析失败，仍然处理该帖子
                        logger.warning(f"日期解析失败，仍然处理该帖子: {post['title']}, 错误: {e}")
                        pass
                
                # 记录标题并分析帖子
                processed_titles.add(post["title"])
                result = self.analyze_post(post)
                
                # 确保板块信息被保留
                if "section" not in result or not result["section"] or result["section"] == "未知板块":
                    result["section"] = section_name
                
                section_results.append(result)
            
            # 如果第一页已经有多个帖子不符合日期条件，可能不需要加载更多
            if outdated_posts_count >= max_outdated_posts:
                logger.info(f"第一页已发现{outdated_posts_count}个不符合日期条件的帖子，不再加载更多内容")
                return section_results
            
            # 尝试加载更多内容
            load_attempts = 0
            max_attempts = 3
            
            while load_attempts < max_attempts:
                load_attempts += 1
                
                # 尝试加载更多内容
                if not post_extractor.load_more_posts(self.page):
                    logger.info("无法加载更多内容，已到达页面底部")
                    break
                
                # 提取新加载的帖子
                new_posts, _ = post_extractor.extract_posts_from_page(self.page)
                
                # 如果没有新帖子，停止尝试
                if not new_posts:
                    logger.info("加载后未发现新帖子，停止尝试")
                    break
                
                # 重置连续不符合条件的帖子计数
                consecutive_outdated = 0
                
                # 处理新帖子
                for post in new_posts:
                    # 添加板块信息
                    post["section"] = section_name
                    
                    # 跳过重复帖子
                    if post["title"] in processed_titles:
                        continue
                    
                    # 检查日期是否在有效范围内
                    if post["date"] != "未知日期":
                        try:
                            post_date = parse_datetime(post["date"], post["time"])
                            # 添加日志，帮助调试日期比较问题
                            if not is_in_date_range(post_date, self.cutoff_date):
                                outdated_posts_count += 1
                                consecutive_outdated += 1
                                logger.debug(f"跳过不符合日期条件的帖子: {post['title']}, 日期: {post['date']} {post['time']}, 截止日期: {self.cutoff_date}")
                                
                                # 如果连续出现多个不符合条件的帖子，认为已经到达了时间边界，停止加载
                                if consecutive_outdated >= max_outdated_posts:
                                    logger.info(f"连续发现{consecutive_outdated}个不符合日期条件的帖子，停止加载更多内容")
                                    return section_results
                                
                                continue
                            else:
                                logger.debug(f"符合日期条件的帖子: {post['title']}, 日期: {post['date']} {post['time']}, 截止日期: {self.cutoff_date}")
                        except Exception as e:
                            # 日期解析失败，仍然处理该帖子
                            logger.warning(f"日期解析失败，仍然处理该帖子: {post['title']}, 错误: {e}")
                            pass
                    
                    # 找到符合条件的帖子，重置连续计数
                    consecutive_outdated = 0
                    
                    # 记录标题并分析帖子
                    processed_titles.add(post["title"])
                    result = self.analyze_post(post)
                    
                    # 确保板块信息被保留
                    if "section" not in result or not result["section"] or result["section"] == "未知板块":
                        result["section"] = section_name
                    
                    section_results.append(result)
            
            logger.info(f"'{section_name}'板块爬取完成，获取 {len(section_results)} 条结果，跳过 {outdated_posts_count} 条不符合日期条件的帖子")
            return section_results
            
        except Exception as e:
            logger.error(f"爬取'{section_name}'板块时出错: {e}")
            return section_results 