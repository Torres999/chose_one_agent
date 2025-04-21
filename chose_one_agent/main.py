# -*- coding: utf-8 -*-
import argparse
import datetime
import sys
import os

from chose_one_agent.scrapers.base_scraper import BaseScraper
from chose_one_agent.utils.extraction import format_output
from chose_one_agent.utils.datetime_utils import parse_cutoff_date
from chose_one_agent.utils.logging_utils import setup_logging, log_error
from chose_one_agent.utils.config import SCRAPER_CONFIG
from chose_one_agent.utils.constants import DEFAULT_CUTOFF_DAYS
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 设置日志
logger = setup_logging("chose_one_agent.main")

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
        default=SCRAPER_CONFIG["default_headless"],
        help="是否使用无头模式运行浏览器"
    )
    parser.add_argument(
        "--sections",
        type=str,
        nargs="+",
        default=SCRAPER_CONFIG["default_sections"],
        help="要爬取的电报子板块，例如'看盘'、'公司'等"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        default=False,
        help="是否启用调试模式"
    )
    # 添加情感分析器相关参数
    parser.add_argument(
        "--sentiment-analyzer",
        type=str,
        choices=["none", "deepseek"],
        default="none",
        help="选择情感分析器类型"
    )
    parser.add_argument(
        "--deepseek-api-key",
        type=str,
        default=os.environ.get("DEEPSEEK_API_KEY", ""),
        help="DeepSeek API密钥"
    )
    return parser.parse_args()

def format_results(posts, args):
    """格式化结果输出"""
    output = []
    for title, date, time, sect, _, sentiment_analysis, text in posts:
        # 直接使用完整的情感分析结果
        output.append(format_output(
            title=title,
            date=date,
            time=time,
            section=sect,
            sentiment=sentiment_analysis,  # 传递完整的情感分析结果
            deepseek_analysis=None,
        ))

    return output

def run_telegraph_scraper(cutoff_date, sections, headless, sentiment_analyzer="none", deepseek_api_key=None, debug=False):
    """
    运行电报爬虫
    
    Args:
        cutoff_date: 截止日期
        sections: 要爬取的电报子板块列表
        headless: 是否使用无头模式
        sentiment_analyzer: 情感分析器类型
        deepseek_api_key: DeepSeek API密钥
        debug: 是否启用调试模式
        
    Returns:
        分析结果列表
    """
    # 处理并清理板块名称，确保没有空白符和无效字符
    processed_sections = [s.strip() for s in sections if s.strip()]
    
    # 如果处理后没有有效的板块，使用默认值
    if not processed_sections:
        processed_sections = SCRAPER_CONFIG["default_sections"]
        
    logger.info("开始爬取电报，截止日期: {0}, 子板块: {1}".format(cutoff_date, processed_sections))
    
    # 初始化情感分析器
    analyzer = None
    if sentiment_analyzer == "deepseek":
        try:
            from chose_one_agent.analyzers.deepseek_sentiment_analyzer import DeepSeekSentimentAnalyzer
            analyzer = DeepSeekSentimentAnalyzer(api_key=deepseek_api_key, debug=debug)
            logger.info("成功初始化DeepSeek情感分析器")
        except ImportError as e:
            logger.error(f"导入DeepSeek情感分析器失败: {e}")
    
    try:
        # 创建爬虫实例
        scraper = BaseScraper(
            cutoff_date=cutoff_date, 
            headless=headless, 
            debug=debug
        )
        
        # 运行爬虫
        raw_results = scraper.run_telegraph_scraper(processed_sections)
        
        # 转换为format_results预期的格式
        results = []
        for post in raw_results:
            # 提取评论
            comments = post.get("comments", [])
            comment_texts = []
            if isinstance(comments, list):
                for comment in comments:
                    if isinstance(comment, str):
                        comment_texts.append(comment)
                    elif isinstance(comment, dict) and "content" in comment:
                        comment_texts.append(comment["content"])
            
            # 构建情感分析结果
            sentiment_analysis = {
                "total_comments": len(comment_texts)
            }
            
            # 如果有评论且启用了情感分析器，进行情感分析
            if comment_texts and analyzer and len(comment_texts) > 0:
                try:
                    logger.info(f"对帖子 '{post.get('title', '未知标题')}' 的 {len(comment_texts)} 条评论进行【情感分析】")
                    analysis_result = analyzer.analyze_comments(comment_texts)
                    
                    # 合并分析结果
                    sentiment_analysis.update(analysis_result)
                    
                    if debug:
                        logger.debug(f"情感分析结果: {analysis_result}")
                except Exception as e:
                    logger.error(f"情感分析失败: {e}")
            
            # 创建7元素元组: (标题,日期,时间,板块,_,情感分析,内容)
            result_tuple = (
                post.get("title", ""),
                post.get("date", ""),
                post.get("time", ""),
                post.get("section", ""),
                None,  # 占位符
                sentiment_analysis,
                post.get("content", "")
            )
            results.append(result_tuple)
        
        # 仅在调试模式下显示详细日志
        if debug:
            logger.info("电报爬取完成，共处理了 {0} 条电报".format(len(results)))
        return results
    except Exception as e:
        log_error(logger, "运行电报爬虫时出错", e, debug)
        return []

def main():
    """
    主函数
    """
    # 解析命令行参数
    args = parse_args()
    
    try:
        # 解析截止日期，如果解析失败会抛出异常
        cutoff_date = parse_cutoff_date(args.cutoff_date)
    except ValueError as e:
        logger.error("截止日期解析失败: {0}".format(e))
        print("\n错误: {0}".format(e))
        sys.exit(1)
        
    # 如果是调试模式，显示所有参数
    if args.debug:
        logger.debug("命令行参数: {0}".format(args))
        logger.debug("截止日期: {0}".format(cutoff_date))
    
    logger.info("开始运行ChoseOne财经网站分析智能体")
    
    try:
        # 爬取电报内容
        results = run_telegraph_scraper(
            cutoff_date, 
            args.sections, 
            args.headless,
            args.sentiment_analyzer,
            args.deepseek_api_key, 
            args.debug
        )
        
        # 格式化并输出结果
        formatted_output = format_results(results, args)
        print("\n" + "\n".join(formatted_output))
        
        # 仅在调试模式下显示总结日志
        if args.debug:
            logger.info("分析完成，共处理了 {0} 条内容".format(len(results)))
        
    except Exception as e:
        log_error(logger, "运行过程中出错", e, args.debug)
        sys.exit(1)

if __name__ == "__main__":
    main() 