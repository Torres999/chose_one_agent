"""
电报分析器，用于分析电报内容
"""
import datetime
import logging
import re
import time
from typing import List, Dict, Any, Optional, Tuple

try:
    from snownlp import SnowNLP
    SNOWNLP_AVAILABLE = True
except ImportError:
    SNOWNLP_AVAILABLE = False

from chose_one_agent.utils.datetime_utils import convert_relative_time
from chose_one_agent.utils.constants import FINANCIAL_TERMS
from chose_one_agent.utils.logging_utils import get_logger
from chose_one_agent.utils.extraction import extract_financial_terms, clean_text

# 设置日志
logger = get_logger(__name__)

class TelegraphAnalyzer:
    """电报分析器类，用于分析财联社电报内容"""
    
    def __init__(self, debug: bool = False):
        """
        初始化电报分析器
        
        Args:
            debug: 是否启用调试模式
        """
        self.debug = debug
    
    def analyze_post_content(self, post_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        分析帖子内容
        
        Args:
            post_data: 帖子数据，包含标题和内容
            
        Returns:
            分析结果字典
        """
        title = post_data.get("title", "")
        content = post_data.get("content", "")
        date = post_data.get("date", "")
        time = post_data.get("time", "")
        
        # 清理文本
        text = clean_text(title + " " + content)
        
        # 提取财经术语
        financial_terms = extract_financial_terms(text, FINANCIAL_TERMS)
        
        # 计算财经相关度
        if len(financial_terms) > 0:
            financial_relevance = min(1.0, len(financial_terms) / 5)
        else:
            financial_relevance = 0.0
        
        # 返回基础分析结果
        return {
            "financial_terms": financial_terms,
            "financial_relevance": financial_relevance,
            "post_date": date,
            "post_time": time
        }
    
    def _combine_comments(self, comments: List[Dict[str, Any]]) -> str:
        """
        合并评论文本
        
        Args:
            comments: 评论列表
            
        Returns:
            合并后的评论文本
        """
        comment_texts = []
        for comment in comments:
            text = comment.get("content", "").strip()
            if text:
                comment_texts.append(text)
        return " ".join(comment_texts)
    
    def analyze_insights(self, post_data: Dict[str, Any], comments: List[Dict[str, Any]] = None) -> str:
        """
        分析帖子和评论，生成洞察
        
        Args:
            post_data: 帖子数据
            comments: 评论数据
            
        Returns:
            洞察文本
        """
        if not post_data:
            return ""
            
        title = post_data.get("title", "")
        content = post_data.get("content", "")
        
        # 提取财经术语
        text = clean_text(title + " " + content)
        financial_terms = extract_financial_terms(text, FINANCIAL_TERMS)
        
        # 如果没有评论或财经术语，返回空洞察
        if (not comments or len(comments) == 0) and len(financial_terms) == 0:
            return ""
            
        # 基础洞察
        insights = []
        
        # 添加财经术语相关洞察
        if financial_terms:
            top_terms = financial_terms[:5]  # 最多显示5个术语
            insights.append(f"关键词: {', '.join(top_terms)}")
        
        return "\n".join(insights)
    
    def analyze_post_data(self, post_data: Dict[str, Any], comments: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        分析帖子数据和评论
        
        Args:
            post_data: 帖子数据
            comments: 评论数据
            
        Returns:
            分析结果
        """
        # 基础结构
        result = {
            "insight": ""
        }
        
        # 如果没有评论，返回基础结果
        if not comments or len(comments) == 0:
            return result
            
        # 生成洞察
        insight = self.analyze_insights(post_data, comments)
        result["insight"] = insight
            
        return result 