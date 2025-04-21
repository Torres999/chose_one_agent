# -*- coding: utf-8 -*-
"""
评论提取器模块，用于从网页中提取评论信息
"""
import re
import time
import json
import logging
import traceback
from typing import List, Dict, Any, Optional, Union
from urllib.parse import urljoin
from datetime import datetime

from playwright.sync_api import ElementHandle, Page
from bs4 import BeautifulSoup

from chose_one_agent.utils.logging_utils import get_logger, log_error
from chose_one_agent.utils.config import BASE_URL
from chose_one_agent.utils.extraction import clean_text

# 获取日志记录器
logger = get_logger(__name__)

# 评论相关选择器
COMMENT_SELECTORS = {
    "COMMENT_CONTAINER": ".comment-container, .comment-list, .evaluate-list",
    "COMMENT_ITEM": ".comment-item, .evaluate-item, .comment",
    "COMMENT_TEXT": ".comment-content, .evaluate-content, .comment-text, .text",
    "COMMENT_AUTHOR": ".comment-author, .evaluate-author, .author, .username, .nickname",
    "COMMENT_DATE": ".comment-time, .evaluate-time, .time, .date, .post-time",
    "MORE_COMMENT_BTN": ".more-comment, .load-more, button:has-text('加载更多')"
}

# 正则表达式
TIME_REGEX = re.compile(r'(\d{2}:\d{2}(?::\d{2})?)')
NUMBER_REGEX = re.compile(r'(\d+)')

class CommentExtractor:
    """评论提取器类，负责从网页中提取评论信息"""
    
    def __init__(self, page: Optional[Page] = None, debug: bool = False):
        """
        初始化评论提取工具
        
        Args:
            page: Playwright页面对象
            debug: 是否启用调试模式
        """
        self.page = page
        self.debug = debug
    
    def set_page(self, page: Page):
        """
        设置页面对象
        
        Args:
            page: Playwright页面对象
        """
        self.page = page
    
    def extract_comments(self, post_url: str, max_comments: int = 50) -> List[str]:
        """
        从帖子URL中提取评论
        
        Args:
            post_url: 帖子URL
            max_comments: 最大获取评论数
            
        Returns:
            评论内容列表
        """
        if not self.page:
            logger.error("未设置页面实例，无法提取评论")
            return []
            
        try:
            logger.info(f"正在从 {post_url} 获取评论")
            
            # 导航到评论页面
            self.page.goto(post_url, wait_until="networkidle")
            time.sleep(2)  # 等待评论加载
            
            # 提取评论
            return self._extract_comment_texts(max_comments)
            
        except Exception as e:
            log_error(logger, f"从 {post_url} 提取评论时出错", e, self.debug)
            return []
            
    def _extract_comment_texts(self, max_comments: int) -> List[str]:
        """从当前页面提取评论文本"""
        try:
            # 加载所有评论
            self._load_all_comments(max_comments)
            
            # 获取评论元素
            comment_items = self.page.query_selector_all(COMMENT_SELECTORS["COMMENT_ITEM"])
            
            logger.info(f"找到 {len(comment_items)} 个评论元素")
            
            # 提取评论文本
            comment_texts = []
            for item in comment_items:
                try:
                    text = self._get_comment_content(item)
                    if text and text.strip():
                        comment_texts.append(text.strip())
                except Exception as e:
                    logger.warning(f"提取评论内容时出错: {e}")
            
            logger.info(f"成功提取了 {len(comment_texts)} 条评论")
            return comment_texts
            
        except Exception as e:
            log_error(logger, "提取评论文本时出错", e, self.debug)
            return []
            
    def _get_comment_content(self, element) -> str:
        """从评论元素中提取内容"""
        try:
            # 尝试主选择器
            text_el = element.query_selector(COMMENT_SELECTORS["COMMENT_TEXT"])
            if text_el:
                return text_el.inner_text().strip()
                
            # 尝试备用选择器
            for selector in [".text", ".content", "p", ".message"]:
                text_el = element.query_selector(selector)
                if text_el:
                    content = text_el.inner_text().strip()
                    if content:
                        return content
                        
            # 如果都找不到，尝试直接使用元素内容
            content = element.inner_text().strip()
            return content
            
        except Exception as e:
            logger.warning(f"获取评论内容时出错: {e}")
            return ""
            
    def _get_comment_count(self) -> int:
        """获取评论总数"""
        try:
            # 尝试从评论数文本中提取
            count_el = self.page.query_selector('.comment-count, .evaluate-count, [class*="count"]')
            if count_el:
                count_text = count_el.inner_text().strip()
                match = NUMBER_REGEX.search(count_text)
                if match:
                    return int(match.group(1))
                    
            # 尝试直接计算评论元素数量
            comment_items = self.page.query_selector_all(COMMENT_SELECTORS["COMMENT_ITEM"])
            return len(comment_items)
            
        except Exception as e:
            logger.warning(f"获取评论总数时出错: {e}")
            return 0
            
    def _load_all_comments(self, target_count: int) -> bool:
        """
        加载所有评论
        
        Args:
            target_count: 目标评论数量
            
        Returns:
            是否成功加载
        """
        try:
            # 获取当前评论数
            current_count = len(self.page.query_selector_all(COMMENT_SELECTORS["COMMENT_ITEM"]))
            
            # 如果当前评论数已经足够，无需加载更多
            if current_count >= target_count:
                logger.info(f"当前评论数 {current_count} 已达到目标 {target_count}")
                return True
                
            # 获取预期评论总数
            total_count = self._get_comment_count()
            actual_target = min(target_count, total_count) if total_count > 0 else target_count
            
            logger.info(f"开始加载评论: {current_count}/{actual_target}")
            
            # 加载更多评论
            self._load_more_comments(actual_target)
            
            # 检查是否加载成功
            final_count = len(self.page.query_selector_all(COMMENT_SELECTORS["COMMENT_ITEM"]))
            success = final_count >= actual_target or final_count >= current_count
            
            logger.info(f"评论加载{'成功' if success else '失败'}: {final_count}/{actual_target}")
            return success
            
        except Exception as e:
            log_error(logger, "加载评论时出错", e, self.debug)
            return False
            
    def _load_more_comments(self, target_count: int, max_attempts: int = 10):
        """
        点击"加载更多"按钮加载更多评论
        
        Args:
            target_count: 目标评论数量
            max_attempts: 最大尝试次数
        """
        attempts = 0
        while attempts < max_attempts:
            try:
                # 检查当前评论数量
                current_comments = self.page.query_selector_all(COMMENT_SELECTORS["COMMENT_ITEM"])
                current_count = len(current_comments)
                
                if current_count >= target_count:
                    logger.info(f"已加载足够的评论: {current_count}/{target_count}")
                    break

                # 查找加载更多按钮
                more_btn = self.page.query_selector(COMMENT_SELECTORS["MORE_COMMENT_BTN"])
                if not more_btn:
                    logger.info("没有更多评论可加载")
                    break

                # 点击加载更多
                logger.info(f"加载更多评论 ({current_count}/{target_count})")
                more_btn.click()
                self.page.wait_for_timeout(1000)  # 等待加载
                
                # 检查是否有新评论加载
                new_comments = self.page.query_selector_all(COMMENT_SELECTORS["COMMENT_ITEM"])
                if len(new_comments) <= current_count:
                    attempts += 1
                    logger.info(f"未加载新评论，尝试次数: {attempts}/{max_attempts}")
                else:
                    attempts = 0  # 重置尝试次数
                    
            except Exception as e:
                logger.error(f"加载更多评论时出错: {e}")
                attempts += 1
                
        logger.info(f"评论加载完成，总计: {len(self.page.query_selector_all(COMMENT_SELECTORS['COMMENT_ITEM']))}")
            
    def _extract_comment_info(self, comment_element: ElementHandle) -> Dict[str, Any]:
        """从评论元素中提取信息
        
        Args:
            comment_element: 评论元素
            
        Returns:
            评论信息字典
        """
        try:
            # 提取评论内容
            text_el = comment_element.query_selector(COMMENT_SELECTORS["COMMENT_TEXT"])
            comment_text = text_el.inner_text() if text_el else ""
            
            # 提取评论者
            author_el = comment_element.query_selector(COMMENT_SELECTORS["COMMENT_AUTHOR"])
            author = author_el.inner_text() if author_el else "匿名用户"
            
            # 提取评论时间
            date_el = comment_element.query_selector(COMMENT_SELECTORS["COMMENT_DATE"])
            date_time = ""
            if date_el:
                date_text = date_el.inner_text()
                match = TIME_REGEX.search(date_text)
                if match:
                    date_time = match.group()
                    
            return {
                "author": author,
                "content": comment_text,
                "datetime": date_time,
                "raw_html": comment_element.inner_html()
            }
        except Exception as e:
            logger.error(f"提取评论信息时出错: {e}")
            return {}
            
    def get_comments_text(self, comments: List[Dict[str, Any]]) -> List[str]:
        """提取评论文本列表
        
        Args:
            comments: 评论信息列表
            
        Returns:
            评论文本列表
        """
        return [comment.get("content", "") for comment in comments if comment.get("content")]
            
    def analyze_sentiment(self, comments: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        分析评论情感
        
        Args:
            comments: 评论列表
            
        Returns:
            分析结果
        """
        # 返回空分析结果
        return {"insight": ""}
    
    def extract_info_from_html(self, html_content: str) -> List[Dict[str, Any]]:
        """从HTML内容中提取评论信息
        
        Args:
            html_content: HTML内容
            
        Returns:
            评论信息列表
        """
        comments = []
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            comment_items = soup.select(COMMENT_SELECTORS["COMMENT_ITEM"])
            
            for item in comment_items:
                try:
                    # 提取评论内容
                    text_el = item.select_one(COMMENT_SELECTORS["COMMENT_TEXT"])
                    comment_text = text_el.get_text() if text_el else ""
                    
                    # 提取评论者
                    author_el = item.select_one(COMMENT_SELECTORS["COMMENT_AUTHOR"])
                    author = author_el.get_text() if author_el else "匿名用户"
                    
                    # 提取评论时间
                    date_el = item.select_one(COMMENT_SELECTORS["COMMENT_DATE"])
                    date_time = ""
                    if date_el:
                        date_text = date_el.get_text()
                        match = TIME_REGEX.search(date_text)
                        if match:
                            date_time = match.group()
                            
                    comments.append({
                        "author": author,
                        "content": comment_text,
                        "datetime": date_time,
                        "raw_html": str(item)
                    })
                except Exception as e:
                    logger.error(f"解析评论元素时出错: {e}")
                    continue
            return comments
        except Exception as e:
            logger.error(f"从HTML提取评论信息时出错: {e}")
            return []

    def extract_comment_count(self, element_text: str) -> int:
        """从元素文本中提取评论数量
        
        Args:
            element_text: 元素文本
            
        Returns:
            评论数量
        """
        try:
            match = NUMBER_REGEX.search(element_text)
            if match:
                return int(match.group())
        except Exception as e:
            logger.error(f"提取评论数量时出错: {e}")
        return 0 