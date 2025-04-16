#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试脚本：用于收集和调试cls.cn/telegraph网站的评论元素信息
"""

import os
import logging
import datetime
import json
import re
from typing import List, Dict, Any

from chose_one_agent.modules.telegraph.base_telegraph_scraper import BaseTelegraphScraper
from chose_one_agent.modules.telegraph.telegraph_scraper import TelegraphScraper
from chose_one_agent.modules.telegraph.post_extractor import PostExtractor
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

def find_non_zero_comment_posts(posts: List[Dict], max_results: int = 3) -> List[Dict]:
    """
    筛选出评论数非零的帖子
    
    Args:
        posts: 帖子列表
        max_results: 最多返回的结果数
        
    Returns:
        评论数非零的帖子列表
    """
    result = []
    for post in posts:
        comment_count = post.get('comment_count', 0)
        if comment_count > 0:
            result.append(post)
            logger.info(f"找到评论数非零的帖子: 标题='{post.get('title', '无标题')}', 评论数={comment_count}")
            if len(result) >= max_results:
                break
    
    if not result:
        logger.warning("未找到评论数非零的帖子，将使用原始帖子列表")
        # 如果没有找到评论数非零的帖子，返回原始帖子列表前几个
        return posts[:max_results]
    
    return result

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
        
        # 测试收集一些帖子
        section_results = []
        
        # 使用对应的爬虫类和上下文管理器方式初始化
        from chose_one_agent.modules.telegraph.sections.kanpan_scraper import KanpanScraper
        with KanpanScraper(
            cutoff_date, 
            headless, 
            debug
        ) as section_scraper:
            try:
                # 导航到板块
                section = "看盘"
                if section_scraper.navigate_to_telegraph_section(section):
                    logger.info(f"成功导航到'{section}'板块")
                    
                    # 创建PostExtractor来提取帖子
                    post_extractor = PostExtractor()
                    
                    # 从页面获取帖子
                    posts, reached_cutoff = post_extractor.extract_posts_from_page(section_scraper.page)
                    logger.info(f"找到 {len(posts)} 个帖子")
                    
                    # 过滤出评论数非零的帖子
                    test_posts = find_non_zero_comment_posts(posts)
                    logger.info(f"选择了 {len(test_posts)} 个帖子进行测试")
                    
                    if test_posts:
                        # 对每个帖子，运行调试功能
                        for i, post_info in enumerate(test_posts):
                            if not post_info.get("is_valid_post", False):
                                logger.warning(f"跳过无效帖子 {i+1}")
                                continue
                                
                            logger.info(f"测试帖子 {i+1}/{len(test_posts)}")
                            
                            # 获取帖子元素
                            post_element = post_info.get("element")
                            if not post_element:
                                logger.warning(f"帖子 {i+1} 没有关联元素，跳过")
                                continue
                            
                            if post_info:
                                logger.info(f"帖子标题: {post_info.get('title', '无标题')}")
                                logger.info(f"评论计数: {post_info.get('comment_count', 0)}")
                                
                                # 调试页面结构
                                debug_info = section_scraper.debug_page_structure()
                                if debug_info:
                                    logger.info(f"已保存页面结构信息: {debug_info}")
                                
                                # 获取评论
                                # 特别观察评论计数为0的处理情况
                                if post_info.get('comment_count', 0) == 0:
                                    logger.info("帖子评论计数为0，观察get_comments方法处理...")
                                else:
                                    logger.info(f"帖子评论计数为{post_info.get('comment_count', 0)}，尝试获取评论...")
                                    
                                comments = section_scraper.get_comments(post_element)
                                logger.info(f"找到 {len(comments)} 条评论")
                                
                                # 记录样本评论
                                if comments:
                                    sample_comments = comments[:min(3, len(comments))]
                                    logger.info(f"样本评论: {sample_comments}")
                                else:
                                    logger.info("未找到任何评论")
                                
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