# -*- coding: utf-8 -*-
import logging
import time
import datetime
import os
from typing import List, Dict, Any, Tuple
import re
import random
import json  # 添加导入

from chose_one_agent.scrapers.base_scraper import BaseScraper
from chose_one_agent.utils.helpers import parse_datetime, is_before_cutoff, extract_date_time, is_in_date_range
from chose_one_agent.analyzers.sentiment_analyzer import SentimentAnalyzer
from chose_one_agent.analyzers.deepseek_sentiment_analyzer import DeepSeekSentimentAnalyzer

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
            self.sentiment_analyzer = DeepSeekSentimentAnalyzer(api_key=deepseek_api_key)
        else:
            logger.info("使用SnowNLP进行情感分析")
            self.sentiment_analyzer = SentimentAnalyzer()
            
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
            # 先保存当前URL，用于识别当前电报的上下文
            current_url = self.page.url
            current_title = None
            
            # 对cls.cn/telegraph网站进行DOM结构分析
            if "cls.cn/telegraph" in current_url:
                logger.info("================ 开始分析cls.cn/telegraph网站 ================")
                # 获取并保存页面结构
                structure_info = self.debug_page_structure()
                if structure_info:
                    logger.info(f"页面结构分析完成: 找到 {structure_info['element_count']} 个包含'评论'的元素")
                else:
                    logger.warning("页面结构分析失败")
            
            # 尝试获取当前帖子的标题，用于关联评论
            try:
                current_title = post_element.inner_text().strip().split("\n")[0]
                if current_title and len(current_title) > 20:  # 标题可能太长，截断一部分
                    current_title = current_title[:20]
                logger.info(f"当前帖子标题: {current_title}")
            except Exception:
                pass
            
            # 检查是否有评论计数 - 增强版
            comment_count = 0
            try:
                # 1. 先获取并记录完整的元素文本，便于调试
                element_text = post_element.inner_text()
                logger.debug(f"帖子完整文本: {element_text}")
                
                # 2. 添加更强的正则表达式匹配模式
                comment_count_patterns = [
                    r'评论.*?[（(](\d+)[)）]',  # 更宽松的匹配，包括中英文括号和中间可能的空格或其他字符
                    r'评论\s*[(\[](\d+)[)\]]',  # 评论(N) 或 评论[N]
                    r'评论[：:]\s*(\d+)',      # 评论: N 或 评论：N
                    r'评论\((\d+)\)',         # 评论(N)
                    r'评论\s*(\d+)',          # 评论 N
                    r'评论.*?(\d+)'           # 极宽松匹配，评论后面出现的任何数字
                ]
                
                # 3. 尝试所有模式并记录匹配情况
                for i, pattern in enumerate(comment_count_patterns):
                    comment_count_match = re.search(pattern, element_text)
                    if comment_count_match:
                        try:
                            found_count = int(comment_count_match.group(1))
                            logger.info(f"使用模式[{i+1}]从帖子文本中提取到评论计数: {found_count}")
                            comment_count = found_count
                            break
                        except (ValueError, IndexError) as e:
                            logger.debug(f"模式[{i+1}]匹配到内容，但无法转换为数字: {e}")
                
                # 4. 如果以上模式都没有匹配成功，尝试直接搜索评论相关元素
                if comment_count == 0:
                    logger.info("未通过正则表达式找到评论计数，尝试通过元素查找")
                    try:
                        # 尝试查找评论数元素
                        count_selectors = [
                            "span.evaluate-count", 
                            "[class*='comment-count']", 
                            "[class*='evaluate-count']",
                            "span:has-text('评论')", 
                            "div:has-text('评论')"
                        ]
                        
                        for selector in count_selectors:
                            count_elements = post_element.query_selector_all(selector)
                            for j, element in enumerate(count_elements):
                                element_text = element.inner_text().strip()
                                logger.info(f"找到可能的评论计数元素[{j+1}]: '{element_text}'")
                                
                                # 尝试从元素文本中提取数字
                                for pattern in comment_count_patterns:
                                    matches = re.search(pattern, element_text)
                                    if matches:
                                        try:
                                            extracted_count = int(matches.group(1))
                                            logger.info(f"从评论元素中提取到评论计数: {extracted_count}")
                                            comment_count = extracted_count
                                            break
                                        except (ValueError, IndexError):
                                            pass
                                
                                if comment_count > 0:
                                    break
                            
                            if comment_count > 0:
                                break
                    except Exception as e:
                        logger.debug(f"通过元素查找评论计数时出错: {e}")
                
                # 如果找到非零评论计数，记录日志
                if comment_count > 0:
                    logger.info(f"帖子最终评论计数: {comment_count}")
                else:
                    # 尝试从页面全局内容中查找与当前帖子关联的评论计数
                    try:
                        # 搜索页面上所有文本节点
                        page_text = self.page.evaluate("() => document.body.innerText")
                        title_fragment = current_title[:10] if current_title and len(current_title) > 10 else current_title
                        
                        if title_fragment:
                            logger.info(f"尝试在页面文本中查找标题片段 '{title_fragment}' 附近的评论计数")
                            # 在页面文本中寻找标题片段附近的评论计数
                            title_pos = page_text.find(title_fragment)
                            if title_pos >= 0:
                                nearby_text = page_text[max(0, title_pos-100):min(len(page_text), title_pos+300)]
                                logger.debug(f"标题附近文本: {nearby_text}")
                                
                                for pattern in comment_count_patterns:
                                    matches = re.search(pattern, nearby_text)
                                    if matches:
                                        try:
                                            extracted_count = int(matches.group(1))
                                            logger.info(f"从页面文本中提取到评论计数: {extracted_count}")
                                            comment_count = extracted_count
                                            break
                                        except (ValueError, IndexError):
                                            pass
                    except Exception as e:
                        logger.debug(f"搜索页面文本中的评论计数时出错: {e}")
            except Exception as e:
                logger.debug(f"提取评论计数过程中出错: {e}")
                
            # 如果评论计数确实为0，提前返回
            if comment_count <= 0:
                logger.info("评论计数为0或无法获取，跳过处理")
                return []
            else:
                logger.info(f"确认帖子有{comment_count}条评论，继续处理")
            
            # 特殊处理CLS电报站点评论
            if "cls.cn/telegraph" in self.page.url:
                logger.info("检测到cls.cn/telegraph网站，使用特定方法获取评论")
                # 再次确认评论计数，避免处理零评论电报
                if comment_count <= 0:
                    logger.info("cls.cn网站评论数为0，跳过处理")
                    return []
                
                try:
                    # 增强识别当前页面是否直接包含评论
                    try:
                        # 搜索页面上所有文本节点，查找明确的评论内容
                        page_text = self.page.evaluate("() => document.body.innerText")
                        # 尝试使用更宽松的模式匹配评论计数
                        all_comment_counts = re.findall(r'评论.*?[（(](\d+)[)）]', page_text)
                        for count in all_comment_counts:
                            try:
                                count_value = int(count)
                                if count_value > 0:
                                    logger.info(f"在页面文本中找到评论计数: {count}")
                                    comment_count = max(comment_count, count_value)
                            except ValueError:
                                pass
                    except Exception as e:
                        logger.debug(f"检查页面文本中的评论计数失败: {e}")
                        
                    # 如果确认评论计数为0，直接返回
                    if comment_count <= 0:
                        logger.info("确认评论计数为0，跳过处理")
                        return []
                        
                    # 在cls.cn网站，尝试特定的评论元素查找策略
                    try:
                        # 增强评论元素选择器 - 更全面的选择器
                        comment_selectors = [
                            "span.evaluate-count", 
                            "span:has-text('评论')", 
                            "div:has-text('评论')",
                            ".comment-count",
                            "[class*='comment']",
                            "[class*='evaluate']",
                            "span:has-text(/评论.*?[0-9]+/)"
                        ]
                        
                        comment_elements = []
                        # 尝试每个选择器
                        for selector in comment_selectors:
                            try:
                                elements = self.page.query_selector_all(selector)
                                if elements and len(elements) > 0:
                                    logger.info(f"使用选择器 '{selector}' 找到 {len(elements)} 个可能的评论元素")
                                    comment_elements.extend(elements)
                            except Exception as e:
                                logger.debug(f"使用选择器 '{selector}' 查找元素时出错: {e}")
                        
                        # 去重，避免重复元素
                        unique_elements = []
                        seen_texts = set()
                        
                        for element in comment_elements:
                            try:
                                element_text = element.inner_text().strip()
                                if element_text and element_text not in seen_texts:
                                    unique_elements.append(element)
                                    seen_texts.add(element_text)
                            except Exception:
                                pass
                        
                        logger.info(f"去重后找到 {len(unique_elements)} 个可能的评论元素")
                        comment_elements = unique_elements
                                                    
                        # 对每个找到的评论元素进行分析
                        for i, element in enumerate(comment_elements):
                            try:
                                # 获取元素文本看是否包含评论计数
                                element_text = element.inner_text().strip()
                                logger.info(f"分析可能的评论元素 [{i+1}/{len(comment_elements)}]: {element_text}")
                                
                                # 检查元素文本是否表明评论为0
                                if re.search(r'评论.*?[（(]0[)）]', element_text) or "暂无评论" in element_text:
                                    logger.info(f"元素 [{i+1}] 文本表明评论为0，跳过: {element_text}")
                                    continue
                                    
                                # 获取元素的计算样式，帮助判断其可见性
                                try:
                                    is_visible = self.page.evaluate("""
                                        (element) => {
                                            const style = window.getComputedStyle(element);
                                            return style.display !== 'none' && 
                                                   style.visibility !== 'hidden' && 
                                                   style.opacity !== '0';
                                        }
                                    """, element)
                                        
                                    if not is_visible:
                                        logger.info(f"元素 [{i+1}] 不可见，跳过")
                                        continue
                                except Exception:
                                    # 忽略样式检查错误，继续处理
                                    pass
                    
                                # 分析元素点击交互
                                logger.info(f"对元素 [{i+1}] 进行点击交互分析...")
                                
                                # 记录元素位置和外观，便于调试
                                try:
                                    bbox = element.bounding_box()
                                    if bbox:
                                        logger.debug(f"元素位置: x={bbox['x']}, y={bbox['y']}, " +
                                                   f"width={bbox['width']}, height={bbox['height']}")
                                except Exception:
                                    pass
                                        
                                interaction_result = self.analyze_comment_interaction(element)
                                
                                if interaction_result:
                                    logger.info(f"交互分析完成: 点击后新增了 {interaction_result['new_elements_count']} 个元素")
                                    logger.info(f"发现 {interaction_result['possible_comments_count']} 条可能的评论内容")
                                    
                                    # 如果找到了可能的评论，记录并返回原页面
                                    if interaction_result['possible_comments_count'] > 0:
                                        # 读取可能的评论
                                        with open(interaction_result['comments'], "r", encoding="utf-8") as f:
                                            comment_data = json.load(f)
                                            for comment in comment_data:
                                                comments.append(comment['text'])
                                        
                                        logger.info(f"成功提取 {len(comments)} 条评论")
                                        # 使用浏览器的后退功能返回原页面
                                        self.page.go_back()
                                        self.page.wait_for_load_state("networkidle", timeout=5000)
                                        break
                                else:
                                    logger.warning(f"元素 [{i+1}] 交互分析失败")
                            except Exception as e:
                                logger.error(f"分析评论元素 [{i+1}] 时出错: {e}")
                                continue
                                
                        # 如果通过点击评论元素找到了评论，返回结果
                        if comments:
                            logger.info(f"通过评论元素交互找到 {len(comments)} 条评论，返回结果")
                            return comments
                    except Exception as e:
                        logger.error(f"查找特定评论元素失败: {e}")
                except Exception as e:
                    logger.error(f"处理cls.cn评论时出错: {e}")
            
            # 继续原有的评论提取逻辑...
            # ... 其他现有代码 ...
            
        except Exception as e:
            logger.error(f"获取评论时出错: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []

    def analyze_post(self, post_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        分析帖子内容，提取关键信息，进行情感分析

        Args:
            post_info: 包含帖子信息的字典

        Returns:
            包含分析结果的字典
        """
        try:
            # 初始化结果
            result = {
                "title": post_info.get("title", "未知标题"),
                "date": post_info.get("date", "未知日期"),
                "time": post_info.get("time", "未知时间"),
                "sentiment_score": 0,  # 默认为无评论
                "sentiment_label": "无评论",
                "section": post_info.get("section", "未知板块"),
                "comments": [],  # 存储评论内容
                "sentiment_analysis": "",  # 存储DeepSeek的详细分析结果
                "has_comments": False
            }
            
            # 获取评论计数
            comment_count = post_info.get("comment_count", 0)
            title = post_info.get("title", "未知标题")
            
            # 如果有评论计数或者元素，尝试获取评论
            if comment_count > 0 or "element" in post_info:
                logger.info(f"帖子 '{title}' 评论数为{comment_count}，获取评论并进行情感分析")
                # 获取评论
                comments = self.get_comments(post_info.get("element"))

                if comments and len(comments) > 0:
                    result["comments"] = comments
                    result["has_comments"] = True
                    logger.info(f"帖子 '{title}' 成功获取到 {len(comments)} 条评论")
                    
                    # 进行情感分析
                    sentiment_score = self.analyze_sentiment(comments)
                    result["sentiment_score"] = sentiment_score
                    
                    # 根据分数设置情感标签
                    if sentiment_score == 0:
                        result["sentiment_label"] = "无评论"
                    elif sentiment_score == 1:
                        result["sentiment_label"] = "极度消极"
                    elif sentiment_score == 2:
                        result["sentiment_label"] = "消极"
                    elif sentiment_score == 3:
                        result["sentiment_label"] = "中性"
                    elif sentiment_score == 4:
                        result["sentiment_label"] = "积极"
                    elif sentiment_score == 5:
                        result["sentiment_label"] = "极度积极"
                    
                    # 如果使用DeepSeek进行情感分析，额外保存详细分析结果
                    if isinstance(self.sentiment_analyzer, DeepSeekSentimentAnalyzer):
                        # 检查是否有详细分析结果
                        detailed_analysis = self.analyze_sentiment_with_deepseek(comments)
                        if detailed_analysis:
                            result["sentiment_analysis"] = detailed_analysis
                else:
                    # 未找到评论，设置为无评论
                    result["sentiment_score"] = 0
                    result["sentiment_label"] = "无评论"
                    logger.info(f"帖子 '{title}' 未找到评论，设置为无评论")
            else:
                # 帖子没有评论计数或元素，设置为无评论
                result["sentiment_score"] = 0
                result["sentiment_label"] = "无评论"
                logger.info(f"帖子 '{title}' 评论数为0或没有关联元素，设置为无评论")
            
            return result
        
        except Exception as e:
            logger.error(f"分析帖子时出错: {e}")
            import traceback
            logger.error(traceback.format_exc())
            
            # 返回基本信息，设置为无评论
            return {
                "title": post_info.get("title", "未知标题"),
                "date": post_info.get("date", "未知日期"),
                "time": post_info.get("time", "未知时间"),
                "sentiment_score": 0,
                "sentiment_label": "无评论",
                "section": post_info.get("section", "未知板块"),
                "comments": [],
                "has_comments": False
            }

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
                sentiment_label = self.sentiment_analyzer.analyze_comments_batch(comments)
                sentiment_score = 0
                
                # 将DeepSeek返回的情感标签转换为0-5的评分
                if sentiment_label == "正面":
                    sentiment_score = 4  # 积极
                elif sentiment_label == "负面":
                    sentiment_score = 2  # 消极
                else:  # 中性
                    sentiment_score = 3
                
                return sentiment_score
                
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
            sentiment_label = analyzer.analyze_comments_batch(comments)
            
            # 2. 计算情感分布
            positive_count = sum(1 for comment in comments if any(kw in comment for kw in ['好', '涨', '支持', '看多', '利好']))
            negative_count = sum(1 for comment in comments if any(kw in comment for kw in ['差', '跌', '空', '利空', '风险']))
            neutral_count = len(comments) - positive_count - negative_count
            
            # 3. 提取情感关键词
            positive_keywords = ['利好', '增长', '突破', '稳健', '看好']
            negative_keywords = ['利空', '下跌', '风险', '减持', '观望']
            
            # 根据情感标签选择关键词
            if sentiment_label == "正面":
                keywords = [kw for kw in positive_keywords if any(kw in comment for comment in comments)]
                if not keywords and positive_count > 0:
                    keywords = positive_keywords[:2]
            elif sentiment_label == "负面":
                keywords = [kw for kw in negative_keywords if any(kw in comment for comment in comments)]
                if not keywords and negative_count > 0:
                    keywords = negative_keywords[:2]
            else:
                keywords = []
                
            # 4. 生成市场情绪
            market_sentiment = "看多" if sentiment_label == "正面" else "看空" if sentiment_label == "负面" else "观望"
            
            # 5. 组装详细分析结果
            analysis_text = f"===== DeepSeek情感分析 =====\n"
            analysis_text += f"- 整体评论情感: {sentiment_label}\n"
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
        # 使用更可靠的标识符跟踪已处理的帖子
        processed_identifiers = set()
        post_extractor = PostExtractor()
        
        # 用于跟踪不符合日期条件的帖子数量
        outdated_posts_count = 0
        # 连续出现不符合条件的帖子的最大次数，超过此值则停止加载
        max_outdated_posts = 5
        
        # 添加最大处理数限制，防止无限循环
        max_posts_to_process = 100
        processed_count = 0
        
        try:
            # 获取第一页数据
            posts, _ = post_extractor.extract_posts_from_page(self.page)
            
            # 如果第一页没有数据，直接返回
            if not posts:
                return section_results
                
            # 处理第一页数据
            for post in posts:
                # 检查是否达到最大处理数量
                processed_count += 1
                if processed_count > max_posts_to_process:
                    logger.warning(f"已处理{max_posts_to_process}个电报，为防止无限处理强制退出")
                    break
                    
                # 添加板块信息
                post["section"] = section_name
                
                # 创建更精确的电报标识符
                post_identifier = f"{post.get('title', '')}_{post.get('date', '')}_{post.get('time', '')}"
                
                # 跳过重复帖子
                if post["title"] in processed_titles or post_identifier in processed_identifiers:
                    logger.info(f"电报已处理过，跳过: {post['title']}")
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
                processed_identifiers.add(post_identifier)
                result = self.analyze_post(post)
                
                # 确保板块信息被保留
                if "section" not in result or not result["section"] or result["section"] == "未知板块":
                    result["section"] = section_name
                
                section_results.append(result)
                logger.info(f"成功处理电报: {post['title']}")
            
            # 如果第一页已经有多个帖子不符合日期条件，可能不需要加载更多
            if outdated_posts_count >= max_outdated_posts:
                logger.info(f"第一页已发现{outdated_posts_count}个不符合日期条件的帖子，不再加载更多内容")
                return section_results
            
            # 尝试加载更多内容
            load_attempts = 0
            max_attempts = 3
            
            while load_attempts < max_attempts:
                # 检查是否达到最大处理数量
                if processed_count > max_posts_to_process:
                    logger.warning(f"已达到最大处理数量限制")
                    break
                
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
                    # 检查是否达到最大处理数量
                    processed_count += 1
                    if processed_count > max_posts_to_process:
                        logger.warning(f"已处理{max_posts_to_process}个电报，为防止无限处理强制退出")
                        break
                        
                    # 添加板块信息
                    post["section"] = section_name
                    
                    # 创建更精确的电报标识符
                    post_identifier = f"{post.get('title', '')}_{post.get('date', '')}_{post.get('time', '')}"
                    
                    # 跳过重复帖子
                    if post["title"] in processed_titles or post_identifier in processed_identifiers:
                        logger.info(f"电报已处理过，跳过: {post['title']}")
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
                    
                    # 记录标题并分析帖子
                    processed_titles.add(post["title"])
                    processed_identifiers.add(post_identifier)
                    result = self.analyze_post(post)
                    
                    # 确保板块信息被保留
                    if "section" not in result or not result["section"] or result["section"] == "未知板块":
                        result["section"] = section_name
                    
                    section_results.append(result)
                    logger.info(f"成功处理电报: {post['title']}")
            
            return section_results
            
        except Exception as e:
            logger.error(f"爬取{section_name}板块时出错: {e}")
            import traceback
            logger.error(traceback.format_exc())
            
            return section_results

    def debug_page_structure(self):
        """
        调试函数：获取并保存页面结构信息，特别关注包含"评论"的元素
        """
        if "cls.cn/telegraph" in self.page.url:
            logger.info("开始获取cls.cn/telegraph网站DOM结构...")
            
            # 获取当前URL，用于日志标识
            current_url = self.page.url
            timestamp = int(time.time())
            log_prefix = f"/tmp/cls_debug_{timestamp}"
            
            try:
                # 保存完整HTML
                html_content = self.page.content()
                html_path = f"{log_prefix}_page.html"
                with open(html_path, "w", encoding="utf-8") as f:
                    f.write(html_content)
                logger.info(f"已保存页面HTML至: {html_path}")
                
                # 保存页面截图
                screenshot_path = f"{log_prefix}_screenshot.png"
                self.page.screenshot(path=screenshot_path)
                logger.info(f"已保存页面截图至: {screenshot_path}")
                
                # 提取包含"评论"的元素信息
                element_info = self.page.evaluate("""
                    () => {
                        const results = [];
                        const elements = document.querySelectorAll('*');
                        for (const el of elements) {
                            try {
                                if (el.innerText && el.innerText.includes('评论')) {
                                    results.push({
                                        tag: el.tagName,
                                        className: el.className,
                                        id: el.id,
                                        text: el.innerText.substring(0, 50), // 限制长度
                                        parent: el.parentElement ? {
                                            tag: el.parentElement.tagName,
                                            className: el.parentElement.className
                                        } : null,
                                        attributes: Array.from(el.attributes).map(attr => ({ 
                                            name: attr.name, 
                                            value: attr.value 
                                        })),
                                        // 创建CSS选择器
                                        selector: el.id ? `#${el.id}` : 
                                                 el.className ? `.${el.className.replace(/\\s+/g, '.')}` : el.tagName.toLowerCase()
                                    });
                                }
                            } catch (e) {
                                // 跳过错误元素
                                continue;
                            }
                        }
                        return results;
                    }
                """)
                
                # 保存元素信息到文件
                elements_path = f"{log_prefix}_comment_elements.json"
                with open(elements_path, "w", encoding="utf-8") as f:
                    json.dump(element_info, f, ensure_ascii=False, indent=2)
                logger.info(f"已保存包含'评论'的元素信息至: {elements_path}")
                
                # 记录评论计数元素
                comment_count_elements = self.page.evaluate("""
                    () => {
                        const results = [];
                        // 尝试不同的选择器模式
                        const selectors = [
                            'span:has-text("评论")', 
                            'div:has-text("评论")', 
                            '.evaluate-count', 
                            '.comment-count',
                            '[class*="evaluate"]',
                            '[class*="comment"]'
                        ];
                        
                        for (const selector of selectors) {
                            try {
                                const elements = document.querySelectorAll(selector);
                                for (const el of elements) {
                                    if (el.innerText && el.innerText.includes('评论')) {
                                        // 检查是否包含数字
                                        const hasDigit = /\\d+/.test(el.innerText);
                                        results.push({
                                            selector: selector,
                                            text: el.innerText,
                                            hasDigits: hasDigit,
                                            className: el.className,
                                            boundingBox: el.getBoundingClientRect ? {
                                                x: Math.round(el.getBoundingClientRect().x),
                                                y: Math.round(el.getBoundingClientRect().y),
                                                width: Math.round(el.getBoundingClientRect().width),
                                                height: Math.round(el.getBoundingClientRect().height),
                                            } : null
                                        });
                                    }
                                }
                            } catch (e) {
                                // 跳过错误
                                continue;
                            }
                        }
                        return results;
                    }
                """)
                
                # 保存评论计数元素信息
                count_elements_path = f"{log_prefix}_comment_count_elements.json"
                with open(count_elements_path, "w", encoding="utf-8") as f:
                    json.dump(comment_count_elements, f, ensure_ascii=False, indent=2)
                logger.info(f"已保存评论计数元素信息至: {count_elements_path}")
                
                return {
                    "html_path": html_path,
                    "screenshot_path": screenshot_path,
                    "elements_path": elements_path,
                    "count_elements_path": count_elements_path,
                    "element_count": len(element_info),
                    "comment_count_elements": len(comment_count_elements)
                }
                
            except Exception as e:
                logger.error(f"获取页面结构信息失败: {e}")
                import traceback
                logger.error(traceback.format_exc())
                return None
        else:
            logger.info("当前不是cls.cn/telegraph网站，跳过DOM分析")
            return None
    
    def analyze_comment_interaction(self, comment_element):
        """
        分析评论元素的交互，尝试点击评论按钮并提取评论内容
        
        Args:
            comment_element: 评论元素
            
        Returns:
            分析结果字典或None
        """
        try:
            logger.info("开始分析评论元素交互...")
            
            # 初始化结果
            result = {
                "new_elements_count": 0,
                "possible_comments_count": 0,
                "comments": ""
            }
            
            # 检查元素是否可见和可点击
            is_visible = False
            try:
                bbox = comment_element.bounding_box()
                is_visible = bbox and bbox["width"] > 0 and bbox["height"] > 0
                if not is_visible:
                    logger.warning("评论元素不可见，无法进行交互")
                    return None
            except Exception as e:
                logger.warning(f"检查元素可见性失败: {e}")
                # 继续尝试，可能仍然可以点击
            
            # 保存点击前的时间戳用于文件名
            timestamp = int(time.time())
            log_prefix = f"/tmp/comment_interaction_{timestamp}"
            
            # 保存点击前的页面截图
            try:
                before_screenshot_path = f"{log_prefix}_before.png"
                self.page.screenshot(path=before_screenshot_path)
                logger.info(f"已保存点击前的页面截图: {before_screenshot_path}")
            except Exception as e:
                logger.debug(f"保存点击前截图失败: {e}")
            
            # 保存点击前的页面元素数量
            before_elements = []
            try:
                before_elements = self.page.evaluate("""
                    () => {
                        const allElements = document.querySelectorAll('*');
                        const results = [];
                        for (let i = 0; i < Math.min(allElements.length, 1000); i++) {
                            const el = allElements[i];
                            const text = el.innerText?.trim();
                            if (text && text.length > 0 && text.length < 200) {
                                results.push({
                                    tag: el.tagName,
                                    text: text.length > 100 ? text.substring(0, 100) + '...' : text,
                                    className: el.className
                                });
                            }
                        }
                        return results;
                    }
                """)
                
                before_elements_path = f"{log_prefix}_before_elements.json"
                with open(before_elements_path, "w", encoding="utf-8") as f:
                    json.dump(before_elements, f, ensure_ascii=False, indent=2)
                
                logger.info(f"点击前页面有 {len(before_elements)} 个文本元素")
            except Exception as e:
                logger.warning(f"获取点击前元素失败: {e}")
            
            # 尝试使用多种方式点击元素
            click_success = False
            try:
                # 方式1：直接点击
                try:
                    logger.info("尝试直接点击评论元素")
                    comment_element.click(timeout=5000)
                    click_success = True
                    logger.info("直接点击评论元素成功")
                except Exception as e:
                    logger.debug(f"直接点击失败: {e}")
                    
                    # 方式2：使用JavaScript点击
                    if not click_success:
                        try:
                            logger.info("尝试使用JavaScript点击评论元素")
                            self.page.evaluate("(element) => element.click()", comment_element)
                            click_success = True
                            logger.info("JavaScript点击评论元素成功")
                        except Exception as e:
                            logger.debug(f"JavaScript点击失败: {e}")
                    
                    # 方式3：模拟移动鼠标并点击
                    if not click_success:
                        try:
                            logger.info("尝试通过鼠标移动点击评论元素")
                            bbox = comment_element.bounding_box()
                            if bbox:
                                x = bbox["x"] + bbox["width"] / 2
                                y = bbox["y"] + bbox["height"] / 2
                                self.page.mouse.move(x, y)
                                self.page.mouse.click(x, y)
                                click_success = True
                                logger.info(f"鼠标点击评论元素成功 (x={x}, y={y})")
                        except Exception as e:
                            logger.debug(f"鼠标移动点击失败: {e}")
                
                if not click_success:
                    logger.warning("所有点击方法均失败")
                    return None
                
                # 等待点击后的页面加载或变化
                try:
                    # 等待网络空闲、DOM变化或新元素出现
                    self.page.wait_for_load_state("networkidle", timeout=5000)
                except Exception:
                    # 即使等待超时，也继续处理，因为可能已经有变化
                    pass
                
                # 确保足够的等待时间让评论加载
                time.sleep(2)
                
                # 保存点击后的页面截图
                try:
                    after_screenshot_path = f"{log_prefix}_after.png"
                    self.page.screenshot(path=after_screenshot_path)
                    logger.info(f"已保存点击后的页面截图: {after_screenshot_path}")
                except Exception as e:
                    logger.debug(f"保存点击后截图失败: {e}")
                
                # 保存点击后的页面元素
                after_elements = []
                try:
                    after_elements = self.page.evaluate("""
                        () => {
                            const allElements = document.querySelectorAll('*');
                            const results = [];
                            for (let i = 0; i < Math.min(allElements.length, 1000); i++) {
                                const el = allElements[i];
                                const text = el.innerText?.trim();
                                if (text && text.length > 0 && text.length < 200) {
                                    results.push({
                                        tag: el.tagName,
                                        text: text.length > 100 ? text.substring(0, 100) + '...' : text,
                                        className: el.className
                                    });
                                }
                            }
                            return results;
                        }
                    """)
                except Exception as e:
                    logger.warning(f"获取点击后元素失败: {e}")
                    after_elements = []
                
                after_elements_path = f"{log_prefix}_after_elements.json"
                with open(after_elements_path, "w", encoding="utf-8") as f:
                    json.dump(after_elements, f, ensure_ascii=False, indent=2)
                
                # 分析元素变化
                new_elements_count = len(after_elements) - len(before_elements)
                logger.info(f"点击后元素数量变化: {new_elements_count} (前: {len(before_elements)}, 后: {len(after_elements)})")
                result["new_elements_count"] = new_elements_count
                
                # 如果元素数量没有明显增加，可能不是成功展开评论
                if new_elements_count <= 0:
                    logger.warning("点击后元素数量没有增加，可能未成功展开评论")
                    # 尝试查找可能的评论内容，即使元素数量没有增加
                
                # 获取页面上所有可能的评论内容
                possible_comments = self.page.evaluate("""
                    () => {
                        const results = [];
                        // 尝试各种可能的评论内容选择器
                        const commentSelectors = [
                            '.comment-item', '.comment-text', '.comment-content',
                            '.evaluate-content', '.comment-body', '[class*="comment-"]',
                            // 更通用的文本选择器 - 针对评论的特征
                            'div', 'p', 'span'
                        ];
                        
                        // 可能的评论容器
                        const containerSelectors = [
                            '.comment-list', '.comments-container', '.evaluate-list',
                            '[class*="comment"]', '[class*="evaluate"]'
                        ];
                        
                        // 先尝试从评论容器中查找
                        for (const containerSelector of containerSelectors) {
                            const containers = document.querySelectorAll(containerSelector);
                            for (const container of containers) {
                                // 在容器中查找评论元素
                                for (const selector of commentSelectors) {
                                    const elements = container.querySelectorAll(selector);
                                    for (const el of elements) {
                                        const text = el.innerText?.trim();
                                        // 评论特征：不太短不太长，不含特定词汇
                                        if (text && text.length > 3 && text.length < 1000 && 
                                            !text.includes('评论') && !text.includes('登录') && 
                                            !text.includes('注册') && !text.includes('点赞')) {
                                            
                                            results.push({
                                                selector: containerSelector + ' ' + selector,
                                                text: text,
                                                className: el.className,
                                                isNew: !el.hasAttribute('data-seen')
                                            });
                                            el.setAttribute('data-seen', 'true');
                                        }
                                    }
                                }
                            }
                        }
                        
                        // 如果没有找到，直接在页面中查找
                        if (results.length === 0) {
                            for (const selector of commentSelectors) {
                                const elements = document.querySelectorAll(selector);
                                for (const el of elements) {
                                    const text = el.innerText?.trim();
                                    if (text && text.length > 3 && text.length < 1000 && 
                                        !text.includes('评论') && !text.includes('登录') && 
                                        !text.includes('注册')) {
                                        
                                        // 进一步过滤 - 检查是否像评论
                                        // 评论通常不会包含很多HTML标签
                                        const hasLowTagDensity = el.innerHTML.length / text.length < 3;
                                        
                                        if (hasLowTagDensity) {
                                            results.push({
                                                selector: selector,
                                                text: text,
                                                className: el.className,
                                                isNew: !el.hasAttribute('data-seen')
                                            });
                                            el.setAttribute('data-seen', 'true');
                                        }
                                    }
                                }
                            }
                        }
                        
                        // 如果上面的方法都没找到评论，尝试查找任何可能是评论的文本内容
                        if (results.length === 0) {
                            // 避免检查整个文档，只检查在点击后可能出现的部分
                            const elementsAfterClick = Array.from(document.querySelectorAll('*'))
                                .filter(el => !el.hasAttribute('data-seen-before-click'));
                            
                            for (const el of elementsAfterClick) {
                                const text = el.innerText?.trim();
                                // 更宽松的评论识别标准
                                if (text && text.length > 5 && text.length < 500 && 
                                    !text.includes('登录') && !text.includes('注册') &&
                                    !text.includes('评论') && !text.includes('点赞')) {
                                    
                                    results.push({
                                        selector: el.tagName.toLowerCase(),
                                        text: text,
                                        className: el.className,
                                        isNew: true
                                    });
                                }
                                el.setAttribute('data-seen', 'true');
                            }
                        }
                        
                        return results;
                    }
                """)
                
                # 保存可能的评论
                comments_path = f"{log_prefix}_possible_comments.json"
                with open(comments_path, "w", encoding="utf-8") as f:
                    json.dump(possible_comments, f, ensure_ascii=False, indent=2)
                
                # 更新结果
                result["possible_comments_count"] = len(possible_comments)
                result["comments"] = comments_path
                
                logger.info(f"找到 {len(possible_comments)} 条可能的评论")
                return result
                
            except Exception as e:
                logger.error(f"处理点击交互时出错: {e}")
                import traceback
                logger.error(traceback.format_exc())
                return None
                
        except Exception as e:
            logger.error(f"分析评论元素交互时出错: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None