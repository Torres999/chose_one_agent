# -*- coding: utf-8 -*-
import logging
import re
from typing import List, Dict, Any

from chose_one_agent.analyzers.sentiment_analyzer import SentimentAnalyzer
from chose_one_agent.analyzers.deepseek_sentiment_analyzer import DeepSeekSentimentAnalyzer
from chose_one_agent.analyzers.keyword_analyzer import KeywordAnalyzer

# 配置日志
logger = logging.getLogger(__name__)

class PostAnalyzer:
    """
    帖子分析器类，负责对帖子内容和评论进行情感分析和关键词分析
    """
    
    def __init__(self, sentiment_analyzer, keyword_analyzer, debug=False):
        """
        初始化帖子分析器
        
        Args:
            sentiment_analyzer: 情感分析器实例
            keyword_analyzer: 关键词分析器实例
            debug: 是否启用调试模式
        """
        self.sentiment_analyzer = sentiment_analyzer
        self.keyword_analyzer = keyword_analyzer
        self.debug = debug
    
    def analyze_post(self, post_info: Dict[str, Any], comments: List[str]) -> Dict[str, Any]:
        """
        分析帖子内容，提取关键信息，进行情感分析和关键词分析

        Args:
            post_info: 包含帖子信息的字典
            comments: 帖子评论列表

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
                "comment_keyword_analysis": {}
            }

            # 获取评论计数
            comment_count = post_info.get("comment_count", 0)
            
            # 处理评论分析
            if comments:
                result["comments"] = comments
                result["has_comments"] = True
                
                # 分析评论情感
                sentiment_score = self.analyze_sentiment(comments)
                result["sentiment_score"] = sentiment_score
                result["sentiment_label"] = self._get_sentiment_label(sentiment_score)
                
                logger.info(f"帖子 '{title}' 评论情感分数: {sentiment_score}, 标签: {result['sentiment_label']}")
                
                # 对评论内容进行关键词分析
                try:
                    all_comments_text = " ".join(comments)
                    comment_keywords = self.keyword_analyzer.analyze_text(all_comments_text)
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
                        detailed_analysis = self.analyze_sentiment_with_deepseek(comments)
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
            
            return result
            
        except Exception as e:
            logger.error(f"分析帖子 '{title}' 时出错: {e}")
            return {
                "title": title,
                "date": post_info.get("date", "未知日期"),
                "time": post_info.get("time", "未知时间"),
                "error": str(e)
            }
    
    def _get_sentiment_label(self, score: int) -> str:
        """
        根据情感得分获取对应的标签
        
        Args:
            score: 情感得分(0-5)
            
        Returns:
            情感标签
        """
        if score == 0:
            return "无评论"
        elif score == 1:
            return "极度消极"
        elif score == 2:
            return "消极"
        elif score == 3:
            return "中性"
        elif score == 4:
            return "积极"
        elif score == 5:
            return "极度积极"
        else:
            return "未知"
            
    def analyze_sentiment(self, comments: List[str]) -> int:
        """
        分析评论的情感
        
        Args:
            comments: 评论列表
            
        Returns:
            情感得分(1-5)，如果没有评论则返回0
        """
        if not comments:
            return 0
            
        # 使用情感分析器获取得分
        if isinstance(self.sentiment_analyzer, DeepSeekSentimentAnalyzer):
            # 使用DeepSeek API进行批量分析
            try:
                # 限制评论数量，避免API调用过多
                limited_comments = comments[:20] if len(comments) > 20 else comments
                
                # 调用API获取情感得分
                score = self.sentiment_analyzer.analyze_comments(limited_comments)
                
                if self.debug:
                    logger.info(f"DeepSeek情感分析得分: {score}")
                    
                return score
            except Exception as e:
                logger.error(f"DeepSeek情感分析出错: {e}")
                # 出错时使用简单方法分析
                return self._analyze_sentiment_simple(comments)
        else:
            # 使用简单方法分析
            return self._analyze_sentiment_simple(comments)
            
    def _analyze_sentiment_simple(self, comments: List[str]) -> int:
        """
        使用简单算法分析情感
        
        Args:
            comments: 评论列表
            
        Returns:
            情感得分(1-5)
        """
        # 简单版情感分析
        positive_words = ["好", "涨", "利好", "上涨", "看多", "看好", "利多", "牛", "赚", 
                       "盈利", "增长", "利润", "吸筹", "拉升", "暴涨", "突破", 
                       "牛市", "牛股", "强势"]
                       
        negative_words = ["差", "跌", "利空", "下跌", "看空", "看淡", "利空", "熊", "亏", 
                        "亏损", "下降", "被套", "套牢", "暴跌", "破位", 
                        "熊市", "熊股", "弱势"]
                        
        # 统计正面词和负面词
        positive_count = 0
        negative_count = 0
        
        for comment in comments:
            for word in positive_words:
                positive_count += comment.count(word)
            for word in negative_words:
                negative_count += comment.count(word)
                
        # 计算情感比例
        total = positive_count + negative_count
        if total == 0:
            # 没有情感关键词，返回中性
            return 3
            
        positive_ratio = positive_count / total
        
        # 根据比例确定情感得分
        if positive_ratio >= 0.8:
            return 5  # 极度积极
        elif positive_ratio >= 0.6:
            return 4  # 积极
        elif positive_ratio >= 0.4:
            return 3  # 中性
        elif positive_ratio >= 0.2:
            return 2  # 消极
        else:
            return 1  # 极度消极
            
    def analyze_sentiment_with_deepseek(self, comments: List[str]) -> str:
        """
        使用DeepSeek进行详细的情感分析，生成分析文本
        
        Args:
            comments: 评论列表
            
        Returns:
            详细的情感分析文本
        """
        if not comments:
            return ""
            
        # 仅在使用DeepSeek分析器时调用
        if not isinstance(self.sentiment_analyzer, DeepSeekSentimentAnalyzer):
            return ""
            
        try:
            # 获取评论中的情感分布
            sentiment_distribution = self._get_sentiment_distribution(comments)
            
            # 提取情感关键词
            sentiment_keywords = self._extract_sentiment_keywords(comments)
            
            # 生成市场情绪
            market_sentiment = self._generate_market_sentiment(sentiment_distribution)
            
            # 组装分析结果
            analysis_result = f"市场情绪：{market_sentiment}\n\n"
            
            # 添加情感分布
            analysis_result += "情感分布：\n"
            for sentiment, percentage in sentiment_distribution.items():
                analysis_result += f"- {sentiment}: {percentage:.1f}%\n"
                
            # 添加情感关键词
            if sentiment_keywords:
                analysis_result += "\n情感关键词：\n"
                for sentiment, keywords in sentiment_keywords.items():
                    if keywords:
                        analysis_result += f"- {sentiment}: {', '.join(keywords[:5])}\n"
                        
            # 添加代表性评论示例
            analysis_result += "\n代表性评论：\n"
            
            # 最多选择3条评论作为示例
            sample_comments = comments[:3] if len(comments) > 3 else comments
            for i, comment in enumerate(sample_comments, 1):
                # 限制评论长度，避免过长
                short_comment = comment[:100] + "..." if len(comment) > 100 else comment
                analysis_result += f"{i}. {short_comment}\n"
                
            return analysis_result
            
        except Exception as e:
            logger.error(f"生成详细情感分析时出错: {e}")
            return ""
            
    def _get_sentiment_distribution(self, comments: List[str]) -> Dict[str, float]:
        """
        获取评论的情感分布
        
        Args:
            comments: 评论列表
            
        Returns:
            情感分布字典，键为情感标签，值为百分比
        """
        # 使用简单方法计算情感分布
        sentiments = {
            "积极": 0,
            "中性": 0,
            "消极": 0
        }
        
        # 情感词典
        positive_words = ["好", "涨", "利好", "上涨", "看多", "看好", "赚"]
        negative_words = ["差", "跌", "利空", "下跌", "看空", "看淡", "亏"]
        
        for comment in comments:
            pos_count = sum(comment.count(word) for word in positive_words)
            neg_count = sum(comment.count(word) for word in negative_words)
            
            if pos_count > neg_count:
                sentiments["积极"] += 1
            elif neg_count > pos_count:
                sentiments["消极"] += 1
            else:
                sentiments["中性"] += 1
                
        # 转换为百分比
        total = len(comments)
        if total > 0:
            for sentiment in sentiments:
                sentiments[sentiment] = (sentiments[sentiment] / total) * 100
                
        return sentiments
        
    def _extract_sentiment_keywords(self, comments: List[str]) -> Dict[str, List[str]]:
        """
        从评论中提取情感关键词
        
        Args:
            comments: 评论列表
            
        Returns:
            情感关键词字典，键为情感标签，值为关键词列表
        """
        # 情感词典
        positive_words = ["好", "涨", "利好", "上涨", "看多", "看好", "利多", "牛", "赚", 
                       "盈利", "增长", "利润", "吸筹", "拉升", "暴涨", "突破"]
                       
        negative_words = ["差", "跌", "利空", "下跌", "看空", "看淡", "利空", "熊", "亏", 
                        "亏损", "下降", "被套", "套牢", "暴跌", "破位"]
                        
        # 统计词频
        positive_counts = {}
        negative_counts = {}
        
        for comment in comments:
            for word in positive_words:
                if word in comment:
                    positive_counts[word] = positive_counts.get(word, 0) + 1
                    
            for word in negative_words:
                if word in comment:
                    negative_counts[word] = negative_counts.get(word, 0) + 1
                    
        # 排序并提取前10个关键词
        positive_keywords = sorted(positive_counts.items(), key=lambda x: x[1], reverse=True)
        negative_keywords = sorted(negative_counts.items(), key=lambda x: x[1], reverse=True)
        
        return {
            "积极关键词": [word for word, _ in positive_keywords[:10]],
            "消极关键词": [word for word, _ in negative_keywords[:10]]
        }
        
    def _generate_market_sentiment(self, sentiment_distribution: Dict[str, float]) -> str:
        """
        根据情感分布生成市场情绪描述
        
        Args:
            sentiment_distribution: 情感分布字典
            
        Returns:
            市场情绪描述
        """
        positive = sentiment_distribution.get("积极", 0)
        negative = sentiment_distribution.get("消极", 0)
        neutral = sentiment_distribution.get("中性", 0)
        
        # 根据情感分布确定市场情绪
        if positive >= 60:
            return "市场情绪非常乐观，投资者对未来表现持积极态度"
        elif positive >= 40 and positive > negative:
            return "市场情绪偏乐观，但也存在一些担忧"
        elif negative >= 60:
            return "市场情绪悲观，投资者对未来表现持消极态度"
        elif negative >= 40 and negative > positive:
            return "市场情绪偏悲观，谨慎情绪较浓"
        elif neutral >= 50:
            return "市场情绪中性，投资者观望态度明显"
        else:
            return "市场情绪混合，乐观与悲观并存" 