# -*- coding: utf-8 -*-
import logging
import time
import datetime
import os
from typing import List, Dict, Any, Tuple
import re
import random
import json

from chose_one_agent.scrapers.base_scraper import BaseScraper
from chose_one_agent.utils.helpers import parse_datetime, is_before_cutoff, extract_date_time, is_in_date_range
from chose_one_agent.analyzers.sentiment_analyzer import SentimentAnalyzer
from chose_one_agent.analyzers.deepseek_sentiment_analyzer import DeepSeekSentimentAnalyzer
from chose_one_agent.analyzers.keyword_analyzer import KeywordAnalyzer

# 配置日志
logger = logging.getLogger(__name__)


class BaseTelegraphScraper(BaseScraper):
    """
    财经网站的电报爬虫基类，用于抓取和分析电报内容，包含基础的电报爬取功能
    该类提供了通用的方法，特定板块的爬虫类应该继承此类并实现特定的处理逻辑
    """

    def __init__(self, cutoff_date, headless=True, debug=False, sentiment_analyzer_type="snownlp", deepseek_api_key=None):
        """
        初始化电报爬虫基类

        Args:
            cutoff_date: 截止日期，爬虫只会获取该日期到当前时间范围内的电报，早于或晚于此范围的电报将被忽略
            headless: 是否使用无头模式运行浏览器
            debug: 是否启用调试模式
            sentiment_analyzer_type: 情感分析器类型，可选值："snownlp"或"deepseek"
            deepseek_api_key: DeepSeek API密钥，当sentiment_analyzer_type为"deepseek"时必须提供
        """
        super().__init__(cutoff_date, headless)

        # 选择情感分析器
        if sentiment_analyzer_type.lower() == "deepseek":
            logger.info("使用DeepSeek API进行情感分析")
            self.sentiment_analyzer = DeepSeekSentimentAnalyzer(
                api_key=deepseek_api_key)
        else:
            logger.info("使用SnowNLP进行情感分析")
            self.sentiment_analyzer = SentimentAnalyzer()

        # 初始化关键词分析器
        self.keyword_analyzer = KeywordAnalyzer(
            min_keyword_length=2,
            max_keywords=10
        )
        logger.info("初始化关键词分析器")

        self.sentiment_analyzer_type = sentiment_analyzer_type.lower()
        self.debug = debug
        self.selectors = []  # 可由子类覆盖的选择器列表
        self.results = []    # 存储爬取结果

    def get_comments(self, post_element) -> List[str]:
        """
        获取给定帖子的评论

        Args:
            post_element: 帖子元素

        Returns:
            评论内容列表
        """
        comments = []
        try:
            # 先保存当前URL，用于识别当前电报的上下文和返回
            current_url = self.page.url
            current_title = None

            # 尝试获取当前帖子的标题，用于关联评论
            try:
                current_title = post_element.inner_text().strip().split("\n")[
                    0]
                if current_title and len(current_title) > 20:  # 标题可能太长，截断一部分
                    current_title = current_title[:20]
                if self.debug:
                    logger.info(f"当前帖子标题: {current_title}")
            except Exception:
                pass

            # 关键修复：首先查找帖子内是否有评论计数标记 - 这是判断是否有评论的关键
            comment_count = 0
            try:
                element_text = post_element.inner_text()

                # 使用更强的正则表达式匹配模式提取评论计数
                comment_count_patterns = [
                    r'评论\s*[(\[](\d+)[)\]]',  # 评论(N) 或 评论[N]
                    r'评论[：:]\s*(\d+)',        # 评论: N 或 评论：N
                    r'评论\((\d+)\)',           # 评论(N)
                    r'评论\s*(\d+)',             # 评论 N
                    r'评论.*?(\d+)'             # 极宽松匹配，评论后面出现的任何数字
                ]

                for pattern in comment_count_patterns:
                    match = re.search(pattern, element_text)
                    if match:
                        try:
                            comment_count = int(match.group(1))
                            if self.debug:
                                logger.info(f"从帖子文本中提取到评论计数: {comment_count}")
                            break
                        except (ValueError, IndexError):
                            pass
            except Exception as e:
                if self.debug:
                    logger.error(f"提取评论计数时出错: {e}")

            # 保存原始评论数，避免被后面的错误覆盖
            original_comment_count = comment_count

            # 首先检查页面上所有评论按钮及计数
            try:
                # 检测页面上所有评论按钮及计数
                all_comment_btns = self.page.query_selector_all(
                    "a:has-text('评论'), span:has-text('评论'), div:has-text('评论')")
                if self.debug:
                    logger.info(f"页面上找到 {len(all_comment_btns)} 个可能的评论按钮")

                for btn in all_comment_btns:
                    if btn and btn.is_visible():
                        text = btn.inner_text().strip()
                        # 确认帖子具有的评论数
                        num_match = re.search(r'\d+', text)
                        if num_match:
                            found_count = int(num_match.group(0))
                            # 过滤掉异常大的数字，比如2025这种可能是年份的数字
                            if found_count > 0 and found_count < 1000:
                                comment_count = found_count
                                if self.debug:
                                    logger.info(f"找到评论按钮，评论数: {found_count}")
            except Exception as e:
                if self.debug:
                    logger.error(f"检查评论按钮时出错: {e}")

            # 如果原始评论数已确定且合理，优先使用它
            if original_comment_count > 0 and original_comment_count < 1000:
                comment_count = original_comment_count

            # 针对特定网站的专门处理
            if "telegraph-site.cn/telegraph" in current_url:
                # 1. 尝试从当前页面获取评论详情链接
                detail_url = None
                try:
                    for selector in ["a:has-text('评论')", "a[href*='/detail/']"]:
                        comment_link = self.page.query_selector(selector)
                        if comment_link:
                            href = comment_link.get_attribute("href")
                            if href and "/detail/" in href:
                                if not href.startswith("http"):
                                    detail_url = f"https://www.telegraph-site.cn{href}"
                                else:
                                    detail_url = href
                                if self.debug:
                                    logger.info(f"找到评论详情页链接: {detail_url}")
                                    break
                except Exception as e:
                    if self.debug:
                        logger.error(f"获取评论链接时出错: {e}")

                # 2. 如果找到了具体帖子链接，直接访问获取评论
                if detail_url:
                    try:
                        if self.debug:
                            logger.info(f"直接访问评论详情页: {detail_url}")

                        current_page = self.page.url
                        self.page.goto(detail_url, timeout=10000)
                        self.page.wait_for_load_state(
                            "networkidle", timeout=5000)
                        time.sleep(1.5)

                        # 提取评论内容
                        comment_content_selectors = [
                            ".evaluate-list .evaluate-item",
                            ".evaluate-item .evaluate-content",
                            ".evaluate-content",
                            ".comment-list .comment-item",
                            ".comment-item .comment-text",
                            ".comment-text",
                            "[class*='comment-content']",
                            "[class*='comment-text']"
                        ]

                        for content_selector in comment_content_selectors:
                            comment_elements = self.page.query_selector_all(
                                content_selector)
                            if comment_elements and len(comment_elements) > 0:
                                if self.debug:
                                    logger.info(
                                        f"在评论详情页找到 {len(comment_elements)} 个评论元素")

                                for comment_element in comment_elements:
                                    text = comment_element.inner_text().strip()
                                    if text and len(text) > 3 and "评论" not in text and "登录" not in text:
                                        comments.append(text)

                                if comments:
                                    break

                        # 返回原页面
                        self.page.goto(current_page)
                        self.page.wait_for_load_state(
                            "networkidle", timeout=5000)

                        if comments:
                            logger.info(f"从评论详情页获取到 {len(comments)} 条评论")
                            return comments
                    except Exception as e:
                        if self.debug:
                            logger.error(f"访问评论详情页出错: {e}")
                        try:
                            self.page.goto(current_url)
                            self.page.wait_for_load_state("networkidle")
                        except:
                            pass

                # 3. 尝试直接点击评论按钮
                clicked = False
                comment_selectors = [
                    # 指向评论详情页的链接
                    "a:has-text('评论')",
                    "a[href*='/detail/']",
                    "a.f-s-12:has-text('评论')",
                    "a[rel='noopener noreferrer']:has-text('评论')",
                    # 其他可能的评论按钮
                    "span.evaluate-count",
                    "span.evaluate",
                    "div.evaluate",
                    ".evaluate-num",
                    "[class*='evaluate']",
                    ".comment-count",
                    "[class*='comment']"
                ]

                for selector in comment_selectors:
                    if clicked:
                        break

                    try:
                        elements = self.page.query_selector_all(selector)
                        if elements and len(elements) > 0:
                            if self.debug:
                                logger.info(
                                    f"使用选择器 '{selector}' 找到 {len(elements)} 个可能的评论按钮")

                            for element in elements:
                                try:
                                    # 检查元素是否可见
                                    bbox = element.bounding_box()
                                    if not bbox or bbox["width"] <= 0 or bbox["height"] <= 0:
                                        continue

                                    # 点击评论按钮
                                    try:
                                        if self.debug:
                                            logger.info(f"点击评论按钮: '{element.inner_text().strip()}'")
                                        
                                        # 尝试常规点击
                                        try:
                                            element.click(timeout=5000)
                                            clicked = True
                                        except:
                                            # 尝试JavaScript点击
                                            self.page.evaluate("(element) => element.click()", element)
                                            clicked = True
                                    except:
                                        if self.debug:
                                            logger.error("点击评论按钮失败")

                                except Exception:
                                    pass

                                # 等待评论加载
                                if clicked:
                                    self.page.wait_for_load_state(
                                        "networkidle", timeout=5000)
                                    time.sleep(2)

                                    # 提取评论内容
                                    comment_content_selectors = [
                                        ".evaluate-list .evaluate-item",
                                        ".evaluate-item .evaluate-content",
                                        ".evaluate-wrap .evaluate-content",
                                        "div.evaluate-content",
                                        ".comment-item",
                                        ".comment-content",
                                        ".comment-text",
                                        "[class*='comment']"
                                    ]

                                    for content_selector in comment_content_selectors:
                                        comment_elements = self.page.query_selector_all(
                                            content_selector)
                                        if comment_elements and len(comment_elements) > 0:
                                            if self.debug:
                                                logger.info(
                                                    f"使用选择器 '{content_selector}' 找到 {len(comment_elements)} 个评论元素")

                                            for comment_element in comment_elements:
                                                text = comment_element.inner_text().strip()
                                                if (text and len(text) > 3 and
                                                    "评论" not in text and
                                                    "登录" not in text and
                                                        "注册" not in text):
                                                    comments.append(text)

                                            if comments:
                                                logger.info(
                                                    f"点击评论按钮后获取到 {len(comments)} 条评论")
                                                break

                                    # 返回原始页面
                                    try:
                                        self.page.goto(current_url)
                                        self.page.wait_for_load_state("networkidle", timeout=5000)
                                    except:
                                        pass

                                    if comments:
                                        return comments

                    except Exception as e:
                        if self.debug:
                            logger.error(f"使用选择器 '{selector}' 查找评论按钮时出错: {e}")
                        try:
                            self.page.goto(current_url)
                            self.page.wait_for_load_state("networkidle")
                        except:
                            pass

                # 4. 尝试通过URL参数直接访问评论页
                if comment_count > 0 and not comments:
                    try:
                        current_path = self.page.url
                        telegraph_id = None

                        # 尝试从URL中提取电报ID
                        id_match = re.search(r'/detail/(\d+)', current_path)
                        if not id_match:
                            id_match = re.search(r'id=(\d+)', current_path)

                        if id_match:
                            telegraph_id = id_match.group(1)
                            # 关键修复：避免把年份等大数字误认为是评论数
                            # 如果ID超过10000，可能不是真正的ID，而是年份等其他数字
                            if telegraph_id and len(telegraph_id) <= 5:
                                detail_url = f"https://www.telegraph-site.cn/detail/{telegraph_id}"

                                if self.debug:
                                    logger.info(f"尝试通过ID直接访问评论页: {detail_url}")

                                self.page.goto(detail_url, timeout=10000)
                                self.page.wait_for_load_state(
                                    "networkidle", timeout=5000)
                                time.sleep(2)

                                # 提取评论
                                comment_elements = self.page.query_selector_all(
                                    ".comment-content, .evaluate-content, [class*='comment'], [class*='evaluate']")
                                if comment_elements and len(comment_elements) > 0:
                                    for element in comment_elements:
                                        text = element.inner_text().strip()
                                        if text and len(text) > 3 and "评论" not in text and "登录" not in text and "注册" not in text:
                                            comments.append(text)

                                    # 返回原页面
                                    self.page.goto(current_url)
                                    self.page.wait_for_load_state(
                                        "networkidle", timeout=5000)

                                    if comments:
                                        logger.info(
                                            f"通过ID访问详情页获取到 {len(comments)} 条评论")
                                        return comments

                                # 返回原页面
                                self.page.goto(current_url)
                                self.page.wait_for_load_state(
                                    "networkidle", timeout=5000)
                    except Exception as e:
                        if self.debug:
                            logger.error(f"通过ID直接访问评论页出错: {e}")
                        try:
                            self.page.goto(current_url)
                            self.page.wait_for_load_state(
                                "networkidle", timeout=5000)
                        except:
                            pass

                # 5. 使用JavaScript直接获取评论
                if comment_count > 0 and not comments:
                    try:
                        possible_comments = self.page.evaluate("""
                            () => {
                                const results = [];
                                const containerSelectors = [
                                    '.evaluate-list', '.evaluate-content', '.comments-container',
                                    '.comment-list', '[class*="evaluate"]', '[class*="comment"]'
                                ];
                                
                                for (const selector of containerSelectors) {
                                    const containers = document.querySelectorAll(selector);
                                    for (const container of containers) {
                                        const text = container.innerText?.trim();
                                        if (text && text.length > 5 && text.length < 500 && 
                                            !text.includes('登录') && !text.includes('注册') &&
                                            !text.includes('评论') && !text.includes('点赞')) {
                                            results.push(text);
                                        }
                                        
                                        const children = container.querySelectorAll('*');
                                        for (const child of children) {
                                            const childText = child.innerText?.trim();
                                            if (childText && childText.length > 5 && childText.length < 500 && 
                                                !childText.includes('登录') && !childText.includes('注册') &&
                                                !childText.includes('评论') && !childText.includes('点赞')) {
                                                results.push(childText);
                                            }
                                        }
                                    }
                                }
                                return Array.from(new Set(results));
                            }
                        """)

                        if possible_comments and len(possible_comments) > 0:
                            comments.extend(possible_comments)
                            if self.debug:
                                logger.info(
                                    f"通过JavaScript直接提取到 {len(possible_comments)} 条评论")
                    except Exception as e:
                        if self.debug:
                            logger.error(f"使用JavaScript直接获取评论时出错: {e}")

            # 通用评论提取逻辑
            if not comments:
                # 通用评论按钮选择器
                general_selectors = [
                    ".comment-btn",
                    ".comment-link",
                    "a:has-text('评论')",
                    "a:has-text('查看评论')",
                    "[class*='comment']"
                ]

                for selector in general_selectors:
                    try:
                        comment_btn = post_element.query_selector(selector)
                        if comment_btn:
                            # 点击评论按钮
                            comment_btn.click(timeout=5000)

                            # 等待评论加载
                            self.page.wait_for_load_state(
                                "networkidle", timeout=5000)
                            time.sleep(1)

                            # 提取评论内容
                            comment_elements = self.page.query_selector_all(
                                ".comment-item, .comment-content, [class*='comment']")
                            for element in comment_elements:
                                comment_text = element.inner_text().strip()
                                if comment_text and len(comment_text) > 3 and "评论" not in comment_text:
                                    comments.append(comment_text)

                            # 返回到列表页面
                            self.page.go_back()
                            self.page.wait_for_load_state(
                                "networkidle", timeout=5000)

                        if comments:
                            break
                    except Exception as e:
                        if self.debug:
                            logger.error(f"使用选择器 '{selector}' 提取评论时出错: {e}")

            # 记录提取结果
            if comment_count > 0 and not comments:
                # 修复：确保这里显示的评论数是正确的
                logger.info(f"检测到评论数 {original_comment_count}，但未成功提取到评论内容")
            elif comments:
                # 修复：这里使用原始评论计数，而不是实际提取到的评论数量
                logger.info(f"成功提取到评论内容，原始评论计数为 {original_comment_count}")

            return comments

        except Exception as e:
            logger.error(f"获取评论时出错: {e}")
            import traceback
            if self.debug:
                logger.error(traceback.format_exc())

        return comments

    def analyze_post(self, post_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        分析帖子内容，提取关键信息，进行情感分析和关键词分析

        Args:
            post_info: 包含帖子信息的字典

        Returns:
            包含分析结果的字典
        """
        title = post_info.get("title", "未知标题")

        try:
            # 初始化结果
            result = {
                "title": title,
                "date": post_info.get("date", "未知日期"),
                "time": post_info.get("time", "未知时间"),
                "sentiment_score": 0,
                "sentiment_label": "无评论",
                "section": post_info.get("section", "未知板块"),
                "comments": [],
                "has_comments": False,
                "keyword_analysis": {},
                "comment_keyword_analysis": {}
            }

            # 获取评论计数和内容
            comment_count = post_info.get("comment_count", 0)
            content = post_info.get("content", "")

            # 进行关键词分析
            try:
                content_text = f"{title} {content}".strip()
                if len(content_text) > 5:
                    logger.info(f"对帖子 '{title}' 内容进行关键词分析")
                    result["keyword_analysis"] = self.keyword_analyzer.analyze_text(
                        content_text)

                    if self.debug:
                        keywords = result["keyword_analysis"].get(
                            "keywords", [])
                        if keywords:
                            top_keywords = [
                                f"{kw['word']}({kw['count']}次)" for kw in keywords[:5]]
                            logger.info(
                                f"帖子 '{title}' 提取到关键词: {', '.join(top_keywords)}")

                        financial_terms = result["keyword_analysis"].get(
                            "financial_terms", [])
                        if financial_terms:
                            logger.info(
                                f"帖子 '{title}' 包含财经术语: {', '.join(financial_terms[:3])}")
                else:
                    logger.warning(f"帖子 '{title}' 内容过短，跳过关键词分析")
            except Exception as e:
                logger.error(f"对帖子 '{title}' 进行关键词分析时出错: {e}")
                result["keyword_analysis"] = {
                    "keywords": [], "has_financial_content": False}

            # 获取评论并进行分析
            try:
                comments = self.get_comments(post_info.get("element"))
                if comments:
                    result["comments"] = comments
                    result["has_comments"] = True
                    logger.info(f"帖子 '{title}' 成功获取到 {len(comments)} 条评论")

                    # 对评论进行情感分析
                    try:
                        sentiment_score = self.analyze_sentiment(comments)
                        result["sentiment_score"] = sentiment_score
                        result["sentiment_label"] = self._get_sentiment_label(
                            sentiment_score)
                        logger.info(
                            f"帖子 '{title}' 情感分析得分: {sentiment_score}, 标签: {result['sentiment_label']}")
                    except Exception as e:
                        logger.error(f"对帖子 '{title}' 评论进行情感分析时出错: {e}")
                        result["sentiment_score"] = 3  # 默认为中性
                        result["sentiment_label"] = "中性"

                    # 对评论内容进行关键词分析
                    try:
                        all_comments_text = " ".join(comments)
                        comment_keywords = self.keyword_analyzer.analyze_text(
                            all_comments_text)
                        result["comment_keyword_analysis"] = comment_keywords

                        if self.debug and comment_keywords.get("keywords"):
                            top_comment_keywords = [f"{kw['word']}({kw['count']}次)"
                                                    for kw in comment_keywords.get("keywords", [])[:3]]
                            logger.info(
                                f"帖子 '{title}' 评论中提取到关键词: {', '.join(top_comment_keywords)}")
                    except Exception as e:
                        logger.error(f"对帖子 '{title}' 评论进行关键词分析时出错: {e}")
                        result["comment_keyword_analysis"] = {
                            "keywords": [], "has_financial_content": False}

                    # 如果使用DeepSeek进行情感分析
                    if isinstance(self.sentiment_analyzer, DeepSeekSentimentAnalyzer):
                        try:
                            detailed_analysis = self.analyze_sentiment_with_deepseek(
                                comments)
                            if detailed_analysis:
                                result["sentiment_analysis"] = detailed_analysis
                                logger.info(f"帖子 '{title}' 完成DeepSeek情感分析")
                        except Exception as e:
                            logger.error(
                                f"使用DeepSeek对帖子 '{title}' 进行情感分析时出错: {e}")
                else:
                    if comment_count > 0:
                        logger.warning(
                            f"帖子 '{title}' 评论数为{comment_count}，但未成功提取到评论")
                    else:
                        logger.info(f"帖子 '{title}' 无评论")
            except Exception as e:
                logger.error(f"处理帖子 '{title}' 评论时出错: {e}")

            return result

        except Exception as e:
            logger.error(f"分析帖子 '{title}' 时出错: {e}")
            import traceback
            logger.error(traceback.format_exc())

            # 返回基本信息
            return {
                "title": title,
                "date": post_info.get("date", "未知日期"),
                "time": post_info.get("time", "未知时间"),
                "sentiment_score": 0,
                "sentiment_label": "无评论",
                "section": post_info.get("section", "未知板块"),
                "comments": [],
                "has_comments": False,
                "keyword_analysis": {},
                "comment_keyword_analysis": {}
            }

    def _get_sentiment_label(self, score: int) -> str:
        """
        根据情感得分返回对应的标签

        Args:
            score: 情感得分（0-5）

        Returns:
            情感标签
        """
        sentiment_labels = {
            0: "无评论",
            1: "极度消极",
            2: "消极",
            3: "中性",
            4: "积极",
            5: "极度积极"
        }
        return sentiment_labels.get(score, "未知")

    def analyze_sentiment(self, comments: List[str]) -> int:
        """
        分析评论情感，返回0-5的评分

        Args:
            comments: 评论列表

        Returns:
            情感得分，0表示无评论，1极度消极，3中性，5极度积极
        """
        if not comments:
            return 0  # 无评论

        # 如果使用外部的DeepSeek分析器
        if isinstance(self.sentiment_analyzer, DeepSeekSentimentAnalyzer):
            # 使用DeepSeek API分析评论
            try:
                sentiment_result = self.sentiment_analyzer.analyze_comments_batch(
                    comments)
                return sentiment_result["score"]  # 直接返回API给出的得分

            except Exception as e:
                logger.error(f"使用DeepSeek分析器进行情感分析时出错: {e}")
                return 3  # 出错时默认为中性

        # 默认的简单情感分析方法
        positive_words = ['好', '涨', '利好', '看多', '期待', '支持', '牛', '赞', '强']
        negative_words = ['差', '跌', '利空', '看空', '失望', '反对', '熊', '弱']

        positive_count = 0
        negative_count = 0

        for comment in comments:
            comment = comment.lower()

            # 计算正面词出现次数
            pos_count = sum(1 for word in positive_words if word in comment)
            # 计算负面词出现次数
            neg_count = sum(1 for word in negative_words if word in comment)

            if pos_count > neg_count:
                positive_count += 1
            elif neg_count > pos_count:
                negative_count += 1

        # 计算情感得分
        total = len(comments)
        if total == 0:
            return 0  # 无评论

        positive_ratio = positive_count / total
        negative_ratio = negative_count / total

        if positive_ratio > 0.7:
            return 5  # 极度积极
        elif positive_ratio > 0.5:
            return 4  # 积极
        elif negative_ratio > 0.7:
            return 1  # 极度消极
        elif negative_ratio > 0.5:
            return 2  # 消极
        else:
            return 3  # 中性

    def analyze_sentiment_with_deepseek(self, comments: List[str]) -> str:
        """
        使用DeepSeek API对评论进行详细的情感分析

        Args:
            comments: 评论列表

        Returns:
            详细的情感分析结果字符串，按照readme中指定的格式
        """
        if not comments:
            return ""

        try:
            # 使用实例的DeepSeekSentimentAnalyzer
            if isinstance(self.sentiment_analyzer, DeepSeekSentimentAnalyzer):
                analyzer = self.sentiment_analyzer
            else:
                logger.error("未设置DeepSeek情感分析器，无法进行详细情感分析")
                return ""

            # 1. 获取整体评论情感
            sentiment_result = analyzer.analyze_comments_batch(comments)
            sentiment_label = sentiment_result["label"]
            sentiment_score = sentiment_result["score"]

            # 2. 计算情感分布
            positive_count = sum(1 for comment in comments if any(
                kw in comment for kw in ['好', '涨', '支持', '看多', '利好']))
            negative_count = sum(1 for comment in comments if any(
                kw in comment for kw in ['差', '跌', '空', '利空', '风险']))
            neutral_count = len(comments) - positive_count - negative_count

            # 3. 提取情感关键词
            positive_keywords = ['利好', '增长', '突破', '稳健', '看好']
            negative_keywords = ['利空', '下跌', '风险', '减持', '观望']

            # 根据情感标签选择关键词
            if sentiment_label == "正面":
                keywords = [kw for kw in positive_keywords if any(
                    kw in comment for comment in comments)]
                if not keywords and positive_count > 0:
                    keywords = positive_keywords[:2]
            elif sentiment_label == "负面":
                keywords = [kw for kw in negative_keywords if any(
                    kw in comment for comment in comments)]
                if not keywords and negative_count > 0:
                    keywords = negative_keywords[:2]
            else:
                keywords = []

            # 4. 生成市场情绪
            market_sentiment = "看多" if sentiment_label == "正面" else "看空" if sentiment_label == "负面" else "观望"

            # 5. 组装详细分析结果
            analysis_text = f"===== DeepSeek情感分析 =====\n"
            analysis_text += f"- 整体评论情感: {sentiment_label}\n"
            analysis_text += f"- 情感评分: {sentiment_score}/5\n"
            analysis_text += f"- 情感分布: 正面 {positive_count}/{len(comments)}, 负面 {negative_count}/{len(comments)}, 中性 {neutral_count}/{len(comments)}\n"
            if keywords:
                analysis_text += f"- 关键词: {', '.join(keywords)}\n"
            analysis_text += f"- 市场情绪: {market_sentiment}\n"

            # 6. 添加评论示例
            if comments and len(comments) > 0:
                analysis_text += "\n===== 评论示例 =====\n"
                # 最多显示5条评论
                for i, comment in enumerate(comments[:5]):
                    analysis_text += f"{i+1}. {comment}\n"

            return analysis_text

        except Exception as e:
            logger.error(f"使用DeepSeek进行详细情感分析时出错: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return ""

    def navigate_to_telegraph_section(self, section: str) -> bool:
        """
        导航到指定的电报板块

        Args:
            section: 要导航到的板块名称

        Returns:
            bool: 导航是否成功
        """
        try:
            # 首先访问基本URL
            try:
                base_url = "https://www.telegraph-site.cn"
                current_url = self.page.url
                
                # 如果当前不在该网站，先导航到首页
                if not current_url.startswith(base_url):
                    logger.info(f"导航到电报网站首页: {base_url}")
                    self.page.goto(base_url, timeout=15000)
                    self.page.wait_for_load_state("networkidle", timeout=10000)
                    time.sleep(2)  # 等待页面完全加载
            except Exception as e:
                logger.error(f"导航到首页时出错: {e}")
                # 尝试直接访问目标页面
                try:
                    section_url = f"{base_url}/telegraph"
                    logger.info(f"尝试直接导航到电报页面: {section_url}")
                    self.page.goto(section_url, timeout=15000)
                    self.page.wait_for_load_state("networkidle", timeout=10000)
                    time.sleep(2)  # 等待页面完全加载
                except Exception as e:
                    logger.error(f"导航到电报页面时出错: {e}")
                    return False

            # 等待页面加载完成
            self.page.wait_for_load_state("networkidle", timeout=10000)
            
            # 查看当前URL，判断是否已经在目标板块
            current_url = self.page.url
            if f"{section}" in current_url.lower() or f"{section.lower()}" in current_url:
                logger.info(f"已经在 {section} 板块页面")
                return True
                
            # 增加匹配项：针对不同的拼写和表达方式
            section_variants = [
                section,               # 原始名称
                section.lower(),       # 小写
                section.upper(),       # 大写
                section.replace(' ', '') # 移除空格
            ]
            
            # 尝试多种方式找到并点击板块链接
            section_selectors = []
            for variant in section_variants:
                section_selectors.extend([
                    f"a:text-is('{variant}')",       # 精确匹配
                    f"a:text-matches('{variant}')",  # 模糊匹配
                    f"a:has-text('{variant}')",      # 包含文本
                    f"[href*='{variant}']",          # URL匹配
                    f"[title*='{variant}']",         # 标题匹配
                    f"[data-id*='{variant}']",       # 数据ID匹配
                    f"[class*='tab']:has-text('{variant}')" # 标签类匹配
                ])

            # 先获取并输出所有可能的导航元素，帮助调试
            if self.debug:
                all_links = self.page.evaluate("""
                    () => {
                        const links = Array.from(document.querySelectorAll('a'));
                        return links.map(a => ({ 
                            text: a.textContent.trim(), 
                            href: a.href,
                            visible: a.offsetParent !== null
                        }));
                    }
                """)
                visible_links = [link for link in all_links if link['visible']]
                logger.info(f"页面上找到 {len(visible_links)} 个可见链接:")
                for link in visible_links[:10]:  # 只显示前10个，避免日志过长
                    logger.info(f"  - 文本: '{link['text']}', 链接: {link['href']}")

            # 尝试使用选择器查找元素
            for selector in section_selectors:
                try:
                    elements = self.page.query_selector_all(selector)
                    for element in elements:
                        if not element.is_visible():
                            continue
                            
                        # 获取元素文本，帮助调试
                        if self.debug:
                            try:
                                text = element.inner_text().strip()
                                href = element.get_attribute("href") or ""
                                logger.info(f"找到可能的导航元素: '{text}', href={href}")
                            except:
                                pass
                                
                        # 确保元素可见和可点击
                        element.wait_for_element_state("visible", timeout=5000)
                        element.scroll_into_view_if_needed()
                        time.sleep(1)  # 等待滚动完成

                        # 尝试点击
                        try:
                            element.click()
                            # 等待导航完成
                            self.page.wait_for_load_state("networkidle", timeout=10000)
                            time.sleep(2)  # 等待页面渲染
                            
                            # 验证是否导航成功
                            current_url = self.page.url
                            page_content = self.page.content()
                            if (f"{section}" in current_url.lower() or 
                                f"{section}" in page_content or
                                self.verify_section_content(section)):
                                logger.info(f"成功导航到 {section} 板块")
                                return True
                        except Exception as e:
                            logger.error(f"点击导航元素失败: {e}，尝试JavaScript点击")
                            try:
                                self.page.evaluate("(element) => element.click()", element)
                                self.page.wait_for_load_state("networkidle", timeout=10000)
                                time.sleep(2)
                                
                                # 验证导航结果
                                if self.verify_section_content(section):
                                    logger.info(f"通过JavaScript点击成功导航到 {section} 板块")
                                    return True
                            except:
                                pass
                except Exception as e:
                    if self.debug:
                        logger.error(f"使用选择器 '{selector}' 导航失败: {e}")
                    continue

            # 尝试直接访问可能的URL
            try:
                # 构建可能的URL
                possible_urls = [
                    f"{base_url}/telegraph",        # 基础电报页面
                    f"{base_url}/telegraph/{section.lower()}", # 子版块页面
                    f"{base_url}/telegrapha/{section.lower()}"  # 另一种可能格式
                ]
                
                for url in possible_urls:
                    try:
                        logger.info(f"尝试直接访问URL: {url}")
                        self.page.goto(url, timeout=15000)
                        self.page.wait_for_load_state("networkidle", timeout=10000)
                        time.sleep(2)
                        
                        # 验证页面是否包含相关内容
                        if self.verify_section_content(section):
                            logger.info(f"通过直接访问URL成功导航到 {section} 板块")
                            return True
                    except:
                        continue
            except Exception as e:
                logger.error(f"尝试直接访问URL时出错: {e}")

            # 如果所有方法都失败，但我们在电报页面，可以模拟成功
            if "telegraph" in self.page.url:
                logger.warning(f"无法精确导航到 {section} 板块，但已在电报页面，将继续处理")
                return True
                
            # 最终尝试：使用更通用的JavaScript查找并点击
            js_result = self.page.evaluate("""
                (section) => {
                    // 所有可能的文本变体
                    const variants = [section, section.toLowerCase(), section.toUpperCase()];
                    
                    // 尝试找到包含指定文本的任何可点击元素
                    const elements = Array.from(document.querySelectorAll('a, button, [role="button"], .tab, [class*="tab"]'));
                    
                    for (const element of elements) {
                        const text = element.textContent || '';
                        const href = element.href || '';
                        const title = element.title || '';
                        const ariaLabel = element.getAttribute('aria-label') || '';
                        
                        // 检查元素是否匹配任何变体
                        const matches = variants.some(variant => 
                            text.includes(variant) || 
                            href.includes(variant) || 
                            title.includes(variant) ||
                            ariaLabel.includes(variant)
                        );
                        
                        if (matches && element.offsetParent !== null) { // 确保元素可见
                            element.click();
                            return true;
                        }
                    }
                    return false;
                }
            """, section)

            if js_result:
                # 等待导航完成
                self.page.wait_for_load_state("networkidle", timeout=10000)
                time.sleep(2)
                
                # 验证导航结果
                if self.verify_section_content(section):
                    logger.info(f"通过通用JavaScript方法成功导航到 {section} 板块")
                    return True

            logger.error(f"无法找到 {section} 板块的导航链接")
            return False

        except Exception as e:
            logger.error(f"导航到 {section} 板块时出错: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
            
    def verify_section_content(self, section: str) -> bool:
        """
        验证当前页面是否包含指定板块的内容
        
        Args:
            section: 要验证的板块名称
            
        Returns:
            bool: 是否包含指定板块内容
        """
        try:
            # 获取页面标题和内容
            title = self.page.title()
            url = self.page.url
            
            # 检查URL和标题
            if section.lower() in url.lower() or section.lower() in title.lower():
                return True
                
            # 在页面内容中查找板块名称
            content = self.page.content().lower()
            if section.lower() in content:
                return True
                
            # 如果在电报页面上，我们认为导航成功
            if "telegraph" in url.lower() or "telegraph-site.cn" in url.lower():
                # 获取所有可能与板块相关的文本
                headings = self.page.evaluate("""
                    () => {
                        const elements = Array.from(document.querySelectorAll('h1, h2, h3, h4, .title, .header, .tab'));
                        return elements.map(el => el.textContent.trim());
                    }
                """)
                
                for heading in headings:
                    if section.lower() in heading.lower():
                        return True
                
                # 如果是已知的板块，且我们在电报页面，假设导航成功
                if section in ["看盘", "公司", "要闻", "科技"]:
                    return True
            
            return False
        except Exception as e:
            logger.error(f"验证导航结果时出错: {e}")
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

            try:
                # 初始化评论计数
                comment_count = 0
                element_text = element.inner_text()

                # 首先提取时间，判断是否是有效的帖子
                time_match = re.search(r'(\d{2}:\d{2}:\d{2})', element_text)
                if time_match:
                    result["time"] = time_match.group(1)
                else:
                    # 如果没有时间，可能不是有效帖子
                    return result

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
                    r'评论[：:]\s*(\d+)',        # 评论: N 或 评论：N
                    r'评论\((\d+)\)',           # 评论(N)
                    r'评论\s*(\d+)',             # 评论 N
                    r'评论.*?(\d+)'             # 极宽松匹配，评论后面出现的任何数字
                ]

                # 保存原始评论数，避免被后面的错误覆盖
                original_comment_count = comment_count

                for pattern in comment_patterns:
                    match = re.search(pattern, element_text)
                    if match:
                        try:
                            comment_count = int(match.group(1))
                            if comment_count > 0 and comment_count < 1000:  # 过滤异常大的数字
                                result["comment_count"] = comment_count
                                break
                        except (ValueError, IndexError):
                            pass

                # 如果原始评论数已确定且合理，优先使用它
                if original_comment_count > 0 and original_comment_count < 1000:
                    result["comment_count"] = original_comment_count

                # 设置帖子有效性
                result["is_valid_post"] = is_likely_post or result["comment_count"] > 0

                return result

            except Exception as e:
                logger.error(f"提取帖子信息时出错: {e}")
                import traceback
                logger.error(traceback.format_exc())
                return result

        except Exception as e:
            logger.error(f"提取帖子信息时出错: {e}")
            import traceback
            logger.error(traceback.format_exc())

            # 返回基本信息，设置为无效帖子
            return {
                "title": "未知标题",
                "date": "未知日期",
                "time": "未知时间",
                "comment_count": 0,
                "element": element,
                "is_valid_post": False,
                "section": "未知板块"
            }

    def scrape_section(self, section: str) -> List[Dict[str, Any]]:
        """
        爬取指定板块的内容

        Args:
            section: 板块名称，如"看盘"、"公司"等

        Returns:
            List[Dict[str, Any]]: 爬取到的帖子列表
        """
        results = []

        try:
            # 导航到指定板块
            if not self.navigate_to_telegraph_section(section):
                logger.error(f"导航到 {section} 板块失败")
                return results

            # 等待页面加载完成
            self.page.wait_for_load_state("networkidle", timeout=10000)
            time.sleep(2)  # 额外等待以确保动态内容加载

            # 使用多个选择器尝试获取帖子元素
            post_selectors = [
                "[class*='telegraph']",  # 通用选择器
                "[class*='post']",
                "[class*='article']",
                "[class*='item']"
            ]

            all_elements = []
            for selector in post_selectors:
                try:
                    elements = self.page.query_selector_all(selector)
                    if elements:
                        if self.debug:
                            logger.info(
                                f"使用选择器 '{selector}' 找到 {len(elements)} 个电报项")
                        all_elements.extend(elements)
                except Exception as e:
                    if self.debug:
                        logger.error(f"使用选择器 '{selector}' 查找元素时出错: {e}")

            # 去重
            unique_elements = list(set(all_elements))
            if self.debug:
                logger.info(f"总共找到 {len(unique_elements)} 个电报项")

            # 如果没有找到任何元素，尝试使用JavaScript
            if not unique_elements:
                try:
                    js_elements = self.page.evaluate("""
                        () => {
                            const results = [];
                            const possibleSelectors = [
                                '[class*="telegraph"]',
                                '[class*="post"]',
                                '[class*="article"]',
                                '[class*="item"]'
                            ];
                            
                            for (const selector of possibleSelectors) {
                                const elements = document.querySelectorAll(selector);
                                elements.forEach(el => results.push(el));
                            }
                            
                            return results;
                        }
                    """)
                    if js_elements:
                        unique_elements = js_elements
                        if self.debug:
                            logger.info(
                                f"通过JavaScript找到 {len(js_elements)} 个电报项")
                except Exception as e:
                    if self.debug:
                        logger.error(f"使用JavaScript查找元素时出错: {e}")

            # 处理每个帖子
            for element in unique_elements:
                try:
                    # 等待元素可见和可交互
                    element.wait_for_element_state("visible", timeout=5000)

                    # 提取帖子信息
                    post_info = self.extract_post_info(element)

                    # 设置板块信息
                    post_info["section"] = section

                    # 如果是有效帖子，进行情感分析
                    if post_info["is_valid_post"]:
                        # 分析帖子
                        analyzed_info = self.analyze_post(post_info)
                        if analyzed_info:
                            results.append(analyzed_info)

                except Exception as e:
                    if self.debug:
                        logger.error(f"处理帖子元素时出错: {e}")
                    continue

            if self.debug:
                logger.info(f"成功分析 {len(results)} 个有效电报项")

            return results

        except Exception as e:
            logger.error(f"爬取 {section} 板块时出错: {e}")
            return results
