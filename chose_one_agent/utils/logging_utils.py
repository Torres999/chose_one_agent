"""
日志工具模块，提供统一的日志配置和处理功能
"""
import logging
import sys
import os
import traceback
import functools
from typing import Optional, Dict, Any, Callable

from chose_one_agent.utils.config import LOG_CONFIG

# 设置基本日志格式
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'
DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

def setup_logging(
    name: str = "chose_one_agent", 
    level: Optional[str] = None,
    log_file: Optional[str] = None,
    log_format: Optional[str] = None,
    propagate: bool = False
) -> logging.Logger:
    """
    设置和获取日志记录器
    
    Args:
        name: 日志记录器名称
        level: 日志级别，默认从配置获取
        log_file: 日志文件路径 (不再使用，仅为兼容性保留)
        log_format: 日志格式，默认从配置获取
        propagate: 是否传播日志到父级记录器

    Returns:
        配置好的Logger对象
    """
    # 获取日志配置
    level = level or LOG_CONFIG.get("level", "INFO")
    log_format = log_format or LOG_CONFIG.get("format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    
    # 创建日志记录器
    logger = logging.getLogger(name)
    
    # 设置日志级别
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(numeric_level)
    
    # 如果已经有处理器，不重复添加
    if logger.handlers:
        return logger
    
    # 创建控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    
    # 创建格式化器
    formatter = logging.Formatter(log_format, DATE_FORMAT)
    console_handler.setFormatter(formatter)
    
    # 添加处理器
    logger.addHandler(console_handler)
    
    # 如果提供了日志文件路径，添加文件处理器
    if log_file:
        # 确保日志目录存在
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)
            
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    # 设置是否传播
    logger.propagate = propagate
    
    return logger

def get_logger(name: str) -> logging.Logger:
    """
    获取或创建日志记录器
    
    Args:
        name: 日志记录器名称
    
    Returns:
        Logger对象
    """
    logger = logging.getLogger(name)
    
    # 如果不是根记录器且没有处理器，返回默认配置记录器
    if name != "root" and not logger.handlers and not logger.parent.handlers:
        return setup_logging(name)
    
    return logger

# 定义包装函数，便于在整个应用程序中使用统一的日志记录风格
def log_function_call(logger: logging.Logger):
    """装饰器: 记录函数调用信息"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            logger.debug("调用 {0}({1}, {2})".format(func.__name__, args, kwargs))
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                logger.error("{0} 出错: {1}".format(func.__name__, e), exc_info=True)
                raise
        return wrapper
    return decorator

def log_error(logger: logging.Logger, message: str, error: Exception, debug: bool = False):
    """
    统一错误日志记录
    
    Args:
        logger: 日志记录器
        message: 错误信息
        error: 异常对象
        debug: 是否记录堆栈信息
    """
    if debug:
        logger.error("{0}: {1}".format(message, error), exc_info=True)
    else:
        logger.error("{0}: {1}".format(message, error)) 