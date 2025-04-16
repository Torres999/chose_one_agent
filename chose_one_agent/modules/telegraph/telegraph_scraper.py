# -*- coding: utf-8 -*-
import logging
import time
from typing import List, Dict, Any
from playwright.sync_api import sync_playwright

from chose_one_agent.modules.telegraph.sections.kanpan_scraper import KanpanScraper
from chose_one_agent.modules.telegraph.sections.company_scraper import CompanyScraper
from chose_one_agent.utils.config import BASE_URL

# 配置日志
logger = logging.getLogger(__name__)

class TelegraphScraper:
    """电报爬虫主类，用于协调不同板块的爬虫"""

    def __init__(self, cutoff_date, headless=True, debug=False, section="看盘", sentiment_analyzer_type="snownlp", deepseek_api_key=None):
        """
        初始化电报爬虫

        Args:
            cutoff_date: 截止日期，爬虫只会获取该日期到当前时间范围内的电报
            headless: 是否使用无头模式运行浏览器
            debug: 是否启用调试模式
            section: 默认抓取的板块，如"看盘"或"公司"
            sentiment_analyzer_type: 情感分析器类型，可选值："snownlp"或"deepseek"
            deepseek_api_key: DeepSeek API密钥，当sentiment_analyzer_type为"deepseek"时必须提供
        """
        self.cutoff_date = cutoff_date
        self.headless = headless
        self.debug = debug
        self.section = section
        self.sentiment_analyzer_type = sentiment_analyzer_type
        self.deepseek_api_key = deepseek_api_key
        self.base_url = BASE_URL
        self.results = []
        
    def __enter__(self):
        """上下文管理器入口"""
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        pass
        
    def run(self, sections: List[str] = None) -> List[Dict[str, Any]]:
        """
        执行爬取和分析过程
        
        Args:
            sections: 要爬取的电报子板块列表，默认为["看盘", "公司"]
            
        Returns:
            包含所有分析结果的列表
        """
        try:
            # 如果没有指定板块，默认爬取"看盘"和"公司"
            if sections is None:
                sections = ["看盘", "公司"]
            
            # 处理板块名称
            processed_sections = [section.strip() for section in sections if section.strip()]
            if not processed_sections:
                processed_sections = ["看盘", "公司"]
                
            if self.debug:
                logger.info(f"开始爬取电报，子板块: {processed_sections}")
            self.results = []  # 清空之前的结果
            
            # 使用单个Playwright实例处理所有板块
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=self.headless)
                context = browser.new_context(viewport={"width": 1280, "height": 800})
                
                try:
                    # 先尝试导航到电报网站首页
                    try:
                        page = context.new_page()
                        logger.info("导航到电报网站首页...")
                        page.goto(BASE_URL, timeout=15000)
                        page.wait_for_load_state("networkidle", timeout=10000)
                        time.sleep(2)
                        
                        # 检查电报链接是否可用
                        telegraph_link = page.query_selector("a[href*='telegraph'], a:has-text('电报')")
                        if telegraph_link:
                            logger.info("找到电报链接，点击导航至电报页面...")
                            telegraph_link.click()
                            page.wait_for_load_state("networkidle", timeout=10000)
                            time.sleep(2)
                        else:
                            logger.info("未找到电报链接，尝试直接导航到电报页面...")
                            page.goto(f"{BASE_URL}/telegraph", timeout=15000)
                            page.wait_for_load_state("networkidle", timeout=10000)
                            time.sleep(2)
                            
                        # 如果我们不在电报页面，打印警告
                        if "telegraph" not in page.url:
                            logger.warning(f"未成功导航到电报页面，当前URL: {page.url}")
                            # 尝试使用JS查找电报链接
                            page.evaluate("""
                                () => {
                                    const links = Array.from(document.querySelectorAll('a'));
                                    const telegraphLink = links.find(link => 
                                        (link.textContent || '').includes('电报') || 
                                        (link.href || '').includes('telegraph')
                                    );
                                    if (telegraphLink) telegraphLink.click();
                                }
                            """)
                            page.wait_for_load_state("networkidle", timeout=10000)
                            time.sleep(2)
                    except Exception as e:
                        logger.error(f"导航到电报页面时出错: {e}")
                        logger.info("继续尝试处理各个板块...")
                    finally:
                        # 关闭初始页面
                        try:
                            page.close()
                        except:
                            pass
                
                    # 爬取每个板块
                    for section in processed_sections:
                        if self.debug:
                            logger.info(f"开始爬取'{section}'板块")
                        
                        # 创建对应板块的爬虫实例
                        if section == "看盘":
                            scraper = KanpanScraper(
                                self.cutoff_date, 
                                self.headless, 
                                self.debug,
                                sentiment_analyzer_type=self.sentiment_analyzer_type,
                                deepseek_api_key=self.deepseek_api_key
                            )
                            scraper.section = "看盘"  # 显式设置板块
                        elif section == "公司":
                            scraper = CompanyScraper(
                                self.cutoff_date, 
                                self.headless, 
                                self.debug,
                                sentiment_analyzer_type=self.sentiment_analyzer_type,
                                deepseek_api_key=self.deepseek_api_key
                            )
                            scraper.section = "公司"  # 显式设置板块
                        else:
                            if self.debug:
                                logger.warning(f"未支持的板块: {section}，跳过")
                            continue
                        
                        # 设置浏览器实例
                        scraper.browser = browser
                        scraper.context = context
                        scraper.page = context.new_page()
                        
                        try:
                            # 首先尝试直接访问板块页面
                            try:
                                section_url = f"{BASE_URL}/telegraph"
                                logger.info(f"直接导航到电报页面: {section_url}")
                                scraper.page.goto(section_url, timeout=15000)
                                scraper.page.wait_for_load_state("networkidle", timeout=10000)
                                time.sleep(2)
                                
                                # 模拟成功导航到板块
                                logger.info(f"已导航到电报页面，将尝试查找'{section}'板块内容")
                            except Exception as e:
                                logger.error(f"直接导航到板块页面失败: {e}")
                            
                            # 运行爬虫
                            section_results = scraper.run()
                            
                            # 处理结果
                            if section_results:
                                # 确保每个结果都包含板块信息，并且是正确的板块
                                for result in section_results:
                                    result["section"] = section
                                
                                self.results.extend(section_results)
                                if self.debug:
                                    logger.info(f"'{section}'板块爬取完成，获取到{len(section_results)}条电报")
                            elif self.debug:
                                logger.warning(f"在'{section}'板块未找到符合条件的电报")
                        except Exception as e:
                            logger.error(f"爬取'{section}'板块时出错: {e}")
                        finally:
                            # 关闭页面
                            if scraper.page:
                                scraper.page.close()
                finally:
                    # 关闭浏览器资源
                    context.close()
                    browser.close()
            
            # 结果汇总，再次确认所有结果都有正确的板块信息
            if self.results:
                if self.debug:
                    logger.info(f"共找到 {len(self.results)} 条符合截止日期 {self.cutoff_date} 之后的电报")
                # 检查每个结果的板块信息
                for i, result in enumerate(self.results):
                    if "section" not in result or not result["section"] or result["section"] == "未知板块":
                        # 尝试从标题推断板块
                        title = result.get("title", "")
                        if "股" in title or any(code in title for code in ["SH", "SZ", "BJ", "HK"]):
                            result["section"] = "看盘"
                        elif "公司" in title or "集团" in title or "股份" in title:
                            result["section"] = "公司"
                    if self.debug:
                        logger.debug(f"结果 {i+1}: 标题='{result.get('title', '无标题')}', 板块='{result.get('section', '未知板块')}'")
            elif self.debug:
                logger.warning(f"未找到任何符合截止日期 {self.cutoff_date} 之后的电报，请考虑调整日期范围")
            
            return self.results
            
        except Exception as e:
            logger.error(f"运行电报爬虫时出错: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return self.results