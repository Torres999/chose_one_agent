#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试脚本：用于验证电报网站的评论解析功能
"""
import re
import json
from bs4 import BeautifulSoup
from pprint import pprint
import sys
import os

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from chose_one_agent.modules.telegraph.comment_parser import CommentParser

# 用于测试的HTML样本
TELEGRAPH_HTML = """
<div class="evaluate-wrap">
    <div class="evaluate-count">评论(5)</div>
    <div class="evaluate-list">
        <div class="evaluate-item">
            <div class="evaluate-user">用户A</div>
            <div class="evaluate-content">这是第一条评论</div>
            <div class="evaluate-time">2023-01-01 12:00</div>
        </div>
        <div class="evaluate-item">
            <div class="evaluate-user">用户B</div>
            <div class="evaluate-content">这是第二条评论</div>
            <div class="evaluate-time">2023-01-01 12:30</div>
        </div>
    </div>
</div>
"""

def test_comment_parser():
    """测试CommentParser类的功能"""
    parser = CommentParser()
    
    # 解析HTML
    soup = BeautifulSoup(TELEGRAPH_HTML, 'html.parser')
    
    # 提取评论计数
    comment_count = parser.extract_comment_count(soup)
    print(f"评论计数: {comment_count}")
    
    # 提取评论内容
    comments = parser.extract_comments(soup)
    print(f"找到 {len(comments)} 条评论:")
    for i, comment in enumerate(comments, 1):
        print(f"{i}. {comment}")
    
    # 验证结果
    assert comment_count == 5, f"评论计数应为5，实际为{comment_count}"
    assert len(comments) == 2, f"应找到2条评论，实际为{len(comments)}"
    assert "这是第一条评论" in comments[0], "第一条评论内容错误"
    assert "这是第二条评论" in comments[1], "第二条评论内容错误"
    
    print("所有测试通过！")

if __name__ == "__main__":
    test_comment_parser() 