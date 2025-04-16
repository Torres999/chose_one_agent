# -*- coding: utf-8 -*-
import logging
import time
import re
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    StaleElementReferenceException,
)

# 配置日志
logger = logging.getLogger(__name__)

class TelegraphScraper:
    """
    Telegraph网站抓取器类，负责网页交互和内容提取
    """
    
    def __init__(self, driver, max_retries=3, debug=False):
        """
        初始化抓取器
        
        Args:
            driver: Selenium WebDriver实例
            max_retries: 最大重试次数
            debug: 是否启用调试模式
        """
        self.driver = driver
        self.max_retries = max_retries
        self.debug = debug
        self.telegraph_url = "https://www.eastmoney.com/telegraph/"
        self.last_navigate_time = 0
    
    def get_comments(self, element, max_comments=None) -> List[str]:
        """
        从帖子元素中提取评论
        
        Args:
            element: 帖子元素
            max_comments: 最大评论数量，None表示不限制
            
        Returns:
            评论列表
        """
        comments = []
        try:
            # 尝试查找评论区域
            comment_elements = element.find_elements(By.CSS_SELECTOR, ".comment-item")
            
            for i, comment_element in enumerate(comment_elements):
                if max_comments and i >= max_comments:
                    break
                    
                try:
                    # 提取评论文本
                    comment_text = comment_element.find_element(By.CSS_SELECTOR, ".comment-content").text.strip()
                    if comment_text:
                        comments.append(comment_text)
                except Exception as e:
                    if self.debug:
                        logger.warning(f"提取评论时出错: {e}")
                    continue
            
            return comments
        except Exception as e:
            if self.debug:
                logger.warning(f"获取评论时出错: {e}")
            return []
    
    def navigate_to_telegraph_section(self, section_name: str) -> bool:
        """
        导航到指定的Telegraph板块
        
        Args:
            section_name: 板块名称
            
        Returns:
            是否成功导航到指定板块
        """
        # 防止频繁导航，设置最小间隔时间
        current_time = time.time()
        if current_time - self.last_navigate_time < 1:
            time.sleep(1)
        
        # 更新最后导航时间
        self.last_navigate_time = time.time()
        
        # 重试计数器
        retries = 0
        
        while retries < self.max_retries:
            try:
                # 导航到Telegraph主页
                if self.driver.current_url != self.telegraph_url:
                    logger.info(f"导航到Telegraph主页: {self.telegraph_url}")
                    self.driver.get(self.telegraph_url)
                    time.sleep(2)  # 等待页面加载
                
                # 查找板块链接
                sections = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".section-link"))
                )
                
                # 遍历所有板块链接
                for section in sections:
                    if section.text.strip() == section_name:
                        # 找到目标板块，点击进入
                        logger.info(f"找到目标板块: {section_name}，准备点击")
                        section.click()
                        
                        # 等待板块页面加载
                        WebDriverWait(self.driver, 10).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, ".post-list"))
                        )
                        
                        logger.info(f"已成功导航到 {section_name} 板块")
                        return True
                
                # 如果未找到指定板块，记录警告并返回失败
                logger.warning(f"未找到板块: {section_name}")
                return False
                
            except TimeoutException:
                retries += 1
                logger.warning(f"导航到板块 {section_name} 超时 (尝试 {retries}/{self.max_retries})")
                # 刷新页面并重试
                self.driver.refresh()
                time.sleep(2)
                
            except Exception as e:
                retries += 1
                logger.error(f"导航到板块 {section_name} 时出错: {e} (尝试 {retries}/{self.max_retries})")
                # 刷新页面并重试
                self.driver.refresh()
                time.sleep(2)
        
        # 达到最大重试次数后仍失败
        logger.error(f"达到最大重试次数 ({self.max_retries})，无法导航到板块 {section_name}")
        return False
    
    def verify_section_content(self, section_name: str) -> bool:
        """
        验证当前页面是否为指定板块的内容
        
        Args:
            section_name: 板块名称
            
        Returns:
            当前页面是否为指定板块的内容
        """
        try:
            # 等待页面标题元素加载
            section_title = WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".section-title"))
            )
            
            # 验证标题是否匹配
            if section_title.text.strip() == section_name:
                return True
            
            # 如果标题不匹配，尝试检查面包屑导航
            breadcrumbs = self.driver.find_elements(By.CSS_SELECTOR, ".breadcrumb-item")
            for breadcrumb in breadcrumbs:
                if breadcrumb.text.strip() == section_name:
                    return True
            
            # 未找到匹配的标题或面包屑
            logger.warning(f"当前页面不是 {section_name} 板块")
            return False
            
        except (TimeoutException, NoSuchElementException) as e:
            logger.error(f"验证板块内容时出错: {e}")
            return False
    
    def extract_post_info(self, post_element) -> Dict[str, Any]:
        """
        从帖子元素中提取帖子信息
        
        Args:
            post_element: 帖子元素
            
        Returns:
            包含帖子信息的字典
        """
        post_info = {
            "title": "",
            "date": "",
            "time": "",
            "comment_count": 0,
            "section": ""
        }
        
        try:
            # 提取帖子标题
            title_element = post_element.find_element(By.CSS_SELECTOR, ".post-title")
            post_info["title"] = title_element.text.strip()
            
            # 提取发帖时间（日期和时间）
            try:
                time_element = post_element.find_element(By.CSS_SELECTOR, ".post-time")
                time_text = time_element.text.strip()
                
                # 解析时间字符串
                if time_text:
                    # 常见的时间格式: "2023-04-15 14:30"
                    time_parts = time_text.split()
                    if len(time_parts) >= 2:
                        post_info["date"] = time_parts[0]
                        post_info["time"] = time_parts[1]
                    else:
                        post_info["date"] = time_text
            except NoSuchElementException:
                # 如果没有找到时间元素，使用当前日期和时间
                now = datetime.now()
                post_info["date"] = now.strftime("%Y-%m-%d")
                post_info["time"] = now.strftime("%H:%M")
            
            # 提取评论数量
            try:
                comment_count_element = post_element.find_element(By.CSS_SELECTOR, ".comment-count")
                comment_count_text = comment_count_element.text.strip()
                
                # 提取数字部分
                count_match = re.search(r'\d+', comment_count_text)
                if count_match:
                    post_info["comment_count"] = int(count_match.group())
            except (NoSuchElementException, ValueError):
                # 如果没有找到评论数量元素或解析出错，使用默认值0
                post_info["comment_count"] = 0
            
            # 提取所属板块
            try:
                section_element = post_element.find_element(By.CSS_SELECTOR, ".post-section")
                post_info["section"] = section_element.text.strip()
            except NoSuchElementException:
                # 如果没有找到板块元素，尝试从页面标题获取
                try:
                    section_title = self.driver.find_element(By.CSS_SELECTOR, ".section-title")
                    post_info["section"] = section_title.text.strip()
                except NoSuchElementException:
                    # 如果仍然找不到，使用默认值
                    post_info["section"] = "未知板块"
            
            return post_info
            
        except Exception as e:
            logger.error(f"提取帖子信息时出错: {e}")
            return post_info
    
    def scrape_section(self, section_name: str, max_posts: int = 10, max_comments_per_post: int = 20) -> List[Dict[str, Any]]:
        """
        抓取指定板块的帖子内容
        
        Args:
            section_name: 板块名称
            max_posts: 最大帖子数量
            max_comments_per_post: 每个帖子的最大评论数量
            
        Returns:
            包含帖子信息和评论的列表
        """
        results = []
        
        try:
            # 导航到指定板块
            if not self.navigate_to_telegraph_section(section_name):
                logger.error(f"无法导航到板块 {section_name}，抓取操作终止")
                return results
            
            # 验证当前页面是否为指定板块
            if not self.verify_section_content(section_name):
                logger.error(f"页面内容验证失败，当前页面不是 {section_name} 板块")
                return results
            
            # 等待帖子列表加载
            post_elements = WebDriverWait(self.driver, 10).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".post-item"))
            )
            
            # 限制帖子数量
            post_elements = post_elements[:max_posts] if len(post_elements) > max_posts else post_elements
            
            logger.info(f"在 {section_name} 板块中找到 {len(post_elements)} 个帖子，准备处理")
            
            # 遍历处理每个帖子
            for i, post_element in enumerate(post_elements, 1):
                try:
                    # 提取帖子信息
                    post_info = self.extract_post_info(post_element)
                    
                    # 提取评论
                    comments = self.get_comments(post_element, max_comments_per_post)
                    
                    # 记录帖子和评论信息
                    post_data = post_info.copy()
                    post_data["comments"] = comments
                    post_data["has_comments"] = len(comments) > 0
                    
                    results.append(post_data)
                    
                    logger.info(f"处理第 {i}/{len(post_elements)} 个帖子：{post_info.get('title', '未知标题')}，找到 {len(comments)} 条评论")
                    
                except (StaleElementReferenceException, NoSuchElementException) as e:
                    logger.warning(f"处理第 {i} 个帖子时元素状态异常: {e}")
                    continue
                    
                except Exception as e:
                    logger.error(f"处理第 {i} 个帖子时出错: {e}")
                    continue
            
            return results
            
        except Exception as e:
            logger.error(f"抓取板块 {section_name} 时出错: {e}")
            return results 