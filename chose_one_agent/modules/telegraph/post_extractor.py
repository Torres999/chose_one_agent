# -*- coding: utf-8 -*-
import logging
import re
import time
import datetime
from typing import List, Dict, Any, Tuple

# 配置日志
logger = logging.getLogger(__name__)

class PostExtractor:
    """帖子内容提取器类，用于从页面中提取帖子信息"""
    
    def __init__(self):
        # 定义用于识别电报元素的CSS选择器
        self.selectors = {
            # 电报列表的可能选择器
            "list_selectors": [
                ".telegraph-list",
                ".telegraph-container",
                ".telegraph-feed",
                ".telegraph-stream",
                ".telegraph-content",
                "#telegraph-list",
                "[class*='telegraph-list']",
                "[class*='telegraph']",
            ],
            
            # 电报项的可能选择器
            "item_selectors": [
                ".telegraph-item",
                ".item-card",
                ".post-item",
                ".feed-item",
                ".news-item",
                ".card-item",
                ".article-item",
                "[class*='item-']",
                "[class*='-item']"
            ]
        }
    
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
            if "桌面通知" in element_text or "声音提醒" in element_text or "语音电报" in element_text:
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
            
            # 提取日期 - 增加对页面显示格式的支持 (YYYY.MM.DD 或 YYYY-MM-DD)
            date_patterns = [
                r'(\d{4}\.\d{2}\.\d{2})',  # YYYY.MM.DD
                r'(\d{4}-\d{2}-\d{2})',    # YYYY-MM-DD
                r'(\d{4})\.(\d{2})\.(\d{2})',  # 年月日分开格式
                r'(\d{4})-(\d{2})-(\d{2})'    # 年月日分开格式
            ]
            
            for pattern in date_patterns:
                date_match = re.search(pattern, element_text)
                if date_match:
                    if len(date_match.groups()) == 3:  # 年月日分开格式
                        result["date"] = f"{date_match.group(1)}.{date_match.group(2)}.{date_match.group(3)}"
                    else:
                        result["date"] = date_match.group(1).replace('-', '.')
                    break
            
            # 如果未找到日期，设置为当天日期
            if result["date"] == "未知日期":
                today = datetime.datetime.now().strftime("%Y.%m.%d")
                result["date"] = today
            
            # 首先提取时间，判断是否是有效的帖子 - 支持不同的时间格式
            time_patterns = [
                r'(\d{2}:\d{2}:\d{2})',  # HH:MM:SS
                r'(\d{2}:\d{2})',        # HH:MM
                r'(\d{2}):(\d{2}):(\d{2})',  # 时分秒分开格式
                r'(\d{2}):(\d{2})'          # 时分分开格式
            ]
            
            for pattern in time_patterns:
                time_match = re.search(pattern, element_text)
                if time_match:
                    if len(time_match.groups()) > 1:  # 时分秒分开格式
                        if len(time_match.groups()) == 3:  # HH:MM:SS
                            result["time"] = f"{time_match.group(1)}:{time_match.group(2)}:{time_match.group(3)}"
                        else:  # HH:MM
                            result["time"] = f"{time_match.group(1)}:{time_match.group(2)}:00"
                    else:
                        result["time"] = time_match.group(1)
                        if ":" in result["time"] and result["time"].count(":") == 1:
                            # 只有时分，添加秒数
                            result["time"] += ":00"
                    break
            
            if result["time"] == "未知时间":
                # 如果没有时间，可能不是有效帖子
                return {"is_valid_post": False, "section": "未知板块"}
            
            # 尝试从标题格式判断是否为帖子
            is_likely_post = False
            
            # 按优先级提取标题
            title_patterns = [
                r'(\d{2}:\d{2}:\d{2})\s+【([^】]+)】', # 时间 + 【标题】
                r'(\d{2}:\d{2})\s+【([^】]+)】',      # 时间 + 【标题】(没有秒)
                r'【([^】]+)】',                      # 【标题】
                r'\[([^\]]+)\]',                     # [标题]
                r'(\d{2}:\d{2}:\d{2})\s+(.+?)(?=\s*\d+阅读|\s*$)',  # 时间后跟随的文本
                r'(\d{2}:\d{2})\s+(.+?)(?=\s*\d+阅读|\s*$)'         # 时间后跟随的文本(没有秒)
            ]
            
            for pattern in title_patterns:
                match = re.search(pattern, element_text)
                if match:
                    if ":" in pattern and pattern.count(':') >= 1:  # 包含时间的模式
                        # 确定title是哪个匹配组
                        if '【' in pattern or '[' in pattern:  # 有括号
                            result["title"] = match.group(2)
                        else:  # 没有括号
                            result["title"] = match.group(2)
                    else:  # 不包含时间的模式
                        result["title"] = match.group(1)
                    
                    is_likely_post = True
                    break
            
            # 如果没有从括号中提取到标题，尝试从冒号后提取
            if result["title"] == "未知标题" and ("：" in element_text or ":" in element_text):
                colon_match = re.search(r'([^：:]+)[：:](.+?)(?=\s*\d|\s*$)', element_text)
                if colon_match:
                    # 可能是 "公司名：标题内容" 的格式
                    result["title"] = colon_match.group(2).strip()
                    if len(result["title"]) > 3:  # 确保提取的内容不是太短
                        is_likely_post = True
            
            # 如果仍然没有标题但有时间，尝试从时间后面提取内容作为标题
            if result["title"] == "未知标题":
                time_str = result["time"]
                time_content_match = re.search(re.escape(time_str) + r'\s+(.+?)(?=\s*\d+阅读|\s*评论|\s*分享|\s*$)', element_text)
                if time_content_match:
                    result["title"] = time_content_match.group(1).strip()
                    if len(result["title"]) > 3:  # 确保提取的内容不是太短
                        is_likely_post = True
            
            # 提取评论数
            comment_patterns = [
                r'评论\s*[(\[](\d+)[)\]]',  # 评论(N) 或 评论[N]
                r'评论[：:]\s*(\d+)',        # 评论: N 或 评论：N
                r'评论\((\d+)\)',           # 评论(N)
                r'评论\s*(\d+)'             # 评论 N
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
                
            # 获取帖子内容
            # 尝试提取报文内容，特别是对于含有"报文"的标题
            if "报文" in element_text or "电报" in element_text:
                # 获取标题后的内容作为报文内容
                title = result["title"]
                if title != "未知标题" and title in element_text:
                    content_parts = element_text.split(title, 1)
                    if len(content_parts) > 1:
                        # 移除评论、阅读、分享等信息
                        content = content_parts[1]
                        # 清理内容
                        content = re.sub(r'\s*\d+\s*阅读.*$', '', content, flags=re.DOTALL)
                        content = re.sub(r'\s*\d+\s*评论.*$', '', content, flags=re.DOTALL)
                        content = re.sub(r'\s*\d+\s*分享.*$', '', content, flags=re.DOTALL)
                        content = content.strip()
                        if content:
                            result["content"] = content
                            # 如果标题中没有明确指出是报文，但内容看起来像报文，则将"报文"添加到标题
                            if "报文" not in result["title"] and len(content) > 50:
                                result["title"] = "【报文】" + result["title"]

            # 验证有效性 - 即使没有日期，只要有时间和标题，也认为是有效帖子
            if is_likely_post and result["time"] != "未知时间" and result["title"] != "未知标题":
                result["is_valid_post"] = True
                
            # 如果有时间并且文本包含"成交额达"、"个股"或"行情"等股市相关词汇，认为是"看盘"板块
            if (result["time"] != "未知时间" and 
                ("成交额" in element_text or "涨停" in element_text or "跌停" in element_text or 
                 "个股" in element_text or "行情" in element_text or "A股" in element_text or 
                 "板块" in element_text)):
                result["section"] = "看盘"
                if result["title"] != "未知标题":
                    result["is_valid_post"] = True
            
            # 如果包含公司、业绩、营收等企业相关词汇，认为是"公司"板块
            if (result["time"] != "未知时间" and 
                ("公司" in element_text or "集团" in element_text or "获批" in element_text or 
                 "业绩" in element_text or "营收" in element_text or "利润" in element_text)):
                result["section"] = "公司"
                if result["title"] != "未知标题":
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
                # 尝试不同的选择器来确定当前板块
                tab_selectors = [
                    "[role='tab'][aria-selected='true']", 
                    ".tab.active", 
                    ".selected-tab",
                    ".nav-tabs .active",
                    ".sub-tabs .active"
                ]
                
                for selector in tab_selectors:
                    tab_elements = page.query_selector_all(selector)
                    for tab in tab_elements:
                        tab_text = tab.inner_text().strip()
                        if tab_text in ["看盘", "公司", "全部", "加红", "港美股", "基金", "提醒"]:
                            section = tab_text
                            logger.info(f"从选项卡识别到板块: {section}")
                            break
                    if section != "未知板块":
                        break
            except Exception as e:
                logger.debug(f"从元素获取板块信息失败: {e}")
                # 如果无法从元素获取，保持默认值
                pass
            
            logger.info(f"当前页面URL: {current_url}, 识别板块: {section}")
            
            # ===== 策略1: 直接查找单个电报项 =====
            all_posts_elements = []
            
            # 查找包含时间格式和电报相关特征的元素
            time_elements = page.query_selector_all("div, article, section, li")
            for element in time_elements:
                try:
                    text = element.inner_text()
                    # 检查是否包含时间格式和电报相关特征
                    if (re.search(r'\d{2}:\d{2}:\d{2}', text) or re.search(r'\d{2}:\d{2}', text)) and len(text) > 10:
                        if ("【" in text or "[" in text or "评论" in text or "分享" in text or "阅读" in text):
                            all_posts_elements.append(element)
                except Exception:
                    continue
                    
            logger.info(f"通过时间格式直接找到 {len(all_posts_elements)} 个可能的电报项")
            
            # 筛选出最合适的元素，排除太大的容器和太小的元素
            filtered_elements = []
            for element in all_posts_elements:
                try:
                    # 获取元素尺寸信息
                    rect = page.evaluate("""(element) => {
                        const rect = element.getBoundingClientRect();
                        return {
                            width: rect.width,
                            height: rect.height,
                            text: element.innerText.length
                        };
                    }""", element)
                    
                    # 电报项通常有适中的高度和文本长度
                    if (20 < rect["height"] < 200) and (20 < rect["text"] < 1000):
                        filtered_elements.append(element)
                except Exception:
                    continue
            
            logger.info(f"筛选后得到 {len(filtered_elements)} 个合适的电报项元素")
            
            # 如果找到了适合的元素，提取信息
            if filtered_elements:
                for element in filtered_elements:
                    post_info = self.extract_post_info(element)
                    post_info["section"] = section  # 设置板块信息
                    
                    # 检查是否有效且不重复
                    if post_info.get("is_valid_post", False) and post_info["title"] not in seen_titles:
                        posts.append(post_info)
                        seen_titles.add(post_info["title"])
            
            # ===== 策略2: 使用标准选择器 =====
            # 只有在策略1未找到足够帖子时才尝试
            if len(posts) < 3:
                # 电报网站电报列表的可能选择器
                list_selectors = [
                    "div[class*='telegraph-list']",
                    ".telegraph-container",
                    ".news-list",
                    ".feed-list",
                    ".posts-list"
                ]
                
                for list_selector in list_selectors:
                    telegraph_elements = page.query_selector_all(list_selector)
                    logger.info(f"使用选择器 '{list_selector}' 找到 {len(telegraph_elements)} 个telegraph-list元素")
                    
                    if telegraph_elements and len(telegraph_elements) > 0:
                        for list_element in telegraph_elements:
                            # 从列表元素中查找子项
                            item_selectors = [
                                "div[class*='item']",
                                "div[class*='post']",
                                "div[class*='article']",
                                "div[class*='telegraph']",
                                "li", "article"
                            ]
                            
                            for item_selector in item_selectors:
                                try:
                                    items = list_element.query_selector_all(item_selector)
                                    if items and len(items) > 0:
                                        logger.info(f"在列表中使用 '{item_selector}' 选择器找到 {len(items)} 个电报项")
                                        
                                        for item in items:
                                            post_info = self.extract_post_info(item)
                                            post_info["section"] = section
                                            
                                            if post_info.get("is_valid_post", False) and post_info["title"] not in seen_titles:
                                                posts.append(post_info)
                                                seen_titles.add(post_info["title"])
                                except Exception as e:
                                    logger.debug(f"处理列表项时出错: {e}")
                        
                        # 如果已经找到了足够多的帖子，停止尝试
                        if len(posts) >= 5:
                            break
            
            # ===== 策略3: 直接使用通用选择器 =====
            # 只有在前两种策略未找到足够帖子时才尝试
            if len(posts) < 3:
                # 电报网站电报项的其他可能选择器
                selectors = [
                    ".telegraph-item",             # 标准电报项
                    "div.box", "div.red-box",      # 框式布局
                    "[class*='telegraph']",        # 包含telegraph的元素
                    "[class*='post']",             # 帖子元素
                    "[class*='item']",             # 通用列表项
                    "[class*='news']",             # 新闻项
                    "article", "li.item"           # 通用文章和列表项
                ]
                
                # 尝试通过选择器查找电报项
                for selector in selectors:
                    elements = page.query_selector_all(selector)
                    if elements and len(elements) > 2:  # 确保选择器找到了足够多的元素
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
            
            # ===== 策略4: JavaScript查找 =====
            # 当其他方法都失败时使用
            if len(posts) < 2:
                logger.info("常规选择器未找到足够的帖子，尝试使用JavaScript查找")
                
                # 使用JavaScript查找可能的电报项
                js_items = page.evaluate("""
                    () => {
                        // 查找具有时间格式和电报特征的元素
                        return Array.from(document.querySelectorAll('*')).filter(el => {
                            const text = el.innerText || '';
                            // 包含时间格式
                            const hasTimeFormat = text.match(/\\d{2}:\\d{2}(:\\d{2})?/);
                            // 包含电报特征
                            const hasTelegraphFeatures = text.includes('评论') || 
                                                         text.includes('分享') || 
                                                         text.includes('阅读') ||
                                                         text.includes('【') ||
                                                         text.includes('】');
                            // 内容长度适中
                            const hasProperLength = text.length > 20 && text.length < 1000;
                            
                            return hasTimeFormat && hasTelegraphFeatures && hasProperLength;
                        }).map(el => {
                            const rect = el.getBoundingClientRect();
                            // 筛选适当尺寸的元素
                            if (rect.height > 20 && rect.height < 200) {
                                return {
                                    element: el,
                                    height: rect.height,
                                    width: rect.width,
                                    text: el.innerText
                                };
                            }
                            return null;
                        }).filter(item => item !== null);
                    }
                """)
                
                for item in js_items:
                    try:
                        element = page.evaluate("el => el", item["element"])
                        post_info = self.extract_post_info(element)
                        
                        # 添加板块信息
                        post_info["section"] = section
                    
                        if post_info.get("is_valid_post", False) and post_info["title"] not in seen_titles:
                            posts.append(post_info)
                            seen_titles.add(post_info["title"])
                    except Exception as e:
                        logger.debug(f"处理JavaScript找到的元素时出错: {e}")
            
            logger.info(f"总共提取到 {len(posts)} 个有效帖子")
            return posts, reached_cutoff
            
        except Exception as e:
            logger.error(f"提取帖子时出错: {e}")
            return posts, reached_cutoff
    
    def load_more_posts(self, page) -> bool:
        """
        尝试加载更多帖子
        
        Args:
            page: Playwright页面对象
            
        Returns:
            是否成功加载了更多内容
        """
        try:
            # 记录当前页面高度
            old_height = page.evaluate("document.body.scrollHeight")
            
            # 1. 尝试找到并点击"加载更多"按钮
            load_more_selectors = [
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