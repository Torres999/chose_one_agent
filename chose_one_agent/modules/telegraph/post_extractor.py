# -*- coding: utf-8 -*-
import logging
import re
import time
from typing import List, Dict, Any, Tuple

# 配置日志
logger = logging.getLogger(__name__)

class PostExtractor:
    """帖子内容提取器类，用于从页面中提取帖子信息"""
    
    def extract_post_info(self, post_element) -> Dict[str, Any]:
        """
        从帖子元素中提取信息

        Args:
            post_element: 帖子的DOM元素

        Returns:
            包含帖子信息的字典
        """
        try:
            element_text = post_element.inner_text()
            
            # 排除非真实帖子内容
            if "桌面通知" in element_text or "声音提醒" in element_text:
                return {"is_valid_post": False, "section": "未知板块"}
            
            # 初始化结果
            result = {
                "title": "未知标题",
                "date": "未知日期",
                "time": "未知时间",
                "comment_count": 0,
                "element": post_element,
                "is_valid_post": False,
                "section": "未知板块"  # 确保有板块字段
            }
            
            # 首先提取时间，判断是否是有效的帖子
            time_match = re.search(r'(\d{2}:\d{2}:\d{2})', element_text)
            if time_match:
                result["time"] = time_match.group(1)
            else:
                # 如果没有时间，可能不是有效帖子
                return {"is_valid_post": False, "section": "未知板块"}
            
            # 提取日期 (YYYY.MM.DD)
            date_match = re.search(r'(\d{4}\.\d{2}\.\d{2})', element_text)
            if date_match:
                result["date"] = date_match.group(1)
            
            # 尝试从标题格式判断是否为帖子
            is_likely_post = False
            
            # 按优先级提取标题
            title_patterns = [
                r'【([^】]+)】',  # 尖括号格式
                r'\[([^\]]+)\]',  # 方括号格式
                r'(\d{2}:\d{2}:\d{2})\s+(.+?)\s+\d+阅读'  # 时间后跟随的文本
            ]
            
            for pattern in title_patterns:
                match = re.search(pattern, element_text)
                if match:
                    result["title"] = match.group(1) if pattern != title_patterns[2] else match.group(2)
                    is_likely_post = True
                    break
            
            # 如果没有从括号中提取到标题，尝试从冒号后提取
            if result["title"] == "未知标题" and "：" in element_text:
                colon_match = re.search(r'([^：]+)：\s*(.+?)(?=\s*\d|\s*$)', element_text)
                if colon_match:
                    # 可能是 "公司名：标题内容" 的格式
                    result["title"] = colon_match.group(2).strip()
                    if len(result["title"]) > 3:  # 确保提取的内容不是太短
                        is_likely_post = True
            
            # 如果仍然没有标题但有时间，尝试从时间后面提取内容作为标题
            if result["title"] == "未知标题":
                time_str = result["time"]
                time_content_match = re.search(re.escape(time_str) + r'\s+(.+?)(?=\s*\d|\s*$)', element_text)
                if time_content_match:
                    result["title"] = time_content_match.group(1).strip()
                    if len(result["title"]) > 3:  # 确保提取的内容不是太短
                        is_likely_post = True
            
            # 提取评论数
            comment_patterns = [
                r'评论\s*[(\[](\d+)[)\]]',  # 评论(N) 或 评论[N]
                r'评论[：:]\s*(\d+)'        # 评论: N 或 评论：N
            ]
            
            for pattern in comment_patterns:
                match = re.search(pattern, element_text)
                if match:
                    try:
                        result["comment_count"] = int(match.group(1))
                        is_likely_post = True  # 有评论计数，更可能是帖子
                        break
                    except ValueError:
                        pass
            
            # 如果元素包含"阅读"或"分享"，更可能是帖子
            if "阅读" in element_text or "分享" in element_text:
                is_likely_post = True
            
            # 只有确认是有效帖子，且没有找到日期时，才使用当天日期
            if is_likely_post and result["date"] == "未知日期":
                import datetime
                today = datetime.datetime.now().strftime("%Y.%m.%d")
                result["date"] = today

            # 验证有效性 - 即使没有日期，只要有时间和标题，也认为是有效帖子
            if is_likely_post and result["time"] != "未知时间" and result["title"] != "未知标题":
                result["is_valid_post"] = True
                
            return result
            
        except Exception as e:
            logger.error(f"提取帖子信息时出错: {e}")
            return {"is_valid_post": False, "section": "未知板块"}
    
    def extract_posts_from_page(self, page) -> Tuple[List[Dict[str, Any]], bool]:
        """
        从当前页面提取所有帖子信息
        
        Args:
            page: 页面对象
            
        Returns:
            帖子信息列表和是否达到截止日期的标志
        """
        posts = []
        seen_titles = set()  # 用于去重
        reached_cutoff = False
        
        try:
            # 获取当前URL以确定所在板块
            current_url = page.url
            section = "未知板块"
            
            # 通过URL确定板块
            if "kanpan" in current_url.lower() or "看盘" in current_url:
                section = "看盘"
            elif "company" in current_url.lower() or "公司" in current_url:
                section = "公司"
            
            # 尝试从页面元素获取板块信息
            try:
                tab_elements = page.query_selector_all("[role='tab'][aria-selected='true'], .tab.active, .selected-tab")
                for tab in tab_elements:
                    tab_text = tab.inner_text().strip()
                    if tab_text in ["看盘", "公司"]:
                        section = tab_text
                        break
            except Exception:
                # 如果无法从元素获取，保持默认值
                pass
            
            logger.info(f"当前页面URL: {current_url}, 识别板块: {section}")
            
            # 财联社电报项的CSS选择器
            selectors = [
                ".telegraph-item",             # 标准电报项
                "div.box", "div.red-box",      # 框式布局
                "[class*='telegraph']",        # 包含telegraph的元素
                "[class*='post']",             # 帖子元素
                "[class*='item']"              # 通用列表项
            ]
            
            # 尝试通过选择器查找电报项
            for selector in selectors:
                elements = page.query_selector_all(selector)
                if elements and len(elements) > 3:  # 确保选择器找到了足够多的元素
                    logger.info(f"使用选择器 '{selector}' 找到 {len(elements)} 个电报项")
                    
                    for element in elements:
                        # 提取帖子信息
                        post_info = self.extract_post_info(element)
                        
                        # 添加板块信息
                        post_info["section"] = section
                        
                        # 检查是否有效且不重复
                        if post_info.get("is_valid_post", False) and post_info["title"] not in seen_titles:
                            posts.append(post_info)
                            seen_titles.add(post_info["title"])
                    
                    # 如果找到了足够多的帖子，停止尝试
                    if len(posts) >= 5:
                        break
            
            # 如果常规选择器没有找到足够的帖子，尝试使用更通用的方法
            if len(posts) < 3:
                logger.info("常规选择器未找到足够的帖子，尝试使用更通用的方法")
                
                # 使用JavaScript查找可能的电报项
                js_items = page.evaluate("""
                    () => {
                        return Array.from(document.querySelectorAll('*')).filter(el => {
                            const text = el.innerText || '';
                            return text.match(/\\d{4}\\.\\d{2}\\.\\d{2}/) && 
                                   text.match(/\\d{2}:\\d{2}:\\d{2}/) &&
                                   (text.includes('评论') || text.includes('分享'));
                        }).map(el => {
                            const rect = el.getBoundingClientRect();
                            return {
                                top: rect.top,
                                height: rect.height,
                                element: el
                            };
                        });
                    }
                """)
                
                for item in js_items:
                    element = page.evaluate("el => el", item["element"])
                    post_info = self.extract_post_info(element)
                    
                    if post_info.get("is_valid_post", False) and post_info["title"] not in seen_titles:
                        posts.append(post_info)
                        seen_titles.add(post_info["title"])
            
            logger.info(f"总共提取到 {len(posts)} 个有效帖子")
            return posts, reached_cutoff
            
        except Exception as e:
            logger.error(f"提取帖子时出错: {e}")
            return [], False
    
    def load_more_posts(self, page) -> bool:
        """
        加载更多帖子
        
        Args:
            page: 页面对象
            
        Returns:
            是否成功加载更多
        """
        try:
            # 记录加载前的页面高度和内容数量
            old_height = page.evaluate("document.body.scrollHeight")
            
            # 1. 尝试点击"加载更多"按钮
            load_more_selectors = [
                "button:has-text('加载更多')",
                "a:has-text('加载更多')",
                ".load-more", 
                "[class*='more']"
            ]
            
            for selector in load_more_selectors:
                load_more_btns = page.query_selector_all(selector)
                for btn in load_more_btns:
                    if btn.is_visible():
                        logger.info(f"找到加载更多按钮: {selector}")
                        btn.scroll_into_view_if_needed()
                        time.sleep(0.5)
                        btn.click()
                        time.sleep(2)
                        
                        # 检查页面是否变化
                        new_height = page.evaluate("document.body.scrollHeight")
                        if new_height > old_height:
                            logger.info("成功加载更多内容")
                            return True
            
            # 2. 如果没有找到按钮，尝试滚动到页面底部
            logger.info("未找到加载更多按钮，尝试滚动到页面底部")
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)
            
            # 检查页面是否变化
            new_height = page.evaluate("document.body.scrollHeight")
            if new_height > old_height:
                logger.info("通过滚动成功加载更多内容")
                return True
                
            return False
            
        except Exception as e:
            logger.error(f"加载更多帖子时出错: {e}")
            return False 