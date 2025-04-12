import logging
from typing import List, Tuple
from snownlp import SnowNLP

# 配置日志
logger = logging.getLogger(__name__)

class SentimentAnalyzer:
    """
    使用SnowNLP进行中文情感分析的类
    """
    
    def __init__(self, 
                 positive_threshold: float = 0.6, 
                 negative_threshold: float = 0.4):
        """
        初始化情感分析器
        
        Args:
            positive_threshold: 积极情感的阈值，高于此值被视为积极
            negative_threshold: 消极情感的阈值，低于此值被视为消极
        """
        self.positive_threshold = positive_threshold
        self.negative_threshold = negative_threshold
    
    def analyze_text(self, text: str) -> Tuple[str, float]:
        """
        分析单条文本的情感
        
        Args:
            text: 待分析的文本
            
        Returns:
            (情感标签, 情感得分)的元组，情感标签为"正面"、"负面"或"中性"
        """
        try:
            # 使用SnowNLP分析情感
            score = SnowNLP(text).sentiments
            
            # 根据得分确定情感标签
            if score >= self.positive_threshold:
                sentiment = "正面"
            elif score <= self.negative_threshold:
                sentiment = "负面"
            else:
                sentiment = "中性"
                
            return sentiment, score
        
        except Exception as e:
            logger.error(f"情感分析错误: {e}")
            return "中性", 0.5
    
    def analyze_comments(self, comments: List[str]) -> str:
        """
        分析多条评论，综合得出整体情感
        
        Args:
            comments: 评论列表
            
        Returns:
            整体情感标签，为"正面"、"负面"或"中性"
        """
        if not comments:
            return "中性"
        
        try:
            # 分析每条评论
            sentiments_with_scores = [self.analyze_text(comment) for comment in comments]
            
            # 计算平均得分
            total_score = sum(score for _, score in sentiments_with_scores)
            avg_score = total_score / len(sentiments_with_scores)
            
            # 统计各类情感数量
            sentiment_counts = {
                "正面": sum(1 for sentiment, _ in sentiments_with_scores if sentiment == "正面"),
                "负面": sum(1 for sentiment, _ in sentiments_with_scores if sentiment == "负面"),
                "中性": sum(1 for sentiment, _ in sentiments_with_scores if sentiment == "中性")
            }
            
            # 如果某类情感占比超过60%，则采用该情感
            max_sentiment = max(sentiment_counts, key=sentiment_counts.get)
            max_count = sentiment_counts[max_sentiment]
            
            if max_count / len(comments) >= 0.6:
                return max_sentiment
            
            # 否则，根据平均得分判断
            if avg_score >= self.positive_threshold:
                return "正面"
            elif avg_score <= self.negative_threshold:
                return "负面"
            else:
                return "中性"
                
        except Exception as e:
            logger.error(f"评论综合分析错误: {e}")
            return "中性" 