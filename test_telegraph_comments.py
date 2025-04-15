#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试脚本：用于收集和调试cls.cn/telegraph网站的评论元素信息
"""

import os
import logging
import datetime
import json
from typing import List, Dict, Any

from chose_one_agent.modules.telegraph.base_telegraph_scraper import BaseTelegraphScraper
from chose_one_agent.modules.telegraph.telegraph_scraper import TelegraphScraper
from chose_one_agent.utils.config import BASE_URL

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/tmp/telegraph_comments_test.log')
    ]
)
logger = logging.getLogger(__name__)

def main():
    """
    运行测试：收集和分析评论元素
    """
    try:
        logger.info("开始运行评论元素收集测试")
        
        # 设置截止日期为昨天，以确保获取最近的帖子
        cutoff_date = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        logger.info(f"使用截止日期: {cutoff_date}")
        
        # 使用非无头模式以便观察浏览器行为
        headless = False
        debug = True
        
        # 创建爬虫实例
        with TelegraphScraper(cutoff_date, headless=headless, debug=debug) as scraper:
            # 先导航到看盘板块，只检查一个板块即可
            sections = ["看盘"]
            
            # 运行爬虫
            logger.info(f"开始爬取板块: {sections}")
            
            # 测试收集一些帖子
            section_results = []
            
            for section in sections:
                logger.info(f"开始爬取'{section}'板块")
                
                # 使用对应的爬虫类
                if section == "看盘":
                    from chose_one_agent.modules.telegraph.sections.kanpan_scraper import KanpanScraper
                    section_scraper = KanpanScraper(
                        cutoff_date, 
                        headless, 
                        debug
                    )
                else:
                    logger.warning(f"未支持测试的板块: {section}，跳过")
                    continue
                
                # 初始化浏览器
                section_scraper.setup_browser()
                
                try:
                    # 导航到板块
                    if section_scraper.navigate_to_telegraph_section(section):
                        logger.info(f"成功导航到'{section}'板块")
                        
                        # 获取帖子列表
                        posts = section_scraper.collect_posts(max_posts=5)  # 只取5个帖子测试
                        logger.info(f"找到 {len(posts)} 个帖子")
                        
                        if posts:
                            # 对每个帖子，运行调试功能
                            for i, post in enumerate(posts[:3]):  # 只取前3个帖子测试
                                logger.info(f"测试帖子 {i+1}/{len(posts[:3])}")
                                
                                # 提取帖子信息
                                post_info = section_scraper.extract_post_info(post)
                                
                                if post_info:
                                    logger.info(f"帖子标题: {post_info.get('title', '无标题')}")
                                    
                                    # 调试页面结构
                                    debug_info = section_scraper.debug_page_structure()
                                    if debug_info:
                                        logger.info(f"已保存页面结构信息: {debug_info}")
                                    
                                    # 获取评论
                                    comments = section_scraper.get_comments(post)
                                    logger.info(f"找到 {len(comments)} 条评论")
                                    
                                    # 记录样本评论
                                    if comments:
                                        sample_comments = comments[:min(3, len(comments))]
                                        logger.info(f"样本评论: {sample_comments}")
                                    
                                    # 将结果添加到列表
                                    if comments:
                                        post_info["comments"] = comments
                                        post_info["section"] = section
                                        section_results.append(post_info)
                    else:
                        logger.error(f"无法导航到'{section}'板块")
                
                except Exception as e:
                    logger.error(f"处理'{section}'板块时出错: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                
                finally:
                    # 关闭浏览器
                    section_scraper.teardown_browser()
            
            # 保存结果
            if section_results:
                timestamp = int(datetime.datetime.now().timestamp())
                results_path = f"/tmp/telegraph_comments_results_{timestamp}.json"
                with open(results_path, "w", encoding="utf-8") as f:
                    json.dump(section_results, f, ensure_ascii=False, indent=2)
                logger.info(f"已保存测试结果至: {results_path}")
                logger.info(f"共获取到 {len(section_results)} 个帖子的信息")
            else:
                logger.warning("未获取到任何帖子信息")
        
        logger.info("评论元素收集测试完成")
    
    except Exception as e:
        logger.error(f"运行测试时发生错误: {e}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    main() 