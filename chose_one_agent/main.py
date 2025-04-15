import argparse
import datetime
import logging
import sys
import traceback
import os
from typing import List, Dict, Any

from chose_one_agent.modules.telegraph import TelegraphScraper
from chose_one_agent.utils.helpers import format_output
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',
    handlers=[
        logging.FileHandler("chose_one_agent.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def parse_args():
    """
    解析命令行参数
    
    Returns:
        解析后的参数
    """
    parser = argparse.ArgumentParser(description="ChoseOne财经网站分析智能体")
    parser.add_argument(
        "--cutoff_date", 
        type=str, 
        default=None,
        help="截止日期时间，格式为'YYYY-MM-DD HH:MM'，早于此日期的内容将被忽略"
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        default=True,
        help="是否使用无头模式运行浏览器"
    )
    parser.add_argument(
        "--sections",
        type=str,
        nargs="+",
        default=["看盘", "公司"],
        help="要爬取的电报子板块，例如'看盘'、'公司'等"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        default=False,
        help="是否启用调试模式"
    )
    parser.add_argument(
        "--sentiment-analyzer",
        type=str,
        choices=["snownlp", "deepseek"],
        default="snownlp",
        help="选择情感分析器类型，snownlp使用本地分析，deepseek使用DeepSeek API"
    )
    parser.add_argument(
        "--deepseek-api-key",
        type=str,
        default=None,
        help="DeepSeek API密钥，当选择deepseek情感分析器时必需。也可通过DEEPSEEK_API_KEY环境变量设置"
    )
    return parser.parse_args()

def parse_cutoff_date(cutoff_date_str: str) -> datetime.datetime:
    """
    解析截止日期字符串
    
    Args:
        cutoff_date_str: 截止日期时间字符串，格式为'YYYY-MM-DD HH:MM'
        
    Returns:
        datetime对象
    """
    if not cutoff_date_str:
        # 默认为当前时间前24小时
        return datetime.datetime.now() - datetime.timedelta(days=1)
    
    try:
        return datetime.datetime.strptime(cutoff_date_str, "%Y-%m-%d %H:%M")
    except ValueError as e:
        logger.error(f"无效的截止日期格式: {cutoff_date_str}，应为'YYYY-MM-DD HH:MM': {e}")
        # 默认为当前时间前24小时
        return datetime.datetime.now() - datetime.timedelta(days=1)

def format_results(results: List[Dict[str, Any]]) -> str:
    """
    格式化结果输出
    
    Args:
        results: 分析结果列表
        
    Returns:
        格式化的输出字符串
    """
    if not results:
        return "未找到符合条件的内容"
    
    output_parts = []
    for result in results:
        title = result.get("title", "无标题")
        date = result.get("date", "")
        time = result.get("time", "")
        section = result.get("section", "未知板块")
        
        # 收集所有情感分析相关的字段
        sentiment_info = {
            "sentiment_score": result.get("sentiment_score", 3),
            "sentiment_label": result.get("sentiment_label", "中性"),
            "has_comments": result.get("has_comments", False),
            "comments": result.get("comments", []),
            "sentiment_analysis": result.get("sentiment_analysis", "")
        }
        
        # 如果还存在旧格式的sentiment字段，优先使用
        old_sentiment = result.get("sentiment", None)
        if old_sentiment is not None:
            sentiment = old_sentiment
        else:
            sentiment = sentiment_info
        
        # 获取Deepseek分析结果（如果有）
        deepseek_analysis = result.get("deepseek_analysis", None)
        
        formatted = format_output(title, date, time, sentiment, section, deepseek_analysis)
        output_parts.append(formatted)
        output_parts.append("-" * 50)
    
    return "\n".join(output_parts)

def run_telegraph_scraper(cutoff_date: datetime.datetime, sections: List[str], headless: bool, debug: bool = False, 
                          sentiment_analyzer: str = "snownlp", deepseek_api_key: str = None) -> List[Dict[str, Any]]:
    """
    运行电报爬虫
    
    Args:
        cutoff_date: 截止日期
        sections: 要爬取的电报子板块列表
        headless: 是否使用无头模式
        debug: 是否启用调试模式
        sentiment_analyzer: 情感分析器类型，"snownlp"或"deepseek"
        deepseek_api_key: DeepSeek API密钥
        
    Returns:
        分析结果列表
    """
    # 处理并清理板块名称，确保没有空白符和无效字符
    processed_sections = []
    for section in sections:
        section = section.strip()
        if section:  # 确保不是空字符串
            processed_sections.append(section)
    
    # 如果处理后没有有效的板块，使用默认值
    if not processed_sections:
        processed_sections = ["看盘", "公司"]
        
    logger.info(f"开始爬取电报，截止日期: {cutoff_date}, 子板块: {processed_sections}")
    logger.info(f"使用情感分析器: {sentiment_analyzer}")
    
    # 检查DeepSeek API密钥
    if sentiment_analyzer == "deepseek":
        deepseek_api_key = deepseek_api_key or os.environ.get("DEEPSEEK_API_KEY")
        if not deepseek_api_key:
            logger.warning("使用DeepSeek情感分析器但未提供API密钥，将回退至SnowNLP")
            sentiment_analyzer = "snownlp"
        else:
            logger.info("已设置DeepSeek API密钥")
    
    # 如果是调试模式，设置日志级别为DEBUG
    if debug:
        logging.getLogger("chose_one_agent").setLevel(logging.DEBUG)
    
    try:
        # 不使用上下文管理器，直接创建实例
        scraper = TelegraphScraper(
            cutoff_date=cutoff_date, 
            headless=headless, 
            debug=debug,
            sentiment_analyzer_type=sentiment_analyzer,
            deepseek_api_key=deepseek_api_key
        )
        results = scraper.run(processed_sections)
        logger.info(f"电报爬取完成，共处理了 {len(results)} 条电报")
        return results
    except Exception as e:
        logger.error(f"运行电报爬虫时出错: {e}")
        logger.error(traceback.format_exc())
        return []

def main():
    """
    主函数
    """
    # 解析命令行参数
    args = parse_args()
    cutoff_date = parse_cutoff_date(args.cutoff_date)
    
    # 如果是调试模式，显示所有参数
    if args.debug:
        logger.setLevel(logging.DEBUG)
        logger.debug(f"命令行参数: {args}")
        logger.debug(f"截止日期: {cutoff_date}")
    
    logger.info(f"开始运行ChoseOne财经网站分析智能体，截止日期: {cutoff_date}")
    
    try:
        # 爬取电报内容
        results = run_telegraph_scraper(
            cutoff_date, 
            args.sections, 
            args.headless, 
            args.debug,
            args.sentiment_analyzer,
            args.deepseek_api_key
        )
        
        # 格式化并输出结果
        formatted_output = format_results(results)
        print("\n" + formatted_output)
        
        logger.info(f"分析完成，共处理了 {len(results)} 条内容")
        
    except Exception as e:
        logger.error(f"运行过程中出错: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main() 