#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试脚本：用于收集和调试电报网站的评论元素信息
"""

import re
import json
import sys
import os
from datetime import datetime

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.sync_api import sync_playwright

def collect_comment_elements(url="https://www.telegraph-site.cn/telegraph"):
    """收集电报网站的评论元素信息"""
    with sync_playwright() as playwright:
        # 初始化浏览器
        browser = playwright.chromium.launch(headless=False)
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()
        
        # 导航到电报页面
        print(f"正在导航到 {url}...")
        page.goto(url, timeout=10000)
        page.wait_for_load_state("networkidle", timeout=5000)
        
        # 等待用户手动导航到包含评论的页面
        print("请手动导航到包含评论的页面，然后按回车继续...")
        input()
        
        # 收集页面上的评论相关元素
        print("正在收集评论元素信息...")
        
        comment_selectors = [
            "span:has-text('评论')",
            ".evaluate-count", 
            "[class*='comment']", 
            "[class*='evaluate']"
        ]
        
        # 查找所有可能的评论元素
        all_elements = []
        for selector in comment_selectors:
            try:
                elements = page.query_selector_all(selector)
                for i, element in enumerate(elements):
                    try:
                        # 获取元素信息
                        bbox = element.bounding_box()
                        if not bbox or bbox["width"] <= 0 or bbox["height"] <= 0:
                            continue  # 跳过不可见元素
                            
                        text = element.inner_text().strip()
                        if not text:
                            continue  # 跳过空元素
                            
                        # 尝试提取评论计数
                        count = None
                        patterns = [
                            r'评论[（(](\d+)[)）]',
                            r'评论[:：]\s*(\d+)',
                            r'评论\s+(\d+)'
                        ]
                        for pattern in patterns:
                            match = re.search(pattern, text)
                            if match:
                                count = int(match.group(1))
                                break
                                
                        all_elements.append({
                            "selector": selector,
                            "text": text,
                            "comment_count": count,
                            "position": {
                                "x": bbox["x"],
                                "y": bbox["y"],
                                "width": bbox["width"],
                                "height": bbox["height"]
                            }
                        })
                        
                        # 高亮这个元素，以便识别
                        page.evaluate("""
                            (element) => {
                                const oldBorder = element.style.border;
                                element.style.border = '2px solid red';
                                setTimeout(() => { element.style.border = oldBorder; }, 1000);
                            }
                        """, element)
                        
                    except Exception as e:
                        print(f"处理元素时出错: {e}")
                        
            except Exception as e:
                print(f"使用选择器 '{selector}' 查找元素时出错: {e}")
        
        # 输出结果
        print(f"找到 {len(all_elements)} 个评论相关元素")
        
        # 保存结果到JSON文件
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"comment_elements_{timestamp}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(all_elements, f, ensure_ascii=False, indent=2)
            
        print(f"结果已保存到 {filename}")
        
        # 等待用户按任意键后关闭浏览器
        print("按回车键退出...")
        input()
        
        # 关闭浏览器
        context.close()
        browser.close()

if __name__ == "__main__":
    collect_comment_elements() 