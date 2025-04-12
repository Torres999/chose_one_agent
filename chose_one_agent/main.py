import argparse
import datetime
import logging
import sys
import traceback
from typing import List, Dict, Any

from chose_one_agent.modules.telegraph import TelegraphScraper
from chose_one_agent.utils.helpers import format_output

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
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
        sentiment = result.get("sentiment", None)
        
        formatted = format_output(title, date, time, sentiment)
        output_parts.append(formatted)
        output_parts.append("-" * 50)
    
    return "\n".join(output_parts)

def run_telegraph_scraper(cutoff_date: datetime.datetime, sections: List[str], headless: bool, debug: bool = False) -> List[Dict[str, Any]]:
    """
    运行电报爬虫
    
    Args:
        cutoff_date: 截止日期
        sections: 要爬取的电报子板块列表
        headless: 是否使用无头模式
        debug: 是否启用调试模式
        
    Returns:
        分析结果列表
    """
    logger.info(f"开始爬取电报，截止日期: {cutoff_date}, 子板块: {sections}")
    
    # 如果是调试模式，设置日志级别为DEBUG
    if debug:
        logging.getLogger("chose_one_agent").setLevel(logging.DEBUG)
    
    try:
        with TelegraphScraper(cutoff_date=cutoff_date, headless=headless) as scraper:
            results = scraper.run(sections)
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
        results = run_telegraph_scraper(cutoff_date, args.sections, args.headless, args.debug)
        
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