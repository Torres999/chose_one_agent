import datetime
import logging
import os
import re
from typing import Tuple, Optional, Union, Dict, Any

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def parse_datetime(date_str: str, time_str: str) -> datetime.datetime:
    """
    将日期和时间字符串解析为datetime对象
    
    Args:
        date_str: 日期字符串，如"2023-05-20"或"05-20"或"2025.04.11"
        time_str: 时间字符串，如"14:30"
        
    Returns:
        datetime对象
    """
    try:
        # 处理空字符串情况
        if not date_str or not time_str:
            logger.warning(f"日期或时间为空: date='{date_str}', time='{time_str}'")
            raise ValueError("日期或时间字符串为空")
        
        # 预处理日期格式
        if len(date_str.split('-')) == 2:  # 只有月份和日期 (如 "05-20")
            current_year = datetime.datetime.now().year
            date_str = f"{current_year}-{date_str}"
        elif re.match(r'^\d{4}\.\d{2}\.\d{2}$', date_str):  # YYYY.MM.DD格式
            date_str = date_str.replace('.', '-')
        
        # 预处理时间格式
        if any(prefix in time_str for prefix in ["上午", "下午", "凌晨", "中午", "晚上"]):
            time_match = re.search(r'(\d+:\d+)', time_str)
            if time_match:
                time_str = time_match.group(1)
            else:
                logger.warning(f"无法从'{time_str}'中提取时间")
                raise ValueError(f"无法从'{time_str}'中提取时间")
        
        # 处理只有小时没有分钟的情况
        if re.match(r'^\d+$', time_str):
            time_str = f"{time_str}:00"
        
        # 合并日期和时间
        datetime_str = f"{date_str} {time_str}"
        
        # 定义支持的日期时间格式
        formats = [
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d %H:%M:%S",
            "%Y/%m/%d %H:%M",
            "%Y年%m月%d日 %H:%M",
            "%m-%d %H:%M",
            "%Y.%m.%d %H:%M",
            "%Y.%m.%d %H:%M:%S"
        ]
        
        # 尝试解析完整的日期时间字符串
        for fmt in formats:
            try:
                return datetime.datetime.strptime(datetime_str, fmt)
            except ValueError:
                continue
        
        # 如果所有格式都失败，尝试只解析日期部分
        logger.warning(f"无法解析完整日期时间: '{datetime_str}'，尝试仅解析日期")
        basic_formats = ["%Y-%m-%d", "%Y.%m.%d", "%Y/%m/%d"]
        for fmt in basic_formats:
            try:
                return datetime.datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        
        # 所有尝试均失败
        logger.error(f"无法解析日期: '{date_str}'")
        raise ValueError(f"无法解析日期: '{date_str}'")
    
    except Exception as e:
        logger.error(f"日期时间解析错误: {e}, date='{date_str}', time='{time_str}'")
        raise ValueError(f"日期时间解析错误: {e}")

def is_before_cutoff(post_date: datetime.datetime, cutoff_date: datetime.datetime) -> bool:
    """
    检查帖子日期是否早于截止日期
    
    Args:
        post_date: 帖子的日期时间
        cutoff_date: 截止日期时间
        
    Returns:
        如果帖子日期早于截止日期则返回True，否则返回False
    """
    return post_date < cutoff_date

def is_in_date_range(post_date: datetime.datetime, cutoff_date: datetime.datetime) -> bool:
    """
    检查帖子日期是否在截止日期之后
    
    Args:
        post_date: 帖子的日期时间
        cutoff_date: 截止日期时间
        
    Returns:
        如果帖子日期大于等于截止日期则返回True，否则返回False
    """
    # 不管截止日期是过去还是未来，只要帖子日期大于等于截止日期就符合条件
    return post_date >= cutoff_date

def extract_date_time(date_time_text: str) -> Tuple[str, str]:
    """
    从日期时间文本中提取日期和时间
    
    Args:
        date_time_text: 日期时间文本，如"2023-05-20 14:30"
        
    Returns:
        (日期字符串, 时间字符串)的元组
    """
    try:
        # 检查输入是否为空
        if not date_time_text or date_time_text.strip() == "":
            logger.warning("日期时间文本为空")
            return "", ""
        
        # 尝试多种分隔模式提取日期和时间
        
        # 1. 标准格式: "YYYY-MM-DD HH:MM"
        match = re.search(r'(\d{4}-\d{1,2}-\d{1,2})\s+(\d{1,2}:\d{1,2})', date_time_text)
        if match:
            return match.group(1), match.group(2)
        
        # 2. 只有时间没有日期: "HH:MM"
        match = re.search(r'(\d{1,2}:\d{1,2})', date_time_text)
        if match:
            today = datetime.datetime.now().strftime("%Y-%m-%d")
            return today, match.group(1)
        
        # 3. 其他格式
        parts = date_time_text.strip().split(' ')
        if len(parts) >= 2:
            date_str = parts[0].strip()
            time_str = parts[1].strip()
            
            # 检查日期部分是否包含日期信息
            if not re.search(r'\d{1,2}[-/]\d{1,2}|\d{4}[-/]\d{1,2}', date_str):
                logger.warning(f"无法从'{date_str}'识别日期格式")
                date_str = datetime.datetime.now().strftime("%Y-%m-%d")
                
            # 检查时间部分是否包含时间信息
            if not re.search(r'\d{1,2}:\d{1,2}', time_str):
                logger.warning(f"无法从'{time_str}'识别时间格式")
                time_str = "00:00"
                
            return date_str, time_str
        else:
            # 如果只有一部分，检查是否是日期或时间
            text = parts[0]
            if re.search(r'\d{1,2}:\d{1,2}', text):
                # 这是一个时间
                today = datetime.datetime.now().strftime("%Y-%m-%d")
                return today, text
            elif re.search(r'\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}', text):
                # 这是一个日期
                return text, "00:00"
                
            logger.warning(f"无法从'{date_time_text}'提取日期和时间")
            return "", ""
            
    except Exception as e:
        logger.error(f"提取日期时间错误: {e}, text='{date_time_text}'")
        return "", ""

def format_output(title: str, date: str, time: str, sentiment: Optional[Union[str, int, Dict[str, Any]]] = None, section: str = "未知板块", 
               deepseek_analysis: Optional[Dict[str, Any]] = None) -> str:
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
        # 新版API返回的是字典
        sentiment_score = sentiment.get("sentiment_score", 0)
        sentiment_label = sentiment.get("sentiment_label", "无评论")
        has_comments = sentiment.get("has_comments", False)
        comments = sentiment.get("comments", [])
        sentiment_analysis = sentiment.get("sentiment_analysis", "")
        
        output += f"\n评论情绪：{sentiment_label}"
        output += f"\n所属板块：{section}"
        
        # 只有在有评论并且使用了DeepSeek分析时，才添加详细分析结果
        if has_comments and comments and len(comments) > 0 and sentiment_analysis and sentiment_label != "无评论":
            # 直接添加详细的情感分析结果
            output += f"\n\n{sentiment_analysis}"
    elif sentiment is not None:
        # 如果是数字评分，转换为文字描述
        if isinstance(sentiment, int):
            sentiment_mapping = {
                0: "无评论",
                1: "极度消极",
                2: "消极",
                3: "中性",
                4: "积极",
                5: "极度积极"
            }
            sentiment_text = sentiment_mapping.get(sentiment, "无评论")
            output += f"\n评论情绪：{sentiment_text}"
        else:
            output += f"\n评论情绪：{sentiment}"
        
        output += f"\n所属板块：{section}"
        
        # 只有在评论情绪不是"无评论"时，才显示DeepSeek分析
        if sentiment != 0 and sentiment_text != "无评论" and deepseek_analysis and isinstance(deepseek_analysis, dict):
            # 如果有情感分数
            if "score" in deepseek_analysis:
                score = deepseek_analysis["score"]
                output += f"\nDeepseek情感分析：{sentiment_text} (得分: {score:.2f})"
            
            # 如果有情感分布
            if "distribution" in deepseek_analysis:
                distribution = deepseek_analysis["distribution"]
                pos = distribution.get("正面", 0) * 100
                neu = distribution.get("中性", 0) * 100
                neg = distribution.get("负面", 0) * 100
                output += f"\n情感分布：正面 {pos:.1f}% | 中性 {neu:.1f}% | 负面 {neg:.1f}%"
            
            # 如果有情感关键词
            if "keywords" in deepseek_analysis and deepseek_analysis["keywords"]:
                keywords = ", ".join(deepseek_analysis["keywords"])
                output += f"\n情感关键词：{keywords}"
            
            # 如果有分析内容
            if "analysis" in deepseek_analysis and deepseek_analysis["analysis"]:
                output += f"\n分析：{deepseek_analysis['analysis']}"
            
            # 如果有市场情绪
            if "market_sentiment" in deepseek_analysis:
                output += f"\n市场情绪：{deepseek_analysis['market_sentiment']}"
            
            # 如果有主要观点
            if "main_points" in deepseek_analysis:
                output += f"\n主要观点：{deepseek_analysis['main_points']}"
            
            # 如果有相关股票
            if "related_stocks" in deepseek_analysis and deepseek_analysis["related_stocks"]:
                stocks = ", ".join([f"{stock}({view})" for stock, view in deepseek_analysis["related_stocks"].items()])
                output += f"\n相关股票：{stocks}"
            
            # 如果有建议
            if "suggestion" in deepseek_analysis:
                output += f"\n建议：{deepseek_analysis['suggestion']}"
    else:
        output += f"\n所属板块：{section}"
    
    return output 