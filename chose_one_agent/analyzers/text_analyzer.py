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

logger = logging.getLogger(__name__)

# 情感标签定义
SENTIMENT_LABELS = {
    "极度积极": (0.8, 1.0),
    "积极": (0.3, 0.8),
    "中性": (-0.3, 0.3),
    "消极": (-0.8, -0.3),
    "极度消极": (-1.0, -0.8)
}

# 财经术语列表
FINANCIAL_TERMS = {
    "股票", "市场", "投资", "基金", "证券", "期货", "期权", "债券", "外汇",
    "黄金", "原油", "指数", "大盘", "个股", "板块", "概念", "题材", "主力",
    "机构", "散户", "游资", "庄家", "筹码", "仓位", "建仓", "加仓", "减仓",
    "清仓", "止损", "止盈", "套利", "套现", "解套", "补仓", "抄底", "逃顶",
    "涨停", "跌停", "高开", "低开", "平开", "高走", "低走", "震荡", "盘整",
    "突破", "回调", "反弹", "反转", "趋势", "支撑", "压力", "均线", "K线",
    "成交量", "换手率", "市盈率", "市净率", "ROE", "EPS", "净利润", "营收",
    "毛利率", "净利率", "负债率", "现金流", "分红", "送转", "增发", "减持",
    "回购", "并购", "重组", "借壳", "退市", "ST", "*ST", "摘帽", "戴帽"
}

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
            float: 相关度得分 (0-1)
        """
        if not text or text.strip() == "":
            return 0.0
        
        try:
            words = set(self.tokenize(text))
            financial_terms = words & (FINANCIAL_TERMS | self.custom_keywords)
            return len(financial_terms) / len(words) if words else 0.0
        except Exception as e:
            logger.error(f"计算财经相关度出错: {e}")
            if self.debug:
                logger.error(traceback.format_exc())
            return 0.0
    
    def analyze_text(self, text: str) -> Dict[str, Any]:
        """分析文本
        
        Args:
            text: 待分析文本
            
        Returns:
            Dict[str, Any]: 分析结果
        """
        if not text or text.strip() == "":
            return {
                "keywords": [],
                "financial_terms": [],
                "has_financial_content": False,
                "financial_relevance": 0.0
            }
        
        try:
            # 提取关键词
            keywords = self.extract_keywords(text, self.max_keywords)
            
            # 提取财经术语
            financial_terms = self.extract_financial_terms(text)
            
            # 计算财经相关度
            financial_relevance = self.calculate_financial_relevance(text)
            
            return {
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
                "keywords": [],
                "financial_terms": [],
                "has_financial_content": False,
                "financial_relevance": 0.0
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
        
        total = len(scores)
        combined = {
            "pos": sum(score.get("pos", 0.0) for score in scores) / total,
            "neg": sum(score.get("neg", 0.0) for score in scores) / total,
            "neu": sum(score.get("neu", 0.0) for score in scores) / total,
            "compound": sum(score.get("compound", 0.0) for score in scores) / total
        }
        
        # 归一化
        total = sum(combined.values())
        if total > 0:
            for key in combined:
                combined[key] /= total
                
        return combined
    
    def get_detailed_analysis(self, comments: List[str]) -> Dict[str, Any]:
        """获取详细情感分析（DeepSeek专用）
        
        Args:
            comments: 评论列表
            
        Returns:
            Dict[str, Any]: 详细分析结果
        """
        if self.sentiment_analyzer_type != "deepseek" or not self.deepseek_api_key:
            return {}
            
        try:
            return self.sentiment_analyzer.get_detailed_analysis(comments)
        except Exception as e:
            logger.error(f"获取详细分析出错: {e}")
            if self.debug:
                logger.error(traceback.format_exc())
            return {}
    
    def generate_insight(self, analysis_result: Dict[str, Any]) -> str:
        """生成分析洞察
        
        Args:
            analysis_result: 分析结果
            
        Returns:
            str: 分析洞察
        """
        try:
            title = analysis_result.get("title", "未知标题")
            sentiment_label = analysis_result.get("sentiment_label", "未知")
            keywords = analysis_result.get("keywords", [])
            financial_terms = analysis_result.get("financial_terms", [])
            
            insight = f"标题《{title}》的情感倾向为{sentiment_label}。"
            
            if keywords:
                insight += f" 主要关键词包括：{', '.join(keywords[:3])}。"
                
            if financial_terms:
                insight += f" 涉及财经术语：{', '.join(financial_terms[:3])}。"
                
            return insight
        except Exception as e:
            logger.error(f"生成洞察出错: {e}")
            if self.debug:
                logger.error(traceback.format_exc())
            return ""


# 从 analyzer.py 中合并 TelegraphAnalyzer 类
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