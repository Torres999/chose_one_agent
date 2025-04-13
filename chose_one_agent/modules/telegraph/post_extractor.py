# -*- coding: utf-8 -*-
import logging
import re
import time
import datetime
from typing import List, Dict, Any, Tuple

# 配置日志
logger = logging.getLogger(__name__)

class PostExtractor:
    """
    帖子内容提取器类，用于从页面中提取帖子信息
    """
    
    def extract_post_info(self, post_element) -> Dict[str, Any]:
        """
        从帖子元素中提取信息

        Args:
            post_element: 帖子的DOM元素

        Returns:
            包含帖子信息的字典
        """
        try:
            # 获取元素的HTML和文本，用于调试
            html = post_element.inner_html()
            element_text = post_element.inner_text()
            
            # 记录提取的原始文本内容
            logger.debug(f"提取帖子原始文本内容: {element_text[:100]}...")
            
            # 排除非真实帖子内容
            if "桌面通知" in element_text or "声音提醒" in element_text:
                return {
                    "title": "非帖子内容",
                    "date": "",
                    "time": "",
                    "comment_count": 0,
                    "element": None,
                    "is_valid_post": False
                }
            
            # 从文本内容中提取【】包围的标题
            title = "无标题"
            title_match = re.search(r'【(.*?)】', element_text)
            if title_match:
                title = title_match.group(1)
                logger.debug(f"从内容中提取到的标题: {title}")
            
            # 提取日期和时间
            date_str = "未知日期"
            time_str = "未知时间"
            
            # 匹配多种日期格式
            # 1. 标准格式: 2025.04.11 星期五
            date_match = re.search(r'(\d{4}\.\d{2}\.\d{2})\s*星期[一二三四五六日]', element_text)
            if date_match:
                date_str = date_match.group(1)
            
            # 2. 尝试其他常见日期格式
            if date_str == "未知日期":
                date_patterns = [
                    r'(\d{4}\.\d{2}\.\d{2})',  # 2025.04.11
                    r'(\d{4}-\d{2}-\d{2})',     # 2025-04-11
                    r'(\d{4}/\d{2}/\d{2})',     # 2025/04/11
                ]
                
                for pattern in date_patterns:
                    date_match = re.search(pattern, element_text)
                    if date_match:
                        date_str = date_match.group(1).replace('-', '.').replace('/', '.')
                        break
                
                # 如果还是没找到，尝试提取月日格式
                if date_str == "未知日期":
                    month_day_match = re.search(r'(\d{1,2})月(\d{1,2})日', element_text)
                    if month_day_match:
                        month, day = month_day_match.groups()
                        year = datetime.datetime.now().year
                        date_str = f"{year}.{int(month):02d}.{int(day):02d}"
            
            # 匹配时间格式：14:05:39 或 14:05
            time_match = re.search(r'(\d{2}:\d{2}(:\d{2})?)', element_text)
            if time_match:
                time_str = time_match.group(1)
            
            # 如果仍然没有找到日期和时间，尝试找到一个连续的数字和冒号组合
            if date_str == "未知日期" and time_str == "未知时间":
                datetime_match = re.search(r'(\d{1,4}[/\-\.]\d{1,2}[/\-\.]\d{1,4}[\s\S]+?\d{1,2}:\d{1,2})', element_text)
                if datetime_match:
                    dt_str = datetime_match.group(1)
                    logger.debug(f"找到日期时间组合: {dt_str}")
                    
                    # 提取日期部分
                    date_part = re.search(r'(\d{1,4}[/\-\.]\d{1,2}[/\-\.]\d{1,4})', dt_str)
                    if date_part:
                        date_parts = re.split(r'[/\-\.]', date_part.group(1))
                        if len(date_parts) == 3:
                            # 确保年份是4位数
                            if len(date_parts[0]) != 4 and len(date_parts[2]) == 4:
                                # 假设格式是DD/MM/YYYY
                                date_str = f"{date_parts[2]}.{int(date_parts[1]):02d}.{int(date_parts[0]):02d}"
                            else:
                                # 假设格式是YYYY/MM/DD
                                date_str = f"{date_parts[0]}.{int(date_parts[1]):02d}.{int(date_parts[2]):02d}"
                    
                    # 提取时间部分
                    time_part = re.search(r'(\d{1,2}:\d{1,2}(:\d{1,2})?)', dt_str)
                    if time_part:
                        time_str = time_part.group(1)
            
            # 提取评论数
            comment_count = 0
            comment_match = re.search(r'评论\((\d+)\)', element_text)
            if comment_match:
                try:
                    comment_count = int(comment_match.group(1))
                except ValueError:
                    comment_count = 0
            
            # 如果仍然没找到评论数，尝试其他格式
            if comment_count == 0:
                comment_match2 = re.search(r'评论[：:]\s*(\d+)', element_text)
                if comment_match2:
                    try:
                        comment_count = int(comment_match2.group(1))
                    except ValueError:
                        comment_count = 0
            
            # 如果没有匹配到标题但有内容，使用内容的前30个字符作为标题
            if title == "无标题" and len(element_text.strip()) > 30:
                # 去除可能的日期时间
                cleaned_text = re.sub(r'\d{4}\.\d{2}\.\d{2}\s*星期[一二三四五六日]', '', element_text)
                cleaned_text = re.sub(r'\d{2}:\d{2}(:\d{2})?', '', cleaned_text)
                # 取前30个字符
                title = cleaned_text.strip()[:30].strip() + "..."
            
            # 记录提取到的信息
            logger.debug(f"提取到的帖子信息 - 标题: {title}, 日期: {date_str}, 时间: {time_str}, 评论数: {comment_count}")
            
            return {
                "title": title,
                "date": date_str,
                "time": time_str,
                "comment_count": comment_count,
                "element": post_element,  # 保存原始元素，以便后续处理
                "is_valid_post": True
            }
            
        except Exception as e:
            logger.error(f"提取帖子信息时出错: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                "title": "错误",
                "date": "未知日期",
                "time": "未知时间",
                "comment_count": 0,
                "element": None,
                "is_valid_post": False
            }
    
    def extract_posts_from_page(self, page) -> Tuple[List[Dict[str, Any]], bool]:
        """
        从当前页面提取所有帖子信息
        
        Args:
            page: 页面对象
            
        Returns:
            帖子信息列表和是否达到截止日期的标志
        """
        posts = []
        seen_titles = set()  # 用于去重，避免同一帖子被多个选择器重复添加
        reached_cutoff = False
        
        try:
            # 优化选择器，专注于WEB版本
            telegraph_item_selectors = [
                ".telegraph-item",
                "[class*='telegraph-item']",
                ".article-item",
                "[class*='article-item']",
                ".post-item",
                "[class*='post-item']",
                ".telegraph-content-box",
                ".m-b-15",
                "div.m-b-15",
                "article",
                ".item"
            ]
            
            items_found = False
            
            for selector in telegraph_item_selectors:
                try:
                    items = page.query_selector_all(selector)
                    logger.info(f"使用选择器 '{selector}' 找到 {len(items)} 个可能的帖子元素")
                    
                    if items and len(items) > 0:
                        items_found = True
                        
                        # 提取帖子信息
                        for item in items:
                            # 获取元素文本内容
                            element_text = item.inner_text().strip()
                            
                            # 如果元素内容太少，可能不是有效帖子
                            if len(element_text) < 10:
                                continue
                                
                            # 排除页面顶部的提示信息
                            if "电报持续更新" in element_text:
                                continue
                                
                            # 提取帖子信息
                            post_info = self.extract_post_info(item)
                            
                            # 跳过无效的帖子
                            if not post_info.get("is_valid_post", False):
                                continue
                            
                            # 如果标题已经处理过，跳过
                            if post_info["title"] in seen_titles:
                                continue
                            
                            # 添加到结果列表
                            posts.append(post_info)
                            seen_titles.add(post_info["title"])
                
                except Exception as e:
                    logger.error(f"使用选择器'{selector}'提取帖子时出错: {e}")
                    continue
                
                # 如果找到了足够的帖子，不再尝试其他选择器
                if len(posts) > 0:
                    break
                    
            # 如果没有找到任何帖子元素，尝试直接解析页面内容
            if not items_found or len(posts) == 0:
                logger.warning("未能通过常规选择器找到帖子，尝试直接解析页面内容")
                
                # 使用JavaScript直接分析页面结构
                try:
                    page_posts = page.evaluate("""
                        () => {
                            // 查找所有可能的帖子元素
                            const possibleItems = Array.from(document.querySelectorAll('div, article'))
                                .filter(el => {
                                    // 尝试识别可能的帖子元素特征
                                    const text = el.textContent;
                                    const hasTitle = text.includes('【') && text.includes('】');
                                    const hasDateTime = /\\d{2}:\\d{2}/.test(text);
                                    const isReasonableSize = el.offsetHeight > 50 && el.offsetWidth > 200;
                                    
                                    return (hasTitle || hasDateTime) && isReasonableSize;
                                });
                            
                            return possibleItems.map(el => {
                                return {
                                    html: el.outerHTML,
                                    text: el.textContent.trim(),
                                    rect: el.getBoundingClientRect()
                                };
                            });
                        }
                    """)
                    
                    logger.info(f"JavaScript分析找到 {len(page_posts)} 个可能的帖子元素")
                    
                    # 根据JavaScript分析结果，直接构建帖子信息
                    for post_data in page_posts:
                        post_text = post_data["text"]
                        
                        # 提取标题
                        title = "无标题"
                        title_match = re.search(r'【(.*?)】', post_text)
                        if title_match:
                            title = title_match.group(1)
                        
                        # 提取日期和时间
                        date_str = "未知日期"
                        time_str = "未知时间"
                        
                        date_match = re.search(r'(\d{4}\.\d{2}\.\d{2})', post_text)
                        if date_match:
                            date_str = date_match.group(1)
                            
                        time_match = re.search(r'(\d{2}:\d{2}(:\d{2})?)', post_text)
                        if time_match:
                            time_str = time_match.group(1)
                            
                        # 跳过已处理的标题
                        if title in seen_titles:
                            continue
                            
                        # 创建帖子信息
                        post_info = {
                            "title": title,
                            "date": date_str,
                            "time": time_str,
                            "comment_count": 0,
                            "element": None,  # JS分析模式下没有DOM元素
                            "is_valid_post": True
                        }
                        
                        # 添加到结果列表
                        posts.append(post_info)
                        seen_titles.add(title)
                        
                except Exception as e:
                    logger.error(f"执行JavaScript分析页面结构时出错: {e}")
            
            logger.info(f"总共找到 {len(posts)} 条可能符合条件的帖子")
            
            return posts, reached_cutoff
        
        except Exception as e:
            logger.error(f"提取帖子时出错: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return [], reached_cutoff
    
    def load_more_posts(self, page) -> bool:
        """
        加载更多帖子
        
        Args:
            page: 页面对象
            
        Returns:
            是否成功加载更多
        """
        try:
            # 获取当前页面高度和内容数量作为基准
            old_height = page.evaluate("document.body.scrollHeight")
            old_content_count = len(page.query_selector_all(".telegraph-item, [class*='telegraph-item'], .article-item, [class*='article-item']"))
            logger.info(f"当前页面高度: {old_height}px, 内容数量: {old_content_count}")
            
            # 首先尝试点击"加载更多"按钮
            logger.info("尝试点击'加载更多'按钮")
            load_more_selectors = [
                "button:has-text('加载更多')",
                "a:has-text('加载更多')",
                "div:has-text('加载更多')",
                "span:has-text('加载更多')",
                "button:has-text('更多')",
                "a:has-text('更多')",
                "div:has-text('更多')",
                "[class*='load-more']",
                "[class*='loadMore']",
                "[class*='more-btn']",
                "[class*='moreBtn']",
                "[class*='load_more']",
                "[id*='load-more']",
                "[id*='loadMore']",
                ".load-more", 
                ".loadMore",
                ".more"
            ]
            
            # 尝试点击加载更多按钮
            for selector in load_more_selectors:
                try:
                    load_more_btns = page.query_selector_all(selector)
                    if load_more_btns and len(load_more_btns) > 0:
                        for btn in load_more_btns:
                            # 判断按钮是否可见和可点击
                            if btn.is_visible():
                                logger.info(f"找到加载更多按钮，使用选择器: {selector}")
                                # 确保按钮在视图中
                                btn.scroll_into_view_if_needed()
                                time.sleep(0.5)
                                btn.click()
                                # 等待页面加载
                                time.sleep(2)
                                
                                # 检查内容是否增加
                                new_height = page.evaluate("document.body.scrollHeight")
                                new_content_count = len(page.query_selector_all(".telegraph-item, [class*='telegraph-item'], .article-item, [class*='article-item']"))
                                
                                if new_height > old_height + 5 or new_content_count > old_content_count:
                                    logger.info(f"点击加载更多按钮成功: 内容从 {old_content_count} 增加到 {new_content_count} 个元素")
                                    return True
                except Exception as e:
                    logger.debug(f"点击加载更多按钮'{selector}'时出错: {e}")
                    continue

            # 如果没有找到加载更多按钮，尝试直接滚动页面
            logger.info("尝试滚动页面触发加载更多")
            
            # 直接滚动到页面底部
            page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            
            # 检查内容是否增加
            new_height = page.evaluate("document.body.scrollHeight")
            new_content_count = len(page.query_selector_all(".telegraph-item, [class*='telegraph-item'], .article-item, [class*='article-item']"))
            
            if new_height > old_height + 5 or new_content_count > old_content_count:
                logger.info(f"滚动页面成功: 内容从 {old_content_count} 增加到 {new_content_count} 个元素")
                return True
                
            # 尝试更高级的JavaScript解决方案
            logger.info("尝试使用JavaScript分析页面结构并触发加载更多")
            success = page.evaluate("""
                () => {
                    // 定义可能的加载更多按钮选择器
                    const loadMoreSelectors = [
                        '.load-more', '.loadMore', '.more-btn', '.moreBtn',
                        '[class*="load-more"]', '[class*="loadMore"]',
                        'button:contains("加载更多")', 'a:contains("加载更多")',
                        'div:contains("加载更多")', 'span:contains("加载更多")',
                        'button:contains("更多")', 'a:contains("更多")',
                        '[class*="more"]'
                    ];
                    
                    // 尝试找到并点击加载更多按钮
                    for (const selector of loadMoreSelectors) {
                        const elements = document.querySelectorAll(selector);
                        for (const element of elements) {
                            if (element.offsetParent !== null) {  // 检查元素是否可见
                                console.log('找到加载更多按钮:', element);
                                element.scrollIntoView({behavior: 'smooth', block: 'center'});
                                setTimeout(() => element.click(), 500);
                                return true;
                            }
                        }
                    }
                    
                    // 如果找不到按钮，尝试滚动页面
                    window.scrollTo({
                        top: document.body.scrollHeight,
                        behavior: 'smooth'
                    });
                    
                    // 尝试触发常见的滚动事件
                    window.dispatchEvent(new Event('scroll'));
                    document.dispatchEvent(new Event('scroll'));
                    
                    // 查找并调用可能的加载更多函数
                    const possibleFunctions = [
                        'loadMore', 'loadMoreData', 'appendMore', 'nextPage',
                        'moreData', 'getMore', 'fetchMore', 'loadmoreHandle'
                    ];
                    
                    // 在全局范围内查找
                    for (const fnName of possibleFunctions) {
                        if (typeof window[fnName] === 'function') {
                            try {
                                console.log(`尝试调用全局函数: ${fnName}`);
                                window[fnName]();
                                return true;
                            } catch (e) {
                                console.log(`调用函数 ${fnName} 失败:`, e);
                            }
                        }
                    }
                    
                    // 尝试查找可能的加载更多元素并模拟点击
                    const possibleLoadMoreElements = Array.from(document.querySelectorAll('*'))
                        .filter(el => {
                            // 尝试匹配可能的加载更多元素
                            if (!el.textContent) return false;
                            const text = el.textContent.toLowerCase();
                            const classAttr = (el.className || '').toLowerCase();
                            const idAttr = (el.id || '').toLowerCase();
                            
                            return (text.includes('更多') || text.includes('加载') ||
                                   classAttr.includes('more') || classAttr.includes('load') ||
                                   idAttr.includes('more') || idAttr.includes('load')) &&
                                   el.offsetParent !== null;  // 确保元素可见
                        });
                    
                    if (possibleLoadMoreElements.length > 0) {
                        console.log('找到可能的加载更多元素:', possibleLoadMoreElements.length);
                        for (const el of possibleLoadMoreElements) {
                            try {
                                el.scrollIntoView({behavior: 'smooth', block: 'center'});
                                setTimeout(() => el.click(), 500);
                                return true;
                            } catch (e) {
                                console.log('点击元素失败:', e);
                            }
                        }
                    }
                    
                    return false;
                }
            """)
            
            if success:
                logger.info("JavaScript分析触发加载更多可能成功")
                time.sleep(3)  # 给足够的时间加载
                
                # 检查内容是否增加
                new_height = page.evaluate("document.body.scrollHeight")
                new_content_count = len(page.query_selector_all(".telegraph-item, [class*='telegraph-item'], .article-item, [class*='article-item']"))
                
                if new_height > old_height + 5 or new_content_count > old_content_count:
                    logger.info(f"JavaScript分析成功: 内容从 {old_content_count} 增加到 {new_content_count} 个元素")
                    return True
            
            # 尝试更复杂的分步滚动
            logger.info("尝试分步滚动页面")
            heights = [old_height // 4, old_height // 2, (old_height * 3) // 4, old_height]
            
            for height in heights:
                page.evaluate(f"window.scrollTo(0, {height});")
                time.sleep(1)
            
            # 最终再次检查内容是否增加
            final_height = page.evaluate("document.body.scrollHeight")
            final_content_count = len(page.query_selector_all(".telegraph-item, [class*='telegraph-item'], .article-item, [class*='article-item']"))
            
            if final_height > old_height + 5 or final_content_count > old_content_count:
                logger.info(f"分步滚动成功: 内容从 {old_content_count} 增加到 {final_content_count} 个元素")
                return True
            
            logger.info("所有加载更多尝试均失败")
            return False
            
        except Exception as e:
            logger.error(f"加载更多帖子时出错: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False 