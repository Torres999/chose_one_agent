# -*- coding: utf-8 -*-
import re
import datetime
from typing import Dict, Any, List, Optional, Union

from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from playwright.sync_api import ElementHandle

from chose_one_agent.utils.logging_utils import get_logger, log_error
from chose_one_agent.utils.datetime_utils import extract_date_time

# 获取日志记录器
logger = get_logger(__name__)

# 正则表达式模式
POST_PATTERNS = {
    "date_standard": re.compile(r'(\d{4}[-\.]\d{1,2}[-\.]\d{1,2})'),
    "date_chinese": re.compile(r'(\d{4})年(\d{1,2})月(\d{1,2})日'),
    "time": re.compile(r'(\d{2}:\d{2}(?::\d{2})?)'),
    "comment_count": re.compile(r'评论\s*[(\[:]?\s*(\d+)[)\]:]?|(\d+)\s*(?:条)?评论'),
    "brackets_title": [
        r'【([^】]+)】',     # 方括号格式
        r'\[([^\]]+)\]',     # 方括号格式
        r'「([^」]+)」'      # 书名号格式
    ]
}

# CSS选择器
POST_SELECTORS = {
    "post": ".topic-item, article.article-list-item",
    "title": "h2 a, h3 a, h2.title span",
    "time": ".meta-item.meta-item-time, .time, .meta .meta-item:not(.meta-item-user)",
    "comment_count": ".meta-item-comment, .commentCounter",
    "load_more": ".load-more, .list-more"
}

class PostExtractor:
    """帖子信息提取器"""

    def __init__(self, driver=None, wait=None, debug: bool = False):
        self.driver = driver
        self.wait = wait
        self.debug = debug
        self.selectors = POST_SELECTORS
        self.patterns = POST_PATTERNS

    def get_posts(self, section: str = "未知板块") -> List[Dict[str, Any]]:
        """获取页面上所有帖子信息"""
        if not self.driver:
            logger.error("驱动未初始化")
            return []
            
        posts = []
        try:
            elements = self.driver.find_elements(By.CSS_SELECTOR, self.selectors["post"])
            logger.info(f"找到 {len(elements)} 个帖子元素")
            
            for element in elements:
                try:
                    post_info = self.extract_post_info(element, section)
                    if self._is_valid_post(post_info):
                        posts.append(post_info)
                except Exception as e:
                    logger.error(f"提取帖子信息失败: {e}")
            
        except Exception as e:
            logger.error(f"获取帖子列表失败: {e}")
        
        return posts

    def extract_post_info(self, element: Union[WebElement, ElementHandle], section: str = "未知板块") -> Dict[str, Any]:
        """从元素中提取完整帖子信息"""
            # 初始化结果
        post_info = {
            "element": element,
                "title": "未知标题",
            "section": section,
            "time": "未知时间",
                "date": "未知日期",
                "comment_count": 0,
            "is_valid_post": False
        }
        
        try:
            # 使用Selenium WebElement
            if isinstance(element, WebElement):
                post_info.update(self._extract_from_selenium_element(element))
            # 使用Playwright ElementHandle
            elif isinstance(element, ElementHandle):
                post_info.update(self._extract_from_playwright_element(element))
                    else:
                logger.error(f"不支持的元素类型: {type(element)}")
                
            # 验证帖子有效性
            post_info["is_valid_post"] = self._is_valid_post(post_info)
            
        except Exception as e:
            logger.error(f"提取帖子信息时出错: {e}")
            
        return post_info
    
    def _extract_from_selenium_element(self, element: WebElement) -> Dict[str, Any]:
        """从Selenium元素提取信息"""
        result = {}
        
        # 提取标题
        result["title"] = self._extract_title_selenium(element)
        
        # 提取时间和日期
        result.update(self._extract_time_selenium(element))
        
        # 提取评论数
        result["comment_count"] = self._extract_comment_count_selenium(element)
        
        return result
    
    def _extract_from_playwright_element(self, element: ElementHandle) -> Dict[str, Any]:
        """从Playwright元素提取信息"""
        result = {}
        
        # 获取元素文本内容
        element_text = element.text_content() or ""
        element_text = element_text.strip()
        
        # 过滤无效内容
        if not element_text or len(element_text) < 10:
            return result
        
        # 提取时间和日期
        self._extract_time_info(element_text, result)
        
        # 提取标题
        self._extract_title_playwright(element_text, result)
        
        # 提取评论数量
        self._extract_comment_count_playwright(element_text, result)
        
        return result

    def _extract_title_selenium(self, element: WebElement) -> str:
        """从Selenium元素提取帖子标题"""
        try:
            title_element = element.find_element(By.CSS_SELECTOR, self.selectors["title"])
            return title_element.text.strip()
        except NoSuchElementException:
            return "无标题"
                                except Exception as e:
            logger.error(f"提取标题出错: {e}")
            return "提取标题失败"

    def _extract_time_selenium(self, element: WebElement) -> Dict[str, str]:
        """从Selenium元素提取帖子发布时间和日期"""
        result = {"date": "", "time": ""}
        
        try:
            time_element = element.find_element(By.CSS_SELECTOR, self.selectors["time"])
            time_text = time_element.text.strip()
            
            # 提取日期
            date_match = self.patterns["date_standard"].search(time_text)
            if date_match:
                result["date"] = date_match.group(1).replace('-', '.')
                
            # 提取时间
            time_match = self.patterns["time"].search(time_text)
            if time_match:
                result["time"] = time_match.group(1)
                
        except NoSuchElementException:
            result["date"] = datetime.datetime.now().strftime("%Y.%m.%d")
        except Exception as e:
            logger.error(f"提取时间出错: {e}")
            
        return result

    def _extract_comment_count_selenium(self, element: WebElement) -> int:
        """从Selenium元素提取评论数量"""
        try:
            comment_element = element.find_element(By.CSS_SELECTOR, self.selectors["comment_count"])
            comment_text = comment_element.text.strip()
            
            comment_match = self.patterns["comment_count"].search(comment_text)
            if comment_match:
                count = comment_match.group(1) if comment_match.group(1) else comment_match.group(2)
                return int(count)
        except (NoSuchElementException, ValueError, AttributeError):
            pass
            
        return 0

    def _extract_time_info(self, text: str, result: Dict[str, Any]) -> None:
        """提取日期和时间信息"""
        # 提取时间
        time_match = self.patterns["time"].search(text)
        if time_match:
            result["time"] = time_match.group(1)
            # 标准化时间格式
            if result["time"].count(':') == 1:
                result["time"] += ":00"
        
        # 提取日期 - 标准格式 (yyyy-mm-dd 或 yyyy.mm.dd)
        date_match = self.patterns["date_standard"].search(text)
        if date_match:
            result["date"] = date_match.group(1).replace('-', '.')
        else:
            # 中文日期格式 (yyyy年mm月dd日)
            cn_date_match = self.patterns["date_chinese"].search(text)
            if cn_date_match:
                year, month, day = cn_date_match.groups()
                result["date"] = f"{year}.{month}.{day}"
            else:
                # 如果没找到日期，使用当前日期
                result["date"] = datetime.datetime.now().strftime("%Y.%m.%d")

    def _extract_title_playwright(self, text: str, result: Dict[str, Any]) -> None:
        """从文本中提取标题"""
        # 尝试从括号中提取标题
        for pattern in self.patterns["brackets_title"]:
            match = re.search(pattern, text)
            if match:
                result["title"] = match.group(1).strip()
                return
        
        # 尝试使用时间作为基准提取标题
        time_str = result.get("time", "未知时间")
        if time_str != "未知时间":
            try:
                # 查找时间后的文本
                parts = text.split(time_str, 1)
                if len(parts) > 1 and parts[1].strip():
                    # 提取第一行或前50个字符作为标题
                    title_text = parts[1].strip().split('\n')[0].strip()
                    if title_text:
                        result["title"] = title_text[:100] if len(title_text) > 100 else title_text
                        return
            except Exception as e:
                if self.debug:
                    logger.error(f"提取基于时间的标题时出错: {e}")
        
        # 检查是否包含冒号格式的标题
        colon_match = re.search(r'([^：:]{2,})[：:](.+?)(?=\s*\d|\s*$)', text)
        if colon_match:
            title = colon_match.group(2).strip()
            if len(title) > 2:
                result["title"] = title

    def _extract_comment_count_playwright(self, text: str, result: Dict[str, Any]) -> None:
        """从文本中提取评论数量"""
        comment_match = self.patterns["comment_count"].search(text)
        if comment_match:
            # 使用第一个捕获组或第二个捕获组（取决于哪个匹配）
            count = comment_match.group(1) if comment_match.group(1) else comment_match.group(2)
            try:
                result["comment_count"] = int(count)
            except ValueError:
                logger.warning(f"无法解析评论数量: {count}")

    def _is_valid_post(self, post_info: Dict[str, Any]) -> bool:
        """验证帖子信息是否有效"""
        title = post_info.get("title", "")
        time = post_info.get("time", "")
        return bool(title and title != "无标题" and title != "提取标题失败" and time != "未知时间")

    def load_more_posts(self, max_retries: int = 3) -> bool:
        """尝试加载更多帖子"""
        if not self.driver:
            return False
            
        for _ in range(max_retries):
            try:
                button = self.driver.find_element(By.CSS_SELECTOR, self.selectors["load_more"])
                if button.is_displayed():
                    button.click()
                    return True
            except (NoSuchElementException, TimeoutException):
                break
        except Exception as e:
                logger.error(f"加载更多帖子失败: {e}")
                
            return False 