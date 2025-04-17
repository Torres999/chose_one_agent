# -*- coding: utf-8 -*-
"""
Telegraph模块的数据模型定义
"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

from chose_one_agent.utils.logging_utils import get_logger

# 获取日志记录器
logger = get_logger(__name__)


@dataclass
class Comment:
    """评论模型"""
    content: str
    author: str = None
    date: str = None
    time: str = None
    sentiment_score: float = 0.0
    keywords: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """如果没有提供时间戳，则使用当前时间"""
        if self.date and self.time:
            self.timestamp = datetime.strptime(f"{self.date} {self.time}", "%Y-%m-%d %H:%M")
        elif self.date:
            self.timestamp = datetime.strptime(self.date, "%Y-%m-%d")
        elif self.time:
            self.timestamp = datetime.strptime(self.time, "%H:%M")
        else:
            self.timestamp = datetime.now()
            
    def __str__(self):
        return f"Comment(author={self.author}, content={self.content[:30]}...)"

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "content": self.content,
            "author": self.author,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "sentiment_score": self.sentiment_score,
            "keywords": self.keywords
        }


@dataclass
class Post:
    """帖子模型"""
    title: str
    url: str = None
    content: str = None
    author: str = None
    date: str = None
    time: str = None
    section: str = None
    comment_count: int = 0
    comments: List[Comment] = field(default_factory=list)
    has_comments: bool = False
    sentiment_analysis: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def datetime(self) -> Optional[datetime]:
        """将日期和时间字符串转换为datetime对象"""
        if self.date and self.time:
            try:
                return datetime.strptime(f"{self.date} {self.time}", "%Y-%m-%d %H:%M")
            except ValueError:
                try:
                    return datetime.strptime(f"{self.date} {self.time}", "%m/%d/%Y %H:%M")
                except ValueError:
                    return None
        elif self.date:
            return datetime.strptime(self.date, "%Y-%m-%d")
        elif self.time:
            return datetime.strptime(self.time, "%H:%M")
        else:
            return None
    
    @property
    def comment_texts(self) -> List[str]:
        """获取所有评论的文本内容"""
        return [comment.content for comment in self.comments]
    
    def __post_init__(self):
        """如果没有提供时间戳，则使用当前时间"""
        if self.date and self.time:
            self.timestamp = datetime.strptime(f"{self.date} {self.time}", "%Y-%m-%d %H:%M")
        elif self.date:
            self.timestamp = datetime.strptime(self.date, "%Y-%m-%d")
        elif self.time:
            self.timestamp = datetime.strptime(self.time, "%H:%M")
        else:
            self.timestamp = datetime.now()
        
        self.sentiment_analysis = {}
        self.has_comments = len(self.comments) > 0
        self.comment_count = len(self.comments)
    
    def add_comment(self, comment: Comment):
        """添加评论"""
        self.comments.append(comment)
        self.has_comments = True
        self.comment_count = max(self.comment_count, len(self.comments))
    
    def __str__(self):
        return f"Post(title={self.title}, comments={len(self.comments)})"
    
    def to_dict(self) -> Dict[str, Any]:
        """将帖子转换为字典格式"""
        return {
            "title": self.title,
            "date": self.date,
            "time": self.time,
            "section": self.section,
            "comment_count": self.comment_count,
            "content": self.content,
            "url": self.url,
            "author": self.author,
            "has_comments": self.has_comments,
            "sentiment_analysis": self.sentiment_analysis,
            "comments": [c.to_dict() for c in self.comments]
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Post':
        """从字典创建帖子对象"""
        # 转换评论列表
        comments = []
        for comment_data in data.get("comments", []):
            # 处理时间戳
            timestamp = None
            if comment_data.get("timestamp"):
                try:
                    timestamp = datetime.fromisoformat(comment_data["timestamp"])
                except (ValueError, TypeError):
                    pass
            
            comment = Comment(
                content=comment_data.get("content", ""),
                author=comment_data.get("author", "未知用户"),
                date=comment_data.get("date"),
                time=comment_data.get("time"),
                sentiment_score=comment_data.get("sentiment_score", 0.0),
                keywords=comment_data.get("keywords", [])
            )
            comments.append(comment)
        
        # 提取帖子属性并创建对象
        post = cls(
            title=data.get("title", ""),
            url=data.get("url", ""),
            content=data.get("content", ""),
            author=data.get("author", "未知用户"),
            date=data.get("date"),
            time=data.get("time"),
            section=data.get("section"),
            comment_count=data.get("comment_count", 0),
            comments=comments,
            has_comments=data.get("has_comments", False),
            sentiment_analysis=data.get("sentiment_analysis", {})
        )
        return post


class TelegraphDataProcessor:
    """Telegraph数据处理类，负责帖子和评论数据的处理和转换"""
    
    @staticmethod
    def convert_raw_data_to_posts(raw_data: List[Dict[str, Any]]) -> List[Post]:
        """将原始抓取数据转换为Post对象列表"""
        posts = []
        for item in raw_data:
            # 创建评论对象
            comments = [Comment(content=text) for text in item.get("comments", [])]
            
            # 创建帖子对象
            post = Post(
                title=item.get("title", ""),
                date=item.get("date", ""),
                time=item.get("time", ""),
                section=item.get("section", ""),
                comment_count=item.get("comment_count", 0),
                comments=comments,
                has_comments=len(comments) > 0
            )
            posts.append(post)
        return posts
    
    @staticmethod
    def merge_posts(existing_posts: List[Post], new_posts: List[Post]) -> List[Post]:
        """合并现有帖子列表和新抓取的帖子列表，避免重复"""
        # 创建标题到帖子的映射
        title_to_post = {post.title: post for post in existing_posts}
        
        # 合并新帖子
        for new_post in new_posts:
            if new_post.title in title_to_post:
                # 更新现有帖子的评论
                existing_post = title_to_post[new_post.title]
                if len(new_post.comments) > len(existing_post.comments):
                    existing_post.comments = new_post.comments
                    existing_post.has_comments = len(new_post.comments) > 0
                    existing_post.comment_count = max(existing_post.comment_count, len(new_post.comments))
            else:
                # 添加新帖子
                title_to_post[new_post.title] = new_post
        
        return list(title_to_post.values()) 