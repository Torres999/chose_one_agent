"""
提取和格式化工具，处理各种文本格式化和数据处理功能
"""
import re
import logging
from typing import Dict, Any, Optional, Union, List

from chose_one_agent.utils.logging_utils import get_logger

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
        sentiment: 情感信息，包括评论数量
        section: 所属板块（可选）
        deepseek_analysis: 参数保留但不再使用
        
    Returns:
        格式化的输出字符串
    """
    output = "标题：{0}\n日期：{1}\n时间：{2}".format(title, date, time)
    output += "\n所属板块：{0}".format(section)
    
    # 显示评论数量字段
    comment_count = 0
    if isinstance(sentiment, dict):
        comment_count = sentiment.get("comment_count", 0)
    
    output += "\n评论数量：{0}".format(comment_count)
    
    # 添加新字段，不设置默认值
    output += "\n评论情绪："
    output += "\n情感分布："
    output += "\n关键评论："
    
    # 添加分隔线
    output += "\n--------------------------------------------------"
    
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

def analyze_post_content(post_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    分析帖子内容，提取基础信息
    
    Args:
        post_data: 帖子数据，包含标题和内容
        
    Returns:
        分析结果字典
    """
    date = post_data.get("date", "")
    time = post_data.get("time", "")
    
    # 返回基础信息
    return {
        "post_date": date,
        "post_time": time
    } 