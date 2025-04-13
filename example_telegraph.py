#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TelegraphScraper 使用示例
"""

import datetime
import sys
import logging
from chose_one_agent.modules.telegraph import TelegraphScraper
from chose_one_agent.utils.helpers import format_output

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def main():
    """
    TelegraphScraper 使用示例主函数
    """
    # 设置截止日期为24小时前
    cutoff_date = datetime.datetime.now() - datetime.timedelta(days=1)
    logger.info(f"设置截止日期为: {cutoff_date}")
    
    # 要爬取的板块
    sections = ["看盘", "公司"]
    logger.info(f"爬取的板块: {sections}")
    
    # 使用上下文管理器初始化并运行爬虫
    try:
        with TelegraphScraper(cutoff_date=cutoff_date, headless=True) as scraper:
            results = scraper.run(sections)
            logger.info(f"爬取完成，共获取到 {len(results)} 条电报")
            
            # 格式化并打印结果
            if results:
                print("\n===== 爬取结果 =====")
                
                # 检查并打印每个板块的结果数量
                kanpan_count = sum(1 for r in results if r.get("section") == "看盘")
                company_count = sum(1 for r in results if r.get("section") == "公司")
                unknown_count = sum(1 for r in results if r.get("section") not in ["看盘", "公司"])
                
                print(f"看盘板块: {kanpan_count}条")
                print(f"公司板块: {company_count}条")
                if unknown_count > 0:
                    print(f"未知板块: {unknown_count}条")
                
                for i, result in enumerate(results, 1):
                    title = result.get("title", "无标题")
                    date = result.get("date", "")
                    time = result.get("time", "")
                    sentiment = result.get("sentiment", None)
                    section = result.get("section", "未知板块")
                    
                    # 强制设置板块名称，防止未知板块的出现
                    if not section or section == "未知板块":
                        if "看盘" in title or "股" in title or any(code in title for code in ["SH", "SZ", "BJ", "HK"]):
                            section = "看盘"
                        elif "公司" in title or "集团" in title or "股份" in title:
                            section = "公司"
                    
                    # 使用format_output输出，确保包含板块信息
                    formatted = format_output(title, date, time, sentiment, section)
                    print(f"\n[{i}] {formatted}")
                    print("-" * 50)
            else:
                print("\n没有找到符合条件的电报")
    except Exception as e:
        logger.error(f"运行爬虫时出错: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 1
        
    return 0

if __name__ == "__main__":
    sys.exit(main()) 