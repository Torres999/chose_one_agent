import re
import logging
from typing import List, Dict, Any, Tuple, Set
from collections import Counter

logger = logging.getLogger(__name__)

class KeywordAnalyzer:
    """
    关键词分析器，用于从文本中提取关键词和术语
    """
    
    def __init__(self, 
                 min_keyword_length: int = 2, 
                 max_keywords: int = 10,
                 custom_keywords: List[str] = None,
                 stopwords: List[str] = None):
        """
        初始化关键词分析器
        
        Args:
            min_keyword_length: 关键词最小长度
            max_keywords: 返回的最大关键词数量
            custom_keywords: 自定义关键词列表
            stopwords: 停用词列表
        """
        self.min_keyword_length = min_keyword_length
        self.max_keywords = max_keywords
        self.custom_keywords = custom_keywords or []
        
        # 默认停用词
        default_stopwords = ['的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', 
                             '一', '一个', '上', '也', '很', '到', '说', '要', '去', '你', '会', 
                             '着', '没有', '看', '好', '自己', '这']
        
        # 合并用户提供的停用词和默认停用词
        self.stopwords = set(stopwords or []) | set(default_stopwords)
        
        # 财经特定术语
        self.financial_terms = [
            '股票', '基金', '债券', '期货', '外汇', '投资', '融资', '分红', '股利', '交易', 
            '市场', '指数', '涨停', '跌停', '牛市', '熊市', '波动', '趋势', '回调', '反弹', 
            '大盘', '个股', '板块', '行业', '业绩', '财报', '营收', '利润', '亏损', '营业额',
            '解禁', '增发', '回购', '配股', '承销', '开盘', '收盘', '高开', '低开', '高走',
            '流通股', '限售股', '总股本', '市值', '市盈率', '市净率', '股息率', '换手率'
        ]
    
    def extract_keywords(self, text: str) -> List[Tuple[str, int]]:
        """
        从文本中提取关键词
        
        Args:
            text: 要分析的文本
            
        Returns:
            关键词列表，每项为(关键词, 出现次数)元组
        """
        if not text or len(text) < self.min_keyword_length:
            return []
        
        # 清理文本
        text = self._clean_text(text)
        
        # 使用正则表达式匹配中文词语（2个或更多连续中文字符）
        words = re.findall(r'[\u4e00-\u9fff]{%d,}' % self.min_keyword_length, text)
        
        # 过滤掉停用词
        filtered_words = [word for word in words if word not in self.stopwords]
        
        # 查找自定义关键词和财经术语
        custom_matches = []
        for keyword in self.custom_keywords + self.financial_terms:
            if keyword in text:
                custom_matches.append(keyword)
        
        # 合并所有词语并计数
        all_words = filtered_words + custom_matches
        word_counts = Counter(all_words).most_common(self.max_keywords)
        
        return word_counts
    
    def analyze_text(self, text: str) -> Dict[str, Any]:
        """
        分析文本并返回关键词分析结果
        
        Args:
            text: 要分析的文本
            
        Returns:
            包含关键词分析结果的字典
        """
        try:
            keywords = self.extract_keywords(text)
            
            result = {
                "keywords": [{"word": word, "count": count} for word, count in keywords],
                "top_keyword": keywords[0][0] if keywords else None,
                "keyword_count": len(keywords)
            }
            
            # 检查是否包含财经术语
            financial_terms_found = []
            for term in self.financial_terms:
                if term in text:
                    financial_terms_found.append(term)
            
            result["financial_terms"] = financial_terms_found
            result["has_financial_content"] = len(financial_terms_found) > 0
            
            return result
            
        except Exception as e:
            logger.error(f"分析文本关键词时出错: {e}")
            return {
                "keywords": [],
                "top_keyword": None,
                "keyword_count": 0,
                "financial_terms": [],
                "has_financial_content": False,
                "error": str(e)
            }
    
    def _clean_text(self, text: str) -> str:
        """
        清理文本，移除标点符号和特殊字符
        
        Args:
            text: 要清理的文本
            
        Returns:
            清理后的文本
        """
        # 移除标点符号和特殊字符
        text = re.sub(r'[^\u4e00-\u9fff\w]', ' ', text)
        # 替换多个空格为单个空格
        text = re.sub(r'\s+', ' ', text)
        return text.strip() 