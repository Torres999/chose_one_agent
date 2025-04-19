"""
Telegraph数据分析模块，提供情感分析和关键词提取功能
"""
import re
import logging
import traceback
from typing import List, Dict, Any, Tuple
from collections import Counter

try:
    from snownlp import SnowNLP
    SNOWNLP_AVAILABLE = True
except ImportError:
    SNOWNLP_AVAILABLE = False

try:
    import nltk
    NLTK_AVAILABLE = True
except ImportError:
    NLTK_AVAILABLE = False

try:
    import jieba
    JIEBA_AVAILABLE = True
except ImportError:
    JIEBA_AVAILABLE = False

# 从constants模块导入常量
from chose_one_agent.utils.constants import SENTIMENT_LABELS, FINANCIAL_TERMS, SENTIMENT_SCORE_LABELS
from chose_one_agent.utils.logging_utils import get_logger

# 获取日志记录器
logger = get_logger(__name__)

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
        self.sentiment_analyzer_type = sentiment_analyzer_type
        self.deepseek_api_key = deepseek_api_key
        self.min_keyword_length = 2
        self.max_keywords = 10
        
        # 初始化情感分析器
        self._init_sentiment_analyzer()
        
        # 初始化停用词
        self.stopwords = self._init_stopwords()
    
    def _init_sentiment_analyzer(self):
        """初始化情感分析器"""
        if self.sentiment_analyzer_type == "deepseek" and self.deepseek_api_key:
            try:
                from chose_one_agent.analyzers.deepseek_sentiment_analyzer import DeepSeekSentimentAnalyzer
                self.sentiment_analyzer = DeepSeekSentimentAnalyzer(self.deepseek_api_key)
            except ImportError:
                logger.warning("DeepSeek分析器不可用，使用SnowNLP")
                self.sentiment_analyzer_type = "snownlp"
                self._init_sentiment_analyzer()
        elif self.sentiment_analyzer_type == "snownlp" and SNOWNLP_AVAILABLE:
            self.sentiment_analyzer = SnowNLP
        else:
            self.sentiment_analyzer_type = "simple"
            logger.warning("使用简单情感分析器")
    
    def _init_stopwords(self):
        """初始化停用词"""
        stopwords = set()
        if NLTK_AVAILABLE:
            try:
                nltk.data.find('corpora/stopwords')
            except LookupError:
                nltk.download('stopwords')
            from nltk.corpus import stopwords as nltk_stopwords
            stopwords.update(nltk_stopwords.words('chinese'))
        return stopwords
    
    def analyze_sentiment(self, text: str) -> Dict[str, float]:
        """分析文本情感
        
        Args:
            text: 待分析文本
            
        Returns:
            Dict[str, float]: 情感分析结果
        """
        if not text or text.strip() == "":
            return {"pos": 0.0, "neg": 0.0, "neu": 1.0, "compound": 0.0}
        
        if self.sentiment_analyzer_type == "deepseek":
            result = self.sentiment_analyzer.analyze_comments_batch([text])
            # 转换DeepSeek结果格式为统一格式
            score = result.get("score", 0)
            # 将0-5的分数映射到-1到1的compound值
            compound = (score - 2.5) / 2.5 if score > 0 else 0
            return {
                "pos": max(0, compound),
                "neg": max(0, -compound),
                "neu": 1.0 - abs(compound),
                "compound": compound
            }
        elif self.sentiment_analyzer_type == "snownlp":
            s = self.sentiment_analyzer(text)
            return {
                "pos": s.sentiments,
                "neg": 1 - s.sentiments,
                "neu": 0.0,
                "compound": (s.sentiments - 0.5) * 2
            }
        else:
            # 简单情感分析
            positive_words = {"好", "涨", "升", "强", "优", "良", "佳"}
            negative_words = {"差", "跌", "降", "弱", "劣", "差", "坏"}
            
            words = set(text.split())
            pos_count = len(words & positive_words)
            neg_count = len(words & negative_words)
            total = pos_count + neg_count
            
            if total == 0:
                return {"pos": 0.0, "neg": 0.0, "neu": 1.0, "compound": 0.0}
            
            pos_score = pos_count / total
            neg_score = neg_count / total
            return {
                "pos": pos_score,
                "neg": neg_score,
                "neu": 1 - (pos_score + neg_score),
                "compound": pos_score - neg_score
            }

    def extract_keywords(self, text: str, top_n: int = 5) -> List[str]:
        """提取文本关键词
        
        Args:
            text: 待分析文本
            top_n: 返回关键词数量
            
        Returns:
            List[str]: 关键词列表
        """
        if not text or text.strip() == "":
            return []
        
        # 分词
        words = self._tokenize(text)
        
        # 过滤停用词和短词
        words = [word for word in words 
                if len(word) >= self.min_keyword_length 
                and word not in self.stopwords]
        
        # 统计词频
        word_freq = Counter(words)
        
        # 返回频率最高的词
        return [word for word, _ in word_freq.most_common(top_n)]
    
    def _tokenize(self, text: str) -> List[str]:
        """分词
        
        Args:
            text: 待分词文本
            
        Returns:
            List[str]: 分词结果
        """
        if NLTK_AVAILABLE:
            try:
                from nltk.tokenize import word_tokenize
                return word_tokenize(text)
            except (ImportError, LookupError):
                pass
        return text.split()
    
    def get_sentiment_label(self, compound_score: float) -> str:
        """获取情感标签
        
        Args:
            compound_score: 情感得分
            
        Returns:
            str: 情感标签
        """
        for label, (min_score, max_score) in SENTIMENT_LABELS.items():
            if min_score <= compound_score <= max_score:
                return label
        return "未知"
    
    def extract_financial_terms(self, text: str) -> List[str]:
        """提取财经术语
        
        Args:
            text: 待分析文本
            
        Returns:
            List[str]: 财经术语列表
        """
        if not text or text.strip() == "":
            return []
        
        found_terms = []
        for term in FINANCIAL_TERMS:
            if term in text:
                found_terms.append(term)
        return found_terms
    
    def calculate_financial_relevance(self, text: str) -> float:
        """计算财经相关度
        
        Args:
            text: 待分析文本
            
        Returns:
            float: 财经相关度，0-1之间
        """
        if not text or text.strip() == "":
            return 0.0
        
        terms = self.extract_financial_terms(text)
        if not terms:
            return 0.0
        
        # 简单计算：出现的财经术语数量除以固定值
        relevance = min(1.0, len(terms) / 5.0)
        return relevance
    
    def analyze_text(self, text: str) -> Dict[str, Any]:
        """分析文本内容
        
        Args:
            text: 待分析文本
            
        Returns:
            Dict[str, Any]: 分析结果
        """
        if not text or text.strip() == "":
            return {
                "sentiment": {"pos": 0.0, "neg": 0.0, "neu": 1.0, "compound": 0.0},
                "sentiment_label": "无评论",
                "keywords": [],
                "financial_terms": [],
                "financial_relevance": 0.0,
                "has_financial_content": False
            }
        
        # 情感分析
        sentiment = self.analyze_sentiment(text)
        sentiment_label = self.get_sentiment_label(sentiment.get("compound", 0))
        
        # 关键词分析
        keywords = self.extract_keywords(text, top_n=self.max_keywords)
        
        # 财经相关性分析
        financial_terms = self.extract_financial_terms(text)
        financial_relevance = self.calculate_financial_relevance(text)
        
        return {
            "sentiment": sentiment,
            "sentiment_label": sentiment_label,
            "keywords": keywords,
            "financial_terms": financial_terms,
            "financial_relevance": financial_relevance,
            "has_financial_content": bool(financial_terms)
        }
    
    def _combine_sentiment_scores(self, scores: List[Dict[str, float]]) -> Dict[str, float]:
        """合并多个情感得分
        
        Args:
            scores: 情感得分列表
            
        Returns:
            Dict[str, float]: 合并后的情感得分
        """
        if not scores:
            return {"pos": 0.0, "neg": 0.0, "neu": 1.0, "compound": 0.0}
        
        # 简单平均
        pos_avg = sum(s.get("pos", 0) for s in scores) / len(scores)
        neg_avg = sum(s.get("neg", 0) for s in scores) / len(scores)
        neu_avg = sum(s.get("neu", 0) for s in scores) / len(scores)
        compound_avg = sum(s.get("compound", 0) for s in scores) / len(scores)
        
        return {
            "pos": pos_avg,
            "neg": neg_avg,
            "neu": neu_avg,
            "compound": compound_avg
        }
    
    def get_detailed_analysis(self, comments: List[str]) -> Dict[str, Any]:
        """获取详细分析
        
        Args:
            comments: 评论列表
            
        Returns:
            Dict[str, Any]: 详细分析结果
        """
        if not comments:
            return {}
        
        if self.sentiment_analyzer_type == "deepseek" and hasattr(self.sentiment_analyzer, "analyze_batch"):
            return self.sentiment_analyzer.analyze_batch(comments[:10])
        return {}
    
    def generate_insight(self, analysis_result: Dict[str, Any]) -> str:
        """生成洞察
        
        Args:
            analysis_result: 分析结果
            
        Returns:
            str: 洞察内容
        """
        if not analysis_result:
            return "暂无洞察"
            
        title = analysis_result.get("title", "未知标题")
        sentiment_label = analysis_result.get("sentiment_label", "无评论")
        keywords = analysis_result.get("keywords", [])
        financial_terms = analysis_result.get("financial_terms", [])
        has_financial = analysis_result.get("has_financial_content", False)
        
        # 生成基本洞察
        insights = []
        
        # 主题
        if keywords:
            topics = "、".join(keywords[:3])
            insights.append(f"主要讨论{topics}等话题")
            
        # 情感倾向
        if sentiment_label in ["积极", "极度积极"]:
            sentiment_text = "积极乐观"
        elif sentiment_label in ["消极", "极度消极"]:
            sentiment_text = "消极悲观"
        else:
            sentiment_text = "情绪中性"
            
        insights.append(f"整体情绪{sentiment_text}")
        
        # 财经相关度
        if has_financial:
            terms = "、".join(financial_terms[:3])
            insights.append(f"涉及{terms}等财经概念")
        
        return "。".join(insights) + "。"
    
    def analyze_post_data(self, post_data: Dict[str, Any], comments: List[str] = None) -> Dict[str, Any]:
        """
        分析帖子数据并返回分析结果
        
        Args:
            post_data: 帖子数据
            comments: 评论列表
            
        Returns:
            Dict[str, Any]: 分析结果
        """
        result = {
            "sentiment_score": 0,
            "sentiment_label": "无评论",
            "insight": "",
            "comment_scores": {}
        }
        
        # 如果没有评论，直接返回默认结果
        if not comments:
            return result
            
        # 合并评论文本进行分析
        combined_comments = " ".join([comment.get("content", "") if isinstance(comment, dict) else comment for comment in comments])
        if not combined_comments.strip():
            return result
            
        # 情感分析
        sentiment_score = self.analyze_sentiment(combined_comments)
        result["sentiment_score"] = sentiment_score
        
        # 使用整数得分来查找情感标签
        if isinstance(sentiment_score, dict) and "compound" in sentiment_score:
            compound = sentiment_score["compound"]
            # 将-1到1的范围映射到0-5的整数
            score_int = round((compound + 1) * 2.5)
            # 确保分数在有效范围内
            score_int = max(0, min(5, score_int))
            result["sentiment_label"] = SENTIMENT_SCORE_LABELS.get(score_int, "无评论")
        elif isinstance(sentiment_score, (int, float)):
            # 直接使用整数得分
            score_int = round(sentiment_score)
            # 确保分数在有效范围内
            score_int = max(0, min(5, score_int)) 
            result["sentiment_label"] = SENTIMENT_SCORE_LABELS.get(score_int, "无评论")
        else:
            # 默认返回经典标签方式
            result["sentiment_label"] = self.get_sentiment_label(sentiment_score.get("compound", 0))
            
        # 生成洞察
        insight = self.generate_insight({
            "title": post_data.get("title", ""),
            "sentiment_label": result["sentiment_label"],
            "keywords": self.extract_keywords(combined_comments, 5),
            "financial_terms": self.extract_financial_terms(combined_comments),
            "has_financial_content": bool(self.extract_financial_terms(combined_comments))
        })
        result["insight"] = insight
        
        # 详细情感分析(DeepSeek)
        if self.sentiment_analyzer_type == "deepseek" and self.deepseek_api_key:
            # 获取每条评论的情感分析结果
            comment_texts = [comment.get("content", "") if isinstance(comment, dict) else comment for comment in comments]
            detailed_result = self.get_detailed_analysis(comment_texts)
            if detailed_result:
                result["deepseek_analysis"] = detailed_result
                
        return result 