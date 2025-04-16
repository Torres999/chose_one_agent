# -*- coding: utf-8 -*-
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Comment:
    """评论数据模型"""
    
    content: str
    author: str = "未知用户"
    timestamp: Optional[datetime] = None
    sentiment_score: Optional[float] = None
    keywords: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """初始化后处理"""
        # 如果没有提供时间戳，则使用当前时间
        if self.timestamp is None:
            self.timestamp = datetime.now()


@dataclass
class Post:
    """帖子数据模型"""
    
    title: str
    date: str
    time: str
    section: str
    comment_count: int = 0
    content: str = ""
    url: str = ""
    author: str = "未知用户"
    comments: List[Comment] = field(default_factory=list)
    has_comments: bool = False
    sentiment_analysis: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def datetime(self) -> Optional[datetime]:
        """将日期和时间字符串转换为datetime对象"""
        try:
            return datetime.strptime(f"{self.date} {self.time}", "%Y-%m-%d %H:%M")
        except ValueError:
            try:
                # 尝试不同的日期格式
                return datetime.strptime(f"{self.date} {self.time}", "%m/%d/%Y %H:%M")
            except ValueError:
                return None
    
    @property
    def comment_texts(self) -> List[str]:
        """获取所有评论的文本内容"""
        return [comment.content for comment in self.comments]
    
    def to_dict(self) -> Dict[str, Any]:
        """将帖子转换为字典格式"""
        post_dict = {
            "title": self.title,
            "date": self.date,
            "time": self.time,
            "section": self.section,
            "comment_count": self.comment_count,
            "content": self.content,
            "url": self.url,
            "author": self.author,
            "has_comments": self.has_comments,
            "sentiment_analysis": self.sentiment_analysis
        }
        
        # 转换评论列表
        comments_list = []
        for comment in self.comments:
            comment_dict = {
                "content": comment.content,
                "author": comment.author,
                "timestamp": comment.timestamp.isoformat() if comment.timestamp else None,
                "sentiment_score": comment.sentiment_score,
                "keywords": comment.keywords
            }
            comments_list.append(comment_dict)
        
        post_dict["comments"] = comments_list
        
        return post_dict
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Post':
        """从字典创建帖子对象"""
        # 提取基本属性
        post = cls(
            title=data.get("title", ""),
            date=data.get("date", ""),
            time=data.get("time", ""),
            section=data.get("section", ""),
            comment_count=data.get("comment_count", 0),
            content=data.get("content", ""),
            url=data.get("url", ""),
            author=data.get("author", "未知用户"),
            has_comments=data.get("has_comments", False),
            sentiment_analysis=data.get("sentiment_analysis", {})
        )
        
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
                timestamp=timestamp,
                sentiment_score=comment_data.get("sentiment_score"),
                keywords=comment_data.get("keywords", [])
            )
            comments.append(comment)
        
        post.comments = comments
        
        return post


class TelegraphDataProcessor:
    """
    Telegraph数据处理类
    负责帖子和评论数据的处理和转换
    """
    
    @staticmethod
    def convert_raw_data_to_posts(raw_data: List[Dict[str, Any]]) -> List[Post]:
        """
        将原始抓取数据转换为Post对象列表
        
        Args:
            raw_data: 原始抓取数据
            
        Returns:
            Post对象列表
        """
        posts = []
        
        for item in raw_data:
            # 创建评论对象
            comments = []
            for comment_text in item.get("comments", []):
                comment = Comment(content=comment_text)
                comments.append(comment)
            
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
        """
        合并现有帖子列表和新抓取的帖子列表，避免重复
        
        Args:
            existing_posts: 现有帖子列表
            new_posts: 新抓取的帖子列表
            
        Returns:
            合并后的帖子列表
        """
        # 创建标题到帖子的映射，用于快速查找
        title_to_post = {post.title: post for post in existing_posts}
        
        # 合并新帖子
        for new_post in new_posts:
            if new_post.title in title_to_post:
                # 更新现有帖子的评论
                existing_post = title_to_post[new_post.title]
                
                # 如果新帖子有更多评论，更新评论列表
                if len(new_post.comments) > len(existing_post.comments):
                    existing_post.comments = new_post.comments
                    existing_post.has_comments = len(new_post.comments) > 0
                    existing_post.comment_count = max(existing_post.comment_count, len(new_post.comments))
            else:
                # 添加新帖子
                title_to_post[new_post.title] = new_post
        
        # 返回合并后的帖子列表
        return list(title_to_post.values()) 