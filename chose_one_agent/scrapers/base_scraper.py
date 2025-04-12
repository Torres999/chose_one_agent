import logging
import time
import datetime
from typing import List, Dict, Any, Optional
from playwright.sync_api import sync_playwright, Page, Browser

# 配置日志
logger = logging.getLogger(__name__)

class BaseScraper:
    """
    基础爬虫类，供各功能模块继承使用
    """
    
    def __init__(self, cutoff_date: datetime.datetime, headless: bool = True):
        """
        初始化爬虫
        
        Args:
            cutoff_date: 截止日期，早于此日期的内容将被忽略
            headless: 是否使用无头模式运行浏览器
        """
        self.cutoff_date = cutoff_date
        self.headless = headless
        self.browser = None
        self.page = None
        self.context = None
        self.base_url = "https://www..cn"
        self.results = []
        
    def __enter__(self):
        """
        上下文管理器入口，启动浏览器
        """
        playwright = sync_playwright().start()
        self.browser = playwright.chromium.launch(headless=self.headless)
        self.context = self.browser.new_context(viewport={"width": 1280, "height": 800})
        self.page = self.context.new_page()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        上下文管理器出口，关闭浏览器
        """
        if self.browser:
            self.browser.close()
            
    def navigate_to_site(self):
        """
        导航到网站
        """
        try:
            logger.info(f"正在导航到{self.base_url}...")
            self.page.goto(self.base_url)
            self.page.wait_for_load_state("networkidle")
            time.sleep(2)
            logger.info("已成功加载网站")
        except Exception as e:
            logger.error(f"导航到网站时出错: {e}")
            raise
            
    def navigate_to_section(self, main_section: str, sub_section: Optional[str] = None):
        """
        导航到指定板块
        
        Args:
            main_section: 主板块名称
            sub_section: 子板块名称（可选）
        """
        try:
            logger.info(f"正在导航到'{main_section}'板块...")
            
            # 尝试多种定位主版块的方式
            try:
                # 先尝试使用文本定位
                self.page.click(f"text='{main_section}'", timeout=5000)
            except Exception:
                try:
                    # 尝试不带引号的文本定位
                    self.page.click(f"text={main_section}", timeout=5000)
                except Exception:
                    # 尝试使用包含类名的元素定位
                    selectors = [
                        f"[class*='nav'] >> text={main_section}",
                        f"[class*='menu'] >> text={main_section}",
                        f"[class*='tab'] >> text={main_section}",
                        f"a >> text={main_section}"
                    ]
                    
                    success = False
                    for selector in selectors:
                        try:
                            self.page.click(selector, timeout=3000)
                            success = True
                            break
                        except Exception:
                            continue
                    
                    if not success:
                        # 如果仍然失败，尝试查找包含此文本的任何元素
                        elements = self.page.query_selector_all(f"text={main_section}")
                        if elements and len(elements) > 0:
                            elements[0].click()
                        else:
                            raise Exception(f"无法找到'{main_section}'主板块")
            
            self.page.wait_for_load_state("networkidle")
            time.sleep(2)
            
            if sub_section:
                logger.info(f"正在导航到'{sub_section}'子板块...")
                
                # 同样尝试多种方式定位子版块
                try:
                    # 先尝试使用文本定位
                    self.page.click(f"text='{sub_section}'", timeout=5000)
                except Exception:
                    try:
                        # 尝试不带引号的文本定位
                        self.page.click(f"text={sub_section}", timeout=5000)
                    except Exception:
                        # 尝试使用包含类名的元素定位
                        selectors = [
                            f"[class*='sub-nav'] >> text={sub_section}",
                            f"[class*='tab'] >> text={sub_section}",
                            f"[class*='submenu'] >> text={sub_section}",
                            f"[class*='category'] >> text={sub_section}",
                            f"a >> text={sub_section}"
                        ]
                        
                        success = False
                        for selector in selectors:
                            try:
                                self.page.click(selector, timeout=3000)
                                success = True
                                break
                            except Exception:
                                continue
                        
                        if not success:
                            # 如果仍然失败，尝试查找包含此文本的任何元素
                            elements = self.page.query_selector_all(f"text={sub_section}")
                            if elements and len(elements) > 0:
                                elements[0].click()
                            else:
                                raise Exception(f"无法找到'{sub_section}'子板块")
                
                self.page.wait_for_load_state("networkidle")
                time.sleep(2)
                logger.info(f"已成功导航到'{main_section}->{sub_section}'板块")
            else:
                logger.info(f"已成功导航到'{main_section}'板块")
                
        except Exception as e:
            logger.error(f"导航到板块时出错: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise
    
    def load_more_content(self, load_more_text: str = "加载更多") -> bool:
        """
        点击"加载更多"按钮加载更多内容
        
        Args:
            load_more_text: 加载更多按钮的文本
            
        Returns:
            是否成功加载更多内容
        """
        try:
            load_more_btn = self.page.query_selector(f"text={load_more_text}") or self.page.query_selector(".load-more")
            if load_more_btn:
                load_more_btn.click()
                self.page.wait_for_load_state("networkidle")
                time.sleep(2)
                return True
            else:
                return False
        except Exception as e:
            logger.error(f"加载更多内容时出错: {e}")
            return False
    
    def run(self) -> List[Dict[str, Any]]:
        """
        执行爬取和分析过程，子类需要重写此方法
        
        Returns:
            包含所有分析结果的列表
        """
        raise NotImplementedError("子类必须实现run方法") 