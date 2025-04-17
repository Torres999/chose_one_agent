"""
Telegraph数据分析模块，提供情感分析和关键词提取功能
"""
import re
import logging
import traceback
from typing import List, Dict, Any, Tuple
from collections import Counter

from chose_one_agent.analyzers.text_analyzer import TextAnalyzer

logger = logging.getLogger(__name__)

class TelegraphAnalyzer:
    """Telegraph数据分析类，提供情感分析和关键词提取功能"""
    
    def __init__(self, sentiment_analyzer_type: str = "snownlp", deepseek_api_key: str = None, debug: bool = False):
        """初始化分析器
        
        Args:
            sentiment_analyzer_type: 情感分析器类型 ('snownlp', 'deepseek', 'simple')
            deepseek_api_key: DeepSeek API密钥
            debug: 是否开启调试模式
        """
        self.debug = debug
        
        # 使用统一的TextAnalyzer替代单独的情感和关键词分析器
        self.analyzer = TextAnalyzer(
            sentiment_analyzer_type=sentiment_analyzer_type,
            deepseek_api_key=deepseek_api_key,
            debug=debug
        )
    
    def analyze_sentiment(self, text: str) -> Dict[str, float]:
        """分析文本情感，返回情感得分"""
        return self.analyzer.analyze_sentiment(text)
    
    def extract_keywords(self, text: str, top_n: int = 5) -> List[str]:
        """提取文本关键词"""
        if not text or text.strip() == "":
            return []
        
        try:
            return self.analyzer.extract_keywords(text, top_n=top_n)
        except Exception as e:
            logger.error("提取关键词时出错: {}".format(e))
            if self.debug:
                logger.error(traceback.format_exc())
            return []
    
    def analyze_post(self, post) -> Any:
        """分析帖子及其评论，更新情感分析和关键词"""
        # 分析帖子标题和内容
        title_sentiment = self.analyze_sentiment(post.title)
        content_sentiment = self.analyze_sentiment(post.content or post.title)
        
        # 提取关键词
        content_keywords = self.extract_keywords(post.content or post.title)
        
        # 获取财经术语
        keyword_analysis = self.analyzer.analyze_text(post.content or post.title)
        financial_terms = keyword_analysis.get("financial_terms", [])
        
        # 更新帖子情感分析
        post.sentiment_analysis = {
            "title": title_sentiment,
            "content": content_sentiment,
            "overall": self.analyzer._combine_sentiment_scores([title_sentiment, content_sentiment]),
            "financial_terms": financial_terms,
            "has_financial_content": bool(financial_terms)
        }
        
        # 分析评论
        if hasattr(post, 'comments') and post.comments:
            for comment in post.comments:
                sentiment = self.analyze_sentiment(comment.content)
                comment.sentiment_score = sentiment.get("compound", 0.0)
                comment.keywords = self.extract_keywords(comment.content, top_n=3)
            
            # 添加评论情感摘要
            comment_sentiments = [self.analyze_sentiment(c.content) for c in post.comments]
            post.sentiment_analysis["comments"] = self.analyzer._combine_sentiment_scores(comment_sentiments)
            
            # 添加整体评分
            all_sentiments = [title_sentiment, content_sentiment] + comment_sentiments
            post.sentiment_analysis["overall"] = self.analyzer._combine_sentiment_scores(all_sentiments)
        
        return post
    
    def analyze_post_batch(self, posts: List[Any]) -> List[Any]:
        """批量分析多个帖子"""
        return [self.analyze_post(post) for post in posts]
    
    def get_trending_keywords(self, posts: List[Any], limit: int = 10) -> List[Tuple[str, int]]:
        """获取热门关键词及其频率"""
        keywords_counter = Counter()
        
        # 收集所有关键词
        for post in posts:
            # 帖子内容关键词
            post_keywords = self.extract_keywords(post.content or post.title)
            keywords_counter.update(post_keywords)
            
            # 评论关键词
            if hasattr(post, 'comments'):
                for comment in post.comments:
                    if hasattr(comment, 'keywords') and comment.keywords:
                        keywords_counter.update(comment.keywords)
        
        # 返回出现频率最高的关键词
        return keywords_counter.most_common(limit)

    def analyze_post_data(self, post_data: Dict[str, Any], comments: List[str] = None) -> Dict[str, Any]:
        """分析帖子数据
        
        Args:
            post_data: 帖子数据字典
            comments: 帖子评论列表
            
        Returns:
            Dict: 分析结果
        """
        title = post_data.get("title", "未知标题")
        
        # 初始化结果
        result = {
            "title": title,
            "date": post_data.get("date", "未知日期"),
            "time": post_data.get("time", "未知时间"),
            "section": post_data.get("section", "未知板块"),
            "comments": comments or [],
            "has_comments": bool(comments),
            "sentiment_score": 0,
            "sentiment_label": "无评论"
        }
        
        # 如果没有评论，返回基本结果
        if not comments:
            return result
            
        try:
            # 情感分析
            # 合并所有评论内容进行整体分析
            combined_comments = " ".join(comments)
            sentiment_score = self.analyze_sentiment(combined_comments)
            result["sentiment_score"] = sentiment_score
            result["sentiment_label"] = self.analyzer.get_sentiment_label(sentiment_score.get("compound", 0))
            
            # 关键词分析
            keyword_results = self.analyzer.analyze_text(combined_comments)
            result["keywords"] = keyword_results.get("keywords", [])
            result["financial_terms"] = keyword_results.get("financial_terms", [])
            result["has_financial_content"] = keyword_results.get("has_financial_content", False)
            result["financial_relevance"] = keyword_results.get("financial_relevance", 0.0)
            
            # 详细情感分析(DeepSeek)
            if self.analyzer.sentiment_analyzer_type == "deepseek" and self.analyzer.deepseek_api_key:
                try:
                    details = self.analyzer.get_detailed_analysis(comments[:10])
                    result["detailed_analysis"] = details
                except Exception as e:
                    logger.error("获取详细分析时出错: {}".format(e))
                    if self.debug:
                        logger.error(traceback.format_exc())
            
            # 生成洞察
            result["insight"] = self.analyzer.generate_insight(result)
            
            return result
        except Exception as e:
            logger.error("分析帖子 '{}' 时出错: {}".format(title, e))
            if self.debug:
                logger.error(traceback.format_exc())
            return dict(result, error=str(e))

    def get_sentiment_label(self, compound_score: float) -> str:
        """获取情感标签"""
        return self.analyzer.get_sentiment_label(compound_score)

    def get_detailed_analysis(self, comments: List[str]) -> Dict[str, Any]:
        """获取详细情感分析（DeepSeek专用）"""
        return self.analyzer.get_detailed_analysis(comments)

    def generate_insight(self, analysis_result: Dict[str, Any]) -> str:
        """生成分析洞察"""
        return self.analyzer.generate_insight(analysis_result)

    def _clean_text(self, text: str) -> str:
        """清理文本"""
        if not text:
            return ""
        # 移除HTML标签
        text = re.sub(r'<[^>]+>', '', text)
        # 移除多余空白
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def _extract_financial_terms(self, text: str) -> List[str]:
        """提取财经术语"""
        return self.analyzer.extract_financial_terms(text)

    def _calculate_financial_relevance(self, text: str) -> float:
        """计算文本与财经相关度"""
        return self.analyzer.calculate_financial_relevance(text) 