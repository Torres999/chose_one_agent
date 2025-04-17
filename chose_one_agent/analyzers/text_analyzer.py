# -*- coding: utf-8 -*-
import re
import logging
import traceback
from typing import List, Dict, Any, Optional, Tuple
from collections import Counter

# 简化依赖导入
try:
    import nltk
    from nltk.sentiment import SentimentIntensityAnalyzer
    from nltk.tokenize import word_tokenize
    NLTK_AVAILABLE = True
except ImportError:
    NLTK_AVAILABLE = False

try:
    from snownlp import SnowNLP
    SNOWNLP_AVAILABLE = True
except ImportError:
    SNOWNLP_AVAILABLE = False

# 从constants模块导入常量
from chose_one_agent.utils.constants import SENTIMENT_LABELS, FINANCIAL_TERMS

logger = logging.getLogger(__name__)

class TextAnalyzer:
    """统一的文本分析器，整合情感分析和关键词提取功能"""
    
    def __init__(self, sentiment_analyzer_type: str = "snownlp", 
                 deepseek_api_key: str = None, min_keyword_length: int = 2,
                 max_keywords: int = 10, custom_stopwords: List[str] = None,
                 custom_keywords: List[str] = None, debug: bool = False):
        """初始化分析器
        
        Args:
            sentiment_analyzer_type: 情感分析器类型 ('snownlp', 'deepseek', 'simple')
            deepseek_api_key: DeepSeek API密钥
            min_keyword_length: 关键词最小长度
            max_keywords: 最大关键词数量
            custom_stopwords: 自定义停用词
            custom_keywords: 自定义关键词
            debug: 是否开启调试模式
        """
        self.sentiment_analyzer_type = sentiment_analyzer_type
        self.deepseek_api_key = deepseek_api_key
        self.min_keyword_length = min_keyword_length
        self.max_keywords = max_keywords
        self.custom_stopwords = set(custom_stopwords or [])
        self.custom_keywords = set(custom_keywords or [])
        self.debug = debug
        
        # 初始化情感分析器
        self._init_sentiment_analyzer()
        
        # 初始化停用词
        self._init_stopwords()
    
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
        self.stopwords = set()
        if NLTK_AVAILABLE:
            try:
                nltk.data.find('corpora/stopwords')
            except LookupError:
                nltk.download('stopwords')
            from nltk.corpus import stopwords
            self.stopwords.update(stopwords.words('chinese'))
        self.stopwords.update(self.custom_stopwords)
    
    def analyze_sentiment(self, text: str) -> Dict[str, float]:
        """分析文本情感
        
        Args:
            text: 待分析文本
            
        Returns:
            Dict[str, float]: 情感分析结果
        """
        if not text or text.strip() == "":
            return {"pos": 0.0, "neg": 0.0, "neu": 1.0, "compound": 0.0}
        
        try:
            if self.sentiment_analyzer_type == "deepseek":
                return self.sentiment_analyzer.analyze(text)
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
        except Exception as e:
            logger.error(f"情感分析出错: {e}")
            if self.debug:
                logger.error(traceback.format_exc())
            return {"pos": 0.0, "neg": 0.0, "neu": 1.0, "compound": 0.0}
    
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
    
    def tokenize(self, text: str) -> List[str]:
        """分词
        
        Args:
            text: 待分词文本
            
        Returns:
            List[str]: 分词结果
        """
        if not text or text.strip() == "":
            return []
        
        try:
            if NLTK_AVAILABLE:
                return [word for word in word_tokenize(text) if word.strip()]
            else:
                return [word for word in text.split() if word.strip()]
        except Exception as e:
            logger.error(f"分词出错: {e}")
            if self.debug:
                logger.error(traceback.format_exc())
            return []
    
    def extract_keywords(self, text: str, top_n: int = 5) -> List[str]:
        """提取关键词
        
        Args:
            text: 待分析文本
            top_n: 返回关键词数量
            
        Returns:
            List[str]: 关键词列表
        """
        if not text or text.strip() == "":
            return []
        
        try:
            # 分词
            words = self.tokenize(text)
            
            # 过滤停用词和短词
            words = [word for word in words 
                    if len(word) >= self.min_keyword_length 
                    and word not in self.stopwords]
            
            # 统计词频
            word_freq = Counter(words)
            
            # 返回频率最高的词
            return [word for word, _ in word_freq.most_common(top_n)]
        except Exception as e:
            logger.error(f"提取关键词出错: {e}")
            if self.debug:
                logger.error(traceback.format_exc())
            return []
    
    def extract_financial_terms(self, text: str) -> List[str]:
        """提取财经术语
        
        Args:
            text: 待分析文本
            
        Returns:
            List[str]: 财经术语列表
        """
        if not text or text.strip() == "":
            return []
        
        try:
            words = set(self.tokenize(text))
            return list(words & (FINANCIAL_TERMS | self.custom_keywords))
        except Exception as e:
            logger.error(f"提取财经术语出错: {e}")
            if self.debug:
                logger.error(traceback.format_exc())
            return []
    
    def calculate_financial_relevance(self, text: str) -> float:
        """计算文本与财经相关度
        
        Args:
            text: 待分析文本
            
        Returns:
            float: 财经相关度，范围[0, 1]
        """
        if not text or text.strip() == "":
            return 0.0
        
        try:
            words = set(self.tokenize(text))
            all_terms = FINANCIAL_TERMS | self.custom_keywords
            
            # 计算财经词汇占比
            financial_words = words & all_terms
            if not words:
                return 0.0
                
            return len(financial_words) / len(words)
        except Exception as e:
            logger.error(f"计算财经相关度出错: {e}")
            if self.debug:
                logger.error(traceback.format_exc())
            return 0.0
    
    def analyze_text(self, text: str) -> Dict[str, Any]:
        """全面分析文本，包括情感、关键词和财经相关度
        
        Args:
            text: 待分析文本
            
        Returns:
            Dict[str, Any]: 分析结果
        """
        if not text or text.strip() == "":
            return {
                "sentiment": {"pos": 0.0, "neg": 0.0, "neu": 1.0, "compound": 0.0},
                "sentiment_label": "中性",
                "keywords": [],
                "financial_terms": [],
                "has_financial_content": False,
                "financial_relevance": 0.0
            }
        
        try:
            # 情感分析
            sentiment = self.analyze_sentiment(text)
            sentiment_label = self.get_sentiment_label(sentiment.get("compound", 0))
            
            # 关键词提取
            keywords = self.extract_keywords(text)
            
            # 财经相关分析
            financial_terms = self.extract_financial_terms(text)
            financial_relevance = self.calculate_financial_relevance(text)
            
            return {
                "sentiment": sentiment,
                "sentiment_label": sentiment_label,
                "keywords": keywords,
                "financial_terms": financial_terms,
                "has_financial_content": bool(financial_terms),
                "financial_relevance": financial_relevance
            }
        except Exception as e:
            logger.error(f"分析文本出错: {e}")
            if self.debug:
                logger.error(traceback.format_exc())
            return {
                "sentiment": {"pos": 0.0, "neg": 0.0, "neu": 1.0, "compound": 0.0},
                "sentiment_label": "中性",
                "keywords": [],
                "financial_terms": [],
                "has_financial_content": False,
                "financial_relevance": 0.0,
                "error": str(e)
            }
    
    def _combine_sentiment_scores(self, scores: List[Dict[str, float]]) -> Dict[str, float]:
        """合并多个情感分析结果
        
        Args:
            scores: 情感分析结果列表
            
        Returns:
            Dict[str, float]: 合并后的情感分析
        """
        if not scores:
            return {"pos": 0.0, "neg": 0.0, "neu": 1.0, "compound": 0.0}
        
        # 计算加权平均
        total_pos = sum(score.get("pos", 0) for score in scores)
        total_neg = sum(score.get("neg", 0) for score in scores)
        total_neu = sum(score.get("neu", 0) for score in scores)
        total_compound = sum(score.get("compound", 0) for score in scores)
        
        count = len(scores)
        return {
            "pos": total_pos / count,
            "neg": total_neg / count,
            "neu": total_neu / count,
            "compound": total_compound / count
        }
    
    def get_detailed_analysis(self, comments: List[str]) -> Dict[str, Any]:
        """获取评论的详细情感分析
        
        Args:
            comments: 评论列表
            
        Returns:
            Dict[str, Any]: 详细分析结果
        """
        # 提供详细的情感分析（DeepSeek专用，其他分析器默认返回空）
        if self.sentiment_analyzer_type != "deepseek" or not self.deepseek_api_key:
            return {}
        
        try:
            return self.sentiment_analyzer.analyze_batch(comments[:10])
        except Exception as e:
            logger.error(f"获取详细分析出错: {e}")
            if self.debug:
                logger.error(traceback.format_exc())
            return {}
    
    def generate_insight(self, analysis_result: Dict[str, Any]) -> str:
        """根据分析结果生成洞察
        
        Args:
            analysis_result: 分析结果
            
        Returns:
            str: 洞察内容
        """
        if not analysis_result:
            return "暂无洞察"
            
        try:
            title = analysis_result.get("title", "未知标题")
            sentiment_label = analysis_result.get("sentiment_label", "中性")
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
        except Exception as e:
            logger.error(f"生成洞察出错: {e}")
            if self.debug:
                logger.error(traceback.format_exc())
            return "无法生成洞察" 