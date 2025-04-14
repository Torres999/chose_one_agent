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

    def get_comments(self, post_info) -> List[str]:
        """
        获取特定帖子的评论，支持点击评论链接、获取详情页、处理分页
        
        Args:
            post_info: 包含帖子信息的字典
            
        Returns:
            评论内容列表
        """
        comments = []
        element = post_info.get("element")
        comment_count = post_info.get("comment_count", 0)
        
        if not element or comment_count <= 0:
            # 如果没有评论或者评论数为0，直接返回空列表
            logger.info("帖子评论数为0或没有关联元素，不获取评论")
            return comments
        
        try:
            # 尝试查找评论按钮或链接
            logger.info(f"尝试获取帖子 '{post_info.get('title', '未知标题')}' 的评论，评论数: {comment_count}")
            
            # 查找评论按钮或链接 - 使用多种选择器
            comment_selectors = [
                f"a:has-text('评论')",
                f"a:has-text('评论({comment_count})')",
                f"a:has-text('评论[{comment_count}]')",
                f"a:has-text('评论：{comment_count}')",
                f"div:has-text('评论') >> a",
                f"div:has-text('评论') >> span >> a",
                f".comment-link",
                f".comment-button",
                f"[class*='comment']",
                f"[class*='pinglun']"
            ]
            
            comment_button = None
            for selector in comment_selectors:
                try:
                    # 尝试在元素内部查找
                    buttons = element.query_selector_all(selector)
                    if buttons and len(buttons) > 0:
                        comment_button = buttons[0]
                        logger.info(f"在元素内找到评论按钮: {selector}")
                        break
                except Exception:
                    pass
            
            # 如果在元素内部没找到，尝试在页面上查找
            if not comment_button:
                page_content = post_info.get("title", "")
                # 尝试在页面上查找包含帖子标题或时间的附近元素
                try:
                    # 使用JavaScript查找可能的评论按钮
                    js_result = self.page.evaluate(f"""
                        () => {{
                            const title = "{post_info.get('title', '')}".replace(/"/g, '\\"');
                            const timeStr = "{post_info.get('time', '')}".replace(/"/g, '\\"');
                            
                            // 查找包含标题的元素
                            const elements = Array.from(document.querySelectorAll('*')).filter(el => 
                                el.innerText.includes(title) || el.innerText.includes(timeStr)
                            );
                            
                            for (const el of elements) {{
                                // 查找附近的评论按钮
                                const parent = el.parentElement;
                                if (!parent) continue;
                                
                                // 在父元素或祖先元素中寻找评论按钮
                                const commentLinks = Array.from(parent.querySelectorAll('a')).filter(a => 
                                    a.innerText.includes('评论') || 
                                    a.href.includes('comment') ||
                                    a.onclick?.toString().includes('comment')
                                );
                                
                                if (commentLinks.length > 0) {{
                                    // 返回评论按钮的属性，便于后续定位
                                    return {{
                                        found: true,
                                        id: commentLinks[0].id || '',
                                        className: commentLinks[0].className || '',
                                        text: commentLinks[0].innerText || '',
                                        href: commentLinks[0].href || '',
                                        rect: commentLinks[0].getBoundingClientRect()
                                    }};
                                }}
                            }}
                            
                            return {{ found: false }};
                        }}
                    """)
                    
                    if js_result.get("found"):
                        # 尝试基于JavaScript获取的信息定位评论按钮
                        if js_result.get("id"):
                            comment_button = self.page.query_selector(f"#{js_result['id']}")
                        elif js_result.get("className"):
                            comment_button = self.page.query_selector(f".{js_result['className']}")
                        elif js_result.get("href"):
                            comment_button = self.page.query_selector(f"a[href='{js_result['href']}']")
                        elif js_result.get("rect"):
                            # 使用坐标点击
                            logger.info("使用坐标定位评论按钮")
                            rect = js_result.get("rect")
                            # 计算元素中心点
                            x = rect.get("left", 0) + rect.get("width", 0) / 2
                            y = rect.get("top", 0) + rect.get("height", 0) / 2
                            self.page.mouse.click(x, y)
                            self.page.wait_for_timeout(2000)  # 等待页面响应
                            self.page.wait_for_load_state("networkidle", timeout=5000)
                            comment_button = True  # 标记为已点击
                except Exception as e:
                    logger.debug(f"JavaScript查找评论按钮失败: {e}")
            
            # 如果找到评论按钮，点击进入评论页面
            if comment_button and comment_button is not True:  # 不是已点击的标记
                try:
                    # 进入评论页面
                    comment_button.click()
                    self.page.wait_for_timeout(2000)  # 等待页面响应
                    self.page.wait_for_load_state("networkidle", timeout=5000)
                    logger.info("已点击评论按钮，等待页面加载")
                except Exception as e:
                    logger.error(f"点击评论按钮失败: {e}")
                    return comments
            
            # 如果没有找到评论按钮，尝试根据URL规则构造可能的评论页面URL
            if not comment_button:
                logger.info("未找到评论按钮，尝试构造评论页面URL")
                # 尝试从当前页面URL构造可能的评论页面URL
                current_url = self.page.url
                
                # 提取可能的帖子ID
                post_id_match = re.search(r'/(\d+)/?$', current_url)
                if post_id_match:
                    post_id = post_id_match.group(1)
                    # 构造可能的评论URL
                    comment_url = f"{self.base_url}/detail/{post_id}"
                    try:
                        self.page.goto(comment_url)
                        self.page.wait_for_load_state("networkidle", timeout=5000)
                        logger.info(f"导航到可能的评论页面: {comment_url}")
                    except Exception as e:
                        logger.error(f"导航到评论页面失败: {e}")
                        return comments
                else:
                    logger.warning("无法从URL提取帖子ID，无法构造评论页面URL")
                    # 如果URL分析失败，直接尝试detail URL
                    if "/telegraph" in current_url:
                        # 尝试直接点击帖子
                        try:
                            post_element = self.page.query_selector(f"div:has-text('{post_info.get('title', '')}')")
                            if post_element:
                                post_element.click()
                                self.page.wait_for_load_state("networkidle", timeout=5000)
                                logger.info("已点击帖子进入详情页")
                        except Exception as e:
                            logger.debug(f"点击帖子进入详情页失败: {e}")
                            return comments
            
            # 等待评论区域加载
            logger.info("等待评论区域加载")
            self.page.wait_for_timeout(2000)
            
            # 提取评论
            # 尝试多个可能的评论选择器
            comment_area_selectors = [
                ".comment-list", 
                ".comments-list", 
                ".comment-area",
                "[class*='comment']",
                "[class*='pinglun']",
                "#comments",
                ".comments"
            ]
            
            comment_items_selectors = [
                ".comment-item",
                ".comment",
                ".comment-content",
                "[class*='comment-item']",
                "[class*='comment-li']",
                ".reply-item"
            ]
            
            # 查找评论区域
            comment_area = None
            for selector in comment_area_selectors:
                try:
                    areas = self.page.query_selector_all(selector)
                    if areas and len(areas) > 0:
                        comment_area = areas[0]
                        logger.info(f"找到评论区域: {selector}")
                        break
                except Exception:
                    pass
            
            if not comment_area:
                # 如果没有找到特定的评论区域，尝试使用更通用的选择器查找评论项
                all_comments = []
                for selector in comment_items_selectors:
                    try:
                        items = self.page.query_selector_all(selector)
                        if items and len(items) > 0:
                            logger.info(f"使用选择器 '{selector}' 找到 {len(items)} 个评论项")
                            all_comments.extend(items)
                    except Exception:
                        pass
                
                # 提取评论文本
                for item in all_comments:
                    try:
                        comment_text = item.inner_text()
                        if comment_text and len(comment_text.strip()) > 0:
                            comments.append(comment_text.strip())
                    except Exception:
                        continue
            else:
                # 如果找到评论区域，从中提取评论项
                for selector in comment_items_selectors:
                    try:
                        items = comment_area.query_selector_all(selector)
                        if items and len(items) > 0:
                            logger.info(f"在评论区域中使用选择器 '{selector}' 找到 {len(items)} 个评论项")
                            for item in items:
                                try:
                                    comment_text = item.inner_text()
                                    if comment_text and len(comment_text.strip()) > 0:
                                        comments.append(comment_text.strip())
                                except Exception:
                                    continue
                            break
                    except Exception:
                        continue
            
            # 如果上述方法都未找到评论，尝试使用JavaScript提取
            if not comments:
                logger.info("尝试使用JavaScript提取评论")
                try:
                    js_comments = self.page.evaluate("""
                        () => {
                            // 查找所有可能的评论文本
                            const commentTexts = [];
                            
                            // 查找包含用户名、时间和内容的组合，这通常是评论的特征
                            const allElements = document.querySelectorAll('*');
                            for (const el of allElements) {
                                const text = el.innerText || '';
                                // 检查元素是否包含评论特征
                                if (
                                    // 包含用户名和时间的特征
                                    (text.match(/\\d+分钟前|\\d+小时前|\\d+天前/) || 
                                     text.match(/\\d{2}:\\d{2}/) ||
                                     text.match(/\\d{4}-\\d{2}-\\d{2}/)) &&
                                    // 并且文本长度合适(不太短也不太长)
                                    text.length > 5 && text.length < 500 &&
                                    // 包含常见的评论内容指示词
                                    (text.includes('回复') || text.includes('评论') || text.includes('说'))
                                ) {
                                    commentTexts.push(text);
                                }
                            }
                            
                            return commentTexts;
                        }
                    """)
                    
                    if js_comments and len(js_comments) > 0:
                        logger.info(f"通过JavaScript找到 {len(js_comments)} 条可能的评论")
                        comments.extend(js_comments)
                except Exception as e:
                    logger.error(f"JavaScript提取评论失败: {e}")
            
            logger.info(f"共获取到{len(comments)}条评论")
            
            # 处理分页 - 类似于加载更多电报的逻辑
            max_pages = 3  # 最多加载3页评论
            current_page = 1
            
            while current_page < max_pages:
                # 检查是否有"下一页"按钮
                next_page_selectors = [
                    "a:has-text('下一页')", 
                    ".next-page", 
                    "[class*='next']",
                    "a[class*='next']",
                    "button:has-text('下一页')",
                    ".pagination >> a:right-of(:text('当前'))",
                    ".page-next"
                ]
                
                next_button = None
                for selector in next_page_selectors:
                    try:
                        buttons = self.page.query_selector_all(selector)
                        if buttons and len(buttons) > 0:
                            next_button = buttons[0]
                            break
                    except Exception:
                        pass
                
                if not next_button:
                    # 如果没有下一页按钮，检查是否有加载更多按钮
                    load_more_selectors = [
                        "a:has-text('加载更多')",
                        "button:has-text('加载更多')",
                        ".load-more",
                        "[class*='load-more']"
                    ]
                    
                    for selector in load_more_selectors:
                        try:
                            buttons = self.page.query_selector_all(selector)
                            if buttons and len(buttons) > 0:
                                next_button = buttons[0]
                                break
                        except Exception:
                            pass
                
                if next_button:
                    try:
                        # 点击下一页/加载更多
                        logger.info("点击下一页/加载更多按钮")
                        next_button.click()
                        self.page.wait_for_timeout(2000)  # 等待页面响应
                        self.page.wait_for_load_state("networkidle", timeout=5000)
                        
                        # 提取新加载的评论
                        new_comments = []
                        if comment_area:
                            # 如果之前找到了评论区域，继续在其中查找新评论
                            for selector in comment_items_selectors:
                                try:
                                    items = comment_area.query_selector_all(selector)
                                    if items and len(items) > len(comments):  # 有新评论加载
                                        logger.info(f"在评论区域中找到 {len(items)} 个评论项，之前有 {len(comments)} 条")
                                        # 只处理新加载的评论
                                        for i in range(len(comments), len(items)):
                                            try:
                                                comment_text = items[i].inner_text()
                                                if comment_text and len(comment_text.strip()) > 0:
                                                    new_comments.append(comment_text.strip())
                                            except Exception:
                                                continue
                                        break
                                except Exception:
                                    continue
                        else:
                            # 如果没有找到特定的评论区域，使用之前的方法查找所有评论
                            old_count = len(comments)
                            all_comments = []
                            for selector in comment_items_selectors:
                                try:
                                    items = self.page.query_selector_all(selector)
                                    if items and len(items) > 0:
                                        all_comments.extend(items)
                                except Exception:
                                    pass
                            
                            # 提取新评论文本
                            for i in range(old_count, len(all_comments)):
                                try:
                                    comment_text = all_comments[i].inner_text()
                                    if comment_text and len(comment_text.strip()) > 0:
                                        new_comments.append(comment_text.strip())
                                except Exception:
                                    continue
                        
                        # 如果找到新评论，添加到结果中
                        if new_comments:
                            logger.info(f"加载了 {len(new_comments)} 条新评论")
                            comments.extend(new_comments)
                        else:
                            # 如果没有新评论，可能已经到底了
                            logger.info("没有加载到新评论，停止翻页")
                            break
                        
                        current_page += 1
                    except Exception as e:
                        logger.error(f"加载更多评论失败: {e}")
                        break
                else:
                    # 没有找到翻页按钮，结束翻页
                    logger.info("未找到翻页按钮，评论已全部加载")
                    break
            
            # 返回到原电报列表页面
            try:
                logger.info("返回到电报列表页面")
                # 优先使用浏览器的后退功能
                self.page.go_back()
                self.page.wait_for_load_state("networkidle", timeout=5000)
            except Exception as e:
                logger.error(f"返回电报列表页面失败: {e}")
                # 如果后退失败，尝试直接导航到电报页面
                try:
                    telegraph_url = f"{self.base_url}/telegraph"
                    self.page.goto(telegraph_url)
                    self.page.wait_for_load_state("networkidle", timeout=5000)
                except Exception as e:
                    logger.error(f"导航到电报页面失败: {e}")
            
            return comments
            
        except Exception as e:
            logger.error(f"获取评论时出错: {e}")
            import traceback
            logger.error(traceback.format_exc())
            
            # 确保返回到电报列表页面
            try:
                telegraph_url = f"{self.base_url}/telegraph"
                self.page.goto(telegraph_url)
                self.page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:
                pass
                
            return comments

    def analyze_post(self, post_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        分析单个帖子，提取信息并进行情感分析
        
        Args:
            post_info: 包含帖子信息的字典
            
        Returns:
            带有分析结果的帖子信息
        """
        try:
            # 继承原始信息
            result = post_info.copy()
            
            # 获取标题
            title = post_info.get("title", "未知标题")
            
            # 如果标题包含公司名称和公告类型，可能是公司板块
            if "公司" in title or "集团" in title or "股份" in title:
                result["section"] = "公司"
            # 如果标题包含指数、涨停等市场行情相关词，可能是看盘板块
            elif "指数" in title or "涨停" in title or "行情" in title or "市场" in title:
                result["section"] = "看盘"
            
            # 默认设置中性情感
            result["sentiment"] = 3  # 中性
            
            # 进一步处理评论(如果评论数大于0)
            comment_count = post_info.get("comment_count", 0)
            if comment_count > 0:
                logger.info(f"帖子 '{title}' 评论数为{comment_count}，获取评论并进行情感分析")
                # 获取评论
                comments = self.get_comments(post_info)
                
                if comments:
                    # 进行情感分析
                    sentiment = self.analyze_sentiment(comments)
                    logger.info(f"评论情感分析结果: {sentiment}")
                    
                    # 更新帖子的情感得分
                    result["sentiment"] = sentiment
                    
                    # 添加情感描述
                    sentiment_descriptions = {
                        0: "无评论",
                        1: "极度消极",
                        2: "消极",
                        3: "中性",
                        4: "积极",
                        5: "极度积极"
                    }
                    result["sentiment_description"] = sentiment_descriptions.get(sentiment, "中性")
                    logger.info(f"帖子 '{title}' 的评论情感评估为: {result['sentiment_description']}")
                else:
                    logger.warning(f"帖子声称有{comment_count}条评论，但实际获取不到评论内容")
            else:
                logger.info(f"帖子 '{title}' 评论数为0或没有关联元素，记录标题内容")
            
            return result
            
        except Exception as e:
            logger.error(f"分析帖子时出错: {e}")
            return post_info  # 返回原始信息

    def analyze_sentiment(self, comments: List[str]) -> int:
        """
        分析评论的情感，返回0-5的评分
        
        Args:
            comments: 评论内容列表
            
        Returns:
            情感评分: 0(无评论), 1(最消极)-5(最积极)
        """
        if not comments or len(comments) == 0:
            return 0  # 无评论
        
        # 积极情绪词汇
        positive_words = [
            '好', '棒', '强', '涨', '赚', '利好', '牛', '看多', '买', '利润', '增长', '上涨',
            '红', '高', '优秀', '漂亮', '突破', '飙升', '暴涨', '爆发', '机会', '支持',
            '看好', '向上', '强势', '加仓', '抄底', '稳健', '提升', '增持'
        ]
        
        # 消极情绪词汇
        negative_words = [
            '差', '跌', '亏', '熊', '空', '跳水', '下跌', '利空', '割', '割肉', '低',
            '绿', '卖', '跑', '崩', '暴跌', '亏损', '减持', '套', '被套', '破位',
            '风险', '见顶', '出货', '反对', '弱势', '踩踏', '跳水', '面包'
        ]
        
        # 中性词汇（对情感判断影响不大）
        neutral_words = [
            '持有', '观望', '等待', '看看', '关注', '不确定', '震荡', '横盘', 
            '盘整', '调整', '不好说', '看', '要看', '再看', '分析'
        ]
        
        # 情感计数
        positive_count = 0
        negative_count = 0
        neutral_count = 0
        total_words = 0
        
        # 分析每条评论
        for comment in comments:
            # 过滤掉非文本内容（如用户名、时间等），只保留主要文本
            # 移除用户名、时间标记等常见非文本内容
            cleaned_comment = re.sub(r'\d+分钟前|\d+小时前|\d+天前|\d{2}:\d{2}|回复', '', comment)
            
            # 分词分析（简单按字符切分，实际项目可考虑使用专业NLP库）
            total_words += len(cleaned_comment)
            
            # 统计积极消极词汇
            pos_matches = sum(1 for word in positive_words if word in cleaned_comment)
            neg_matches = sum(1 for word in negative_words if word in cleaned_comment)
            neu_matches = sum(1 for word in neutral_words if word in cleaned_comment)
            
            positive_count += pos_matches
            negative_count += neg_matches
            neutral_count += neu_matches
            
            # 考虑一些情感强化表达
            if '！' in cleaned_comment or '!' in cleaned_comment:
                if pos_matches > neg_matches:
                    positive_count += 1
                elif neg_matches > pos_matches:
                    negative_count += 1
        
        # 计算情感得分
        # 如果有明显情感偏向
        if positive_count > negative_count + neutral_count:
            # 积极情感，评分4-5
            ratio = positive_count / (positive_count + negative_count + neutral_count + 0.1)
            if ratio > 0.7:
                return 5  # 非常积极
            else:
                return 4  # 积极
        elif negative_count > positive_count + neutral_count:
            # 消极情感，评分1-2
            ratio = negative_count / (positive_count + negative_count + neutral_count + 0.1)
            if ratio > 0.7:
                return 1  # 非常消极
            else:
                return 2  # 消极
        else:
            # 中性或轻微偏向，评分3
            return 3  # 中性

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