"""
提取和格式化工具，处理各种文本格式化和数据处理功能
"""
import re
import logging
from typing import Dict, Any, Optional, Union, List

from chose_one_agent.utils.logging_utils import get_logger
from chose_one_agent.utils.constants import SENTIMENT_SCORE_LABELS

# 获取日志记录器
logger = get_logger(__name__)

def format_output(title: str, date: str, time: str, sentiment: Optional[Union[str, int, Dict[str, Any]]] = None, 
               section: str = "未知板块", deepseek_analysis: Optional[Dict[str, Any]] = None) -> str:
    """
    格式化输出结果
    
    Args:
        title: 电报标题
        date: 电报日期
        time: 电报时间
        sentiment: 评论情绪（可选），可以是字符串、0-5的数字评分或包含情感分析信息的字典
        section: 所属板块（可选）
        deepseek_analysis: Deepseek情感分析的详细结果（可选）
        
    Returns:
        格式化的输出字符串
    """
    output = f"标题：{title}\n日期：{date}\n时间：{time}"
    
    # 处理情感分析结果
    if isinstance(sentiment, dict):
        sentiment_label = sentiment.get("sentiment_label", "无评论")
        has_comments = sentiment.get("has_comments", False)
        comments = sentiment.get("comments", [])
        sentiment_analysis = sentiment.get("sentiment_analysis", "")
        
        output += f"\n评论情绪：{sentiment_label}"
        output += f"\n所属板块：{section}"
        
        # 只有在有评论且有情感分析结果时，才添加详细分析
        if has_comments and comments and sentiment_analysis and sentiment_label != "无评论":
            # 格式化情感分析结果
            for pattern in ["整体评论情感", "情感评分", "情感分布", "关键词", "市场情绪"]:
                sentiment_analysis = sentiment_analysis.replace(f"- {pattern}:", f"\n- {pattern}:")
                
            # 移除开头可能的多余换行
            sentiment_analysis = sentiment_analysis.lstrip("\n")
            output += f"\n\n{sentiment_analysis}"
    elif isinstance(sentiment, (int, float)):
        # 评分作为整数，转换为情感描述
        output += f"\n评论情绪：{SENTIMENT_SCORE_LABELS.get(sentiment, f'未知({sentiment})')}"
        output += f"\n所属板块：{section}"
    else:
        # 处理旧格式的字符串情感
        output += f"\n评论情绪：{sentiment or '无评论'}"
        output += f"\n所属板块：{section}"
    
    # 如果有DeepSeek的分析结果
    if deepseek_analysis:
        sentiment_label = deepseek_analysis.get("label", "中性")
        sentiment_score = deepseek_analysis.get("score", 3)
        output += f"\n\nDeepSeek情感分析：{sentiment_label} (得分: {sentiment_score}/5)"
    
    return output

def extract_post_content(html_content: str) -> str:
    """
    从HTML内容中提取帖子正文
    
    Args:
        html_content: 帖子HTML内容
        
    Returns:
        提取的帖子正文
    """
    # 移除HTML标签
    content = re.sub(r'<[^>]+>', ' ', html_content)
    # 移除多余空白
    content = re.sub(r'\s+', ' ', content).strip()
    return content

def extract_financial_terms(text: str, terms_set: set) -> List[str]:
    """
    从文本中提取财经术语
    
    Args:
        text: 要分析的文本
        terms_set: 财经术语集合
        
    Returns:
        提取到的财经术语列表
    """
    if not text or not terms_set:
        return []
    
    try:
        # 简单匹配每个术语是否出现在文本中
        found_terms = [term for term in terms_set if term in text]
        return found_terms
    except Exception as e:
        logger.error(f"提取财经术语出错: {e}")
        return []

def clean_text(text: str) -> str:
    """
    清理文本，去除多余空白和特殊字符
    
    Args:
        text: 原始文本
        
    Returns:
        清理后的文本
    """
    if not text:
        return ""
    
    # 移除HTML标签
    text = re.sub(r'<[^>]+>', '', text)
    # 替换换行符
    text = re.sub(r'\n+', ' ', text)
    # 移除连续空白
    text = re.sub(r'\s+', ' ', text)
    # 移除首尾空白
    return text.strip() 