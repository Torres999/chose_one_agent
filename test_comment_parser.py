#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试脚本：用于验证cls.cn/telegraph网站的评论解析功能
"""

from __future__ import unicode_literals
import os
import re
import json
import pytest
import mock  # 使用mock库替代unittest.mock

# 处理Python 2.7 Unicode问题
import sys
reload(sys)
sys.setdefaultencoding('utf-8')

# 假设示例HTML片段
CLS_TELEGRAPH_HTML = """
<div class="post-item">
    <div class="title">测试电报标题</div>
    <div class="content">测试电报内容</div>
    <div class="evaluate-wrapper">
        <span class="evaluate-count">评论(1)</span>
        <span class="evaluate-count">分享(271)</span>
    </div>
</div>
<div class="post-item">
    <div class="title">没有评论的电报</div>
    <div class="content">这个电报没有评论</div>
    <div class="evaluate-wrapper">
        <span class="evaluate-count">评论(0)</span>
        <span class="evaluate-count">分享(5)</span>
    </div>
</div>
"""

# 模拟评论内容示例
SAMPLE_COMMENTS_JSON = """
[
    {
        "selector": "div",
        "text": "这是一条评论内容",
        "className": "comment-text",
        "isNew": true
    },
    {
        "selector": "p",
        "text": "这是另一条评论内容",
        "className": "",
        "isNew": true
    }
]
"""

def test_evaluate_count_regex():
    """测试评论计数正则表达式是否能正确匹配各种格式"""
    # 测试不同格式的评论计数
    test_cases = [
        ("评论(1)", 1),
        ("评论（5）", 5),
        ("评论 (10)", 10),
        ("评论（ 20 ）", 20),
        ("评论:30", None),  # 这种格式当前正则不支持
        ("评论 15", None)    # 这种格式当前正则不支持
    ]
    
    # 现有的正则表达式
    current_regex = r'评论.*?[（(](\d+)[)）]'
    
    # 扩展的正则表达式，支持更多格式
    extended_regex = r'评论.*?(?:[（(](\d+)[)）]|[:：](\d+)|(\d+))'
    
    for text, expected in test_cases:
        # 测试当前正则
        match = re.search(current_regex, text)
        if expected and match:
            assert int(match.group(1)) == expected
        elif not expected:
            assert match is None or match.group(1) is None
            
        # 测试扩展正则
        match = re.search(extended_regex, text)
        if expected:
            # 获取第一个非None的捕获组
            groups = [g for g in match.groups() if g is not None] if match else []
            if groups:
                assert int(groups[0]) == expected
            else:
                assert False, "扩展正则未能匹配: {}".format(text)


def test_html_parsing():
    """测试从HTML中提取评论元素"""
    from bs4 import BeautifulSoup
    
    # 解析HTML
    soup = BeautifulSoup(CLS_TELEGRAPH_HTML, 'html.parser')
    
    # 查找评论计数元素
    comment_elements = soup.select('.evaluate-count')
    
    # 应该找到两个元素
    assert len(comment_elements) == 4
    
    # 提取评论计数
    comment_counts = []
    for el in comment_elements:
        text = el.text.strip()
        if '评论' in text:
            match = re.search(r'评论.*?[（(](\d+)[)）]', text)
            if match:
                comment_counts.append(int(match.group(1)))
    
    # 应该找到两个评论计数：1和0
    assert sorted(comment_counts) == [0, 1]


def test_create_temp_comment_file():
    """测试创建临时评论文件并读取"""
    # 创建临时文件
    temp_file = "/tmp/test_comments.json"
    with open(temp_file, "w") as f:
        f.write(SAMPLE_COMMENTS_JSON)
    
    # 读取并验证
    with open(temp_file, "r") as f:
        comments_data = json.load(f)
    
    # 应该有两条评论
    assert len(comments_data) == 2
    assert comments_data[0]["text"] == "这是一条评论内容"
    assert comments_data[1]["text"] == "这是另一条评论内容"
    
    # 清理
    if os.path.exists(temp_file):
        os.remove(temp_file)


@pytest.mark.parametrize("element_text,expected", [
    ("评论(5)", 5),
    ("评论(0)", 0),
    ("暂无评论", 0),
    ("其他文本", None)
])
def test_extract_comment_count(element_text, expected):
    """测试从元素文本中提取评论计数"""
    # 使用更通用的正则表达式
    regex_patterns = [
        r'评论.*?[（(](\d+)[)）]',  # 标准格式：评论(5)
        r'评论[:：]?\s*(\d+)',      # 冒号格式：评论:5 或 评论5
    ]
    
    count = None
    for pattern in regex_patterns:
        match = re.search(pattern, element_text)
        if match:
            count = int(match.group(1))
            break
    
    if "暂无评论" in element_text:
        count = 0
        
    assert count == expected


def test_mock_playwright_interaction():
    """测试模拟Playwright的交互过程"""
    # 创建模拟对象
    mock_page = mock.MagicMock()
    mock_element = mock.MagicMock()
    
    # 设置模拟行为
    mock_element.inner_text.return_value = "评论(3)"
    mock_page.query_selector_all.return_value = [mock_element]
    
    # 模拟evaluate方法返回可能的评论内容
    mock_page.evaluate.return_value = json.loads(SAMPLE_COMMENTS_JSON)
    
    # 模拟点击和交互
    mock_element.click.return_value = None
    
    # 执行测试
    # 查找评论元素
    elements = mock_page.query_selector_all("span.evaluate-count")
    assert len(elements) == 1
    
    # 获取评论计数
    element_text = elements[0].inner_text()
    match = re.search(r'评论.*?[（(](\d+)[)）]', element_text)
    if match:
        count = int(match.group(1))
    else:
        count = 0
    
    assert count == 3
    
    # 模拟点击
    elements[0].click()
    
    # 模拟获取评论
    comments = mock_page.evaluate()
    assert len(comments) == 2
    assert comments[0]["text"] == "这是一条评论内容"


if __name__ == "__main__":
    # 运行单个测试
    test_evaluate_count_regex()
    test_html_parsing()
    test_create_temp_comment_file()
    test_extract_comment_count("评论(5)", 5)
    test_mock_playwright_interaction()
    
    print("所有测试通过！") 