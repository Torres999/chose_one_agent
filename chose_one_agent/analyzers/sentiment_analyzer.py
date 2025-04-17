"""
分析器类集合
"""
from typing import List, Set, Dict, Any
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

from chose_one_agent.utils.constants import FINANCIAL_TERMS

class BaseAnalyzer:
    """
    分析器基类，所有分析器继承自此类
    """
    
    def __init__(self, debug: bool = False):
        """
        初始化分析器
        
        Args:
            debug: 是否启用调试模式
        """
        self.debug = debug
    
    def analyze(self, text: str) -> dict:
        """
        分析文本
        
        Args:
            text: 待分析文本
            
        Returns:
            dict: 分析结果
        """
        # 基类方法，子类应当重写
        raise NotImplementedError("子类必须实现此方法")

class KeywordAnalyzer(BaseAnalyzer):
    """
    关键词分析器类，用于提取文本中的关键词
    """
    
    def __init__(self, min_length: int = 2, max_keywords: int = 10, 
                 custom_stopwords: List[str] = None, debug: bool = False):
        """
        初始化关键词分析器
        
        Args:
            min_length: 关键词最小长度
            max_keywords: 最大关键词数量
            custom_stopwords: 自定义停用词
            debug: 是否启用调试模式
        """
        super().__init__(debug)
        self.min_length = min_length
        self.max_keywords = max_keywords
        self.custom_stopwords = set(custom_stopwords or [])
        self.stopwords = self._init_stopwords()
        
    def _init_stopwords(self) -> Set[str]:
        """初始化停用词"""
        stopwords = set()
        if NLTK_AVAILABLE:
            try:
                nltk.data.find('corpora/stopwords')
                from nltk.corpus import stopwords as nltk_stopwords
                stopwords.update(nltk_stopwords.words('chinese'))
            except (ImportError, LookupError):
                pass
        stopwords.update(self.custom_stopwords)
        return stopwords
    
    def analyze(self, text: str) -> dict:
        """
        分析文本提取关键词
        
        Args:
            text: 待分析文本
            
        Returns:
            dict: 关键词分析结果
        """
        keywords = self.extract_keywords(text)
        financial_terms = self.extract_financial_terms(text)
        relevance = self.calculate_financial_relevance(text)
        
        return {
            "keywords": keywords,
            "financial_terms": financial_terms,
            "financial_relevance": relevance
        }
    
    def extract_keywords(self, text: str) -> List[str]:
        """
        提取关键词
        
        Args:
            text: 待分析文本
            
        Returns:
            List[str]: 关键词列表
        """
        if not text or text.strip() == "":
            return []
        
        # 分词
        words = self._tokenize(text)
        
        # 过滤停用词和短词
        words = [word for word in words 
                if len(word) >= self.min_length 
                and word not in self.stopwords]
        
        # 统计词频
        word_freq = Counter(words)
        
        # 返回频率最高的词
        return [word for word, _ in word_freq.most_common(self.max_keywords)]
    
    def _tokenize(self, text: str) -> List[str]:
        """
        分词
        
        Args:
            text: 待分词文本
            
        Returns:
            List[str]: 分词结果
        """
        if NLTK_AVAILABLE:
            try:
                from nltk.tokenize import word_tokenize
                return word_tokenize(text)
            except ImportError:
                pass
        return text.split()
    
    def extract_financial_terms(self, text: str) -> List[str]:
        """
        提取财经术语
        
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
        """
        计算财经相关度
        
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

class SentimentAnalyzer(BaseAnalyzer):
    """
    情感分析器类，用于分析文本的情感倾向
    """
    
    def __init__(self, analyzer_type: str = "snownlp", api_key: str = None, debug: bool = False):
        """
        初始化情感分析器
        
        Args:
            analyzer_type: 分析器类型，'snownlp'或'deepseek'
            api_key: API密钥，仅在使用deepseek时需要
            debug: 是否启用调试模式
        """
        super().__init__(debug)
        self.analyzer_type = analyzer_type
        self.api_key = api_key
        
        if analyzer_type == "deepseek" and api_key:
            try:
                from chose_one_agent.analyzers.deepseek_sentiment_analyzer import DeepSeekSentimentAnalyzer
                self.analyzer = DeepSeekSentimentAnalyzer(api_key)
            except ImportError:
                self.analyzer_type = "snownlp"
                self._init_snownlp()
        else:
            self._init_snownlp()
    
    def _init_snownlp(self):
        """初始化SnowNLP分析器"""
        if SNOWNLP_AVAILABLE:
            self.analyzer = SnowNLP
        else:
            self.analyzer_type = "simple"
    
    def analyze(self, text: str) -> dict:
        """
        分析文本情感
        
        Args:
            text: 待分析文本
            
        Returns:
            dict: 情感分析结果
        """
        if not text or text.strip() == "":
            return {"pos": 0.0, "neg": 0.0, "neu": 1.0, "compound": 0.0}
        
        if self.analyzer_type == "deepseek":
            return self.analyzer.analyze(text)
        elif self.analyzer_type == "snownlp":
            s = self.analyzer(text)
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