"""
日期时间处理工具，提供统一的日期时间处理函数
"""
import datetime
import re
import logging
from typing import Tuple, Optional

from chose_one_agent.utils.logging_utils import get_logger
from chose_one_agent.utils.constants import DATETIME_FORMATS, DEFAULT_CUTOFF_DAYS

# 获取日志记录器
logger = get_logger(__name__)

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
        if not date_str or not time_str:
            raise ValueError("日期或时间字符串为空")
        
        # 预处理日期格式
        if len(date_str.split('-')) == 2:  # 只有月份和日期 (如 "05-20")
            date_str = f"{datetime.datetime.now().year}-{date_str}"
        elif re.match(r'^\d{4}\.\d{2}\.\d{2}$', date_str):  # YYYY.MM.DD格式
            date_str = date_str.replace('.', '-')
        
        # 预处理时间格式
        if any(prefix in time_str for prefix in ["上午", "下午", "凌晨", "中午", "晚上"]):
            time_match = re.search(r'(\d+:\d+)', time_str)
            if time_match:
                time_str = time_match.group(1)
            else:
                raise ValueError(f"无法从'{time_str}'中提取时间")
        
        # 处理只有小时没有分钟的情况
        if re.match(r'^\d+$', time_str):
            time_str = f"{time_str}:00"
        
        # 合并日期和时间
        datetime_str = f"{date_str} {time_str}"
        
        # 尝试解析各种格式
        formats = [
            DATETIME_FORMATS["standard"],
            DATETIME_FORMATS["standard_with_seconds"],
            DATETIME_FORMATS["slash_date"],
            DATETIME_FORMATS["chinese_date"],
            DATETIME_FORMATS["dot_date"],
            DATETIME_FORMATS["dot_date_with_seconds"]
        ]
        
        for fmt in formats:
            try:
                return datetime.datetime.strptime(datetime_str, fmt)
            except ValueError:
                continue
        
        raise ValueError(f"无法解析日期时间: '{datetime_str}'")
    
    except Exception as e:
        logger.error(f"日期时间解析错误: {e}")
        raise ValueError(f"日期时间解析错误: {e}")

def extract_date_time(date_time_text: str) -> Tuple[str, str]:
    """
    从日期时间文本中提取日期和时间
    
    Args:
        date_time_text: 日期时间文本，如"2023-05-20 14:30"
        
    Returns:
        (日期字符串, 时间字符串)的元组
    """
    try:
        if not date_time_text or date_time_text.strip() == "":
            return "", ""
        
        # 标准格式: "YYYY-MM-DD HH:MM"
        match = re.search(r'(\d{4}-\d{1,2}-\d{1,2})\s+(\d{1,2}:\d{1,2})', date_time_text)
        if match:
            return match.group(1), match.group(2)
        
        # 只有时间没有日期: "HH:MM"
        match = re.search(r'(\d{1,2}:\d{1,2})', date_time_text)
        if match:
            return datetime.datetime.now().strftime(DATETIME_FORMATS["date_only"]), match.group(1)
        
        # 其他格式
        parts = date_time_text.strip().split(' ')
        if len(parts) >= 2:
            date_str = parts[0].strip()
            time_str = parts[1].strip()
            
            # 检查日期和时间格式
            if not re.search(r'\d{1,2}[-/]\d{1,2}|\d{4}[-/]\d{1,2}', date_str):
                date_str = datetime.datetime.now().strftime(DATETIME_FORMATS["date_only"])
                
            if not re.search(r'\d{1,2}:\d{1,2}', time_str):
                time_str = "00:00"
                
            return date_str, time_str
        
        # 如果只有一部分，检查是否是日期或时间
        text = parts[0]
        if re.search(r'\d{1,2}:\d{1,2}', text):
            return datetime.datetime.now().strftime(DATETIME_FORMATS["date_only"]), text
        elif re.search(r'\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}', text):
            return text, "00:00"
            
        return "", ""
            
    except Exception as e:
        logger.error(f"提取日期时间错误: {e}")
        return "", ""

def parse_cutoff_date(cutoff_date_str: Optional[str] = None) -> datetime.datetime:
    """
    解析截止日期字符串
    
    Args:
        cutoff_date_str: 截止日期时间字符串，格式为'YYYY-MM-DD HH:MM'或'YYYY-MM-DD HH:MM:SS'
        
    Returns:
        datetime对象
        
    Raises:
        ValueError: 如果截止日期格式无效或解析失败
    """
    if not cutoff_date_str:
        raise ValueError("必须提供截止日期参数")
    
    # 尝试多种格式解析
    formats = [
        DATETIME_FORMATS["standard"],                # YYYY-MM-DD HH:MM
        DATETIME_FORMATS.get("standard_with_seconds", "%Y-%m-%d %H:%M:%S")  # YYYY-MM-DD HH:MM:SS
    ]
    
    for fmt in formats:
        try:
            return datetime.datetime.strptime(cutoff_date_str, fmt)
        except ValueError:
            continue
    
    # 如果所有格式都失败，抛出异常
    raise ValueError(f"无效的截止日期格式: {cutoff_date_str}，应为'YYYY-MM-DD HH:MM'或'YYYY-MM-DD HH:MM:SS'")

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
    return post_date >= cutoff_date

def is_time_after_cutoff(post_time: str, cutoff_time: str) -> bool:
    """
    检查帖子时间是否晚于截止时间
    
    Args:
        post_time: 帖子时间字符串，格式为"HH:MM"或"HH:MM:SS"
        cutoff_time: 截止时间字符串，格式为"HH:MM"或"HH:MM:SS"
        
    Returns:
        如果帖子时间晚于或等于截止时间则返回True，否则返回False
    """
    try:
        # 确保时间格式统一
        if post_time.count(':') == 1:
            post_time += ':00'
        if cutoff_time.count(':') == 1:
            cutoff_time += ':00'
            
        post_parts = list(map(int, post_time.split(':')))
        cutoff_parts = list(map(int, cutoff_time.split(':')))
        
        # 比较时间 (小时、分钟、秒)
        for i in range(len(post_parts)):
            if post_parts[i] > cutoff_parts[i]:
                return True
            elif post_parts[i] < cutoff_parts[i]:
                return False
                
        return True  # 时间相等
        
    except Exception as e:
        logger.error(f"时间比较出错: {e}")
        return True  # 出错时默认接受帖子

def format_date(dt: datetime.datetime, format_str: str = None) -> str:
    """
    格式化日期
    
    Args:
        dt: 日期时间对象
        format_str: 格式字符串，默认使用标准日期格式
        
    Returns:
        格式化后的日期字符串
    """
    if format_str is None:
        format_str = DATETIME_FORMATS["date_only"]
    return dt.strftime(format_str)

def format_time(dt: datetime.datetime, format_str: str = None) -> str:
    """
    格式化时间
    
    Args:
        dt: 日期时间对象
        format_str: 格式字符串，默认使用标准时间格式
        
    Returns:
        格式化后的时间字符串
    """
    if format_str is None:
        format_str = DATETIME_FORMATS["time_only"]
    return dt.strftime(format_str)

def get_current_date_time() -> Tuple[str, str]:
    """
    获取当前日期和时间
    
    Returns:
        (日期字符串, 时间字符串)的元组
    """
    now = datetime.datetime.now()
    date_str = format_date(now)
    time_str = format_time(now)
    return date_str, time_str

def convert_relative_time(time_text: str) -> datetime.datetime:
    """
    将相对时间文本（如"3分钟前"，"昨天"）转换为datetime对象
    
    Args:
        time_text: 相对时间文本
        
    Returns:
        datetime对象
    """
    now = datetime.datetime.now()
    
    if not time_text or time_text.strip() == "":
        return now
    
    time_text = time_text.strip()
    
    # 刚刚
    if time_text == "刚刚" or time_text == "刚才":
        return now
    
    # x分钟前
    match = re.search(r'(\d+)\s*分钟前', time_text)
    if match:
        minutes = int(match.group(1))
        return now - datetime.timedelta(minutes=minutes)
    
    # x小时前
    match = re.search(r'(\d+)\s*小时前', time_text)
    if match:
        hours = int(match.group(1))
        return now - datetime.timedelta(hours=hours)
    
    # 今天
    if time_text.startswith("今天"):
        time_part = re.search(r'(\d{1,2}:\d{1,2})', time_text)
        if time_part:
            time_str = time_part.group(1)
            hour, minute = map(int, time_str.split(':'))
            return datetime.datetime(now.year, now.month, now.day, hour, minute)
        return datetime.datetime(now.year, now.month, now.day)
    
    # 昨天
    if time_text.startswith("昨天"):
        yesterday = now - datetime.timedelta(days=1)
        time_part = re.search(r'(\d{1,2}:\d{1,2})', time_text)
        if time_part:
            time_str = time_part.group(1)
            hour, minute = map(int, time_str.split(':'))
            return datetime.datetime(yesterday.year, yesterday.month, yesterday.day, hour, minute)
        return datetime.datetime(yesterday.year, yesterday.month, yesterday.day)
    
    # 前天
    if time_text.startswith("前天"):
        day_before_yesterday = now - datetime.timedelta(days=2)
        time_part = re.search(r'(\d{1,2}:\d{1,2})', time_text)
        if time_part:
            time_str = time_part.group(1)
            hour, minute = map(int, time_str.split(':'))
            return datetime.datetime(day_before_yesterday.year, day_before_yesterday.month, day_before_yesterday.day, hour, minute)
        return datetime.datetime(day_before_yesterday.year, day_before_yesterday.month, day_before_yesterday.day)
    
    # 尝试直接解析日期时间
    try:
        # 尝试解析标准格式
        formats = [
            DATETIME_FORMATS["standard"],
            DATETIME_FORMATS["standard_with_seconds"],
            DATETIME_FORMATS["date_only"] + " " + DATETIME_FORMATS["time_only"],
            DATETIME_FORMATS["dot_date"] + " " + DATETIME_FORMATS["time_only"]
        ]
        
        for fmt in formats:
            try:
                return datetime.datetime.strptime(time_text, fmt)
            except ValueError:
                continue
    except Exception:
        pass
    
    # 如果无法解析，返回当前时间
    logger.warning(f"无法解析时间文本: {time_text}，使用当前时间")
    return now

def get_current_datetime() -> datetime.datetime:
    """
    获取当前的datetime对象
    
    Returns:
        当前的datetime对象
    """
    return datetime.datetime.now() 