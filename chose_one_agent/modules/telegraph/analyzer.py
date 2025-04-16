# -*- coding: utf-8 -*-
import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from collections import Counter

try:
    import nltk
    from nltk.sentiment import SentimentIntensityAnalyzer
    from nltk.tokenize import word_tokenize
    from nltk.corpus import stopwords
    NLTK_AVAILABLE = True
except ImportError:
    NLTK_AVAILABLE = False

try:
    import spacy
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False

from chose_one_agent.modules.telegraph.data_models import Post, Comment


class TelegraphAnalyzer:
    """Telegraph数据分析类"""
    
    def __init__(self, use_nltk: bool = True, use_spacy: bool = False):
        """
        初始化分析器
        
        Args:
            use_nltk: 是否使用NLTK进行分析
            use_spacy: 是否使用spaCy进行分析
        """
        self.logger = logging.getLogger(__name__)
        self.use_nltk = use_nltk and NLTK_AVAILABLE
        self.use_spacy = use_spacy and SPACY_AVAILABLE
        
        # 初始化NLTK组件
        if self.use_nltk:
            try:
                nltk.download('vader_lexicon', quiet=True)
                nltk.download('punkt', quiet=True)
                nltk.download('stopwords', quiet=True)
                self.sia = SentimentIntensityAnalyzer()
                self.stop_words = set(stopwords.words('english'))
                self.logger.info("NLTK组件初始化成功")
            except Exception as e:
                self.logger.error(f"NLTK组件初始化失败: {str(e)}")
                self.use_nltk = False
        
        # 初始化spaCy模型
        if self.use_spacy:
            try:
                self.nlp = spacy.load("en_core_web_sm")
                self.logger.info("spaCy模型初始化成功")
            except Exception as e:
                self.logger.error(f"spaCy模型加载失败: {str(e)}")
                self.use_spacy = False
    
    def analyze_sentiment(self, text: str) -> Dict[str, float]:
        """
        分析文本情感
        
        Args:
            text: 待分析文本
            
        Returns:
            情感分析结果，包含积极、消极、中性和复合得分
        """
        if not text or text.strip() == "":
            return {"pos": 0.0, "neg": 0.0, "neu": 1.0, "compound": 0.0}
        
        if self.use_nltk:
            try:
                scores = self.sia.polarity_scores(text)
                return scores
            except Exception as e:
                self.logger.error(f"NLTK情感分析失败: {str(e)}")
        
        # 简单的基于规则的回退方法
        positive_words = ["good", "great", "excellent", "amazing", "wonderful", "fantastic"]
        negative_words = ["bad", "terrible", "awful", "horrible", "poor", "disappointing"]
        
        words = text.lower().split()
        pos_count = sum(1 for word in words if word in positive_words)
        neg_count = sum(1 for word in words if word in negative_words)
        total = len(words) or 1  # 避免除以零
        
        pos_score = pos_count / total
        neg_score = neg_count / total
        neu_score = 1 - (pos_score + neg_score)
        compound = pos_score - neg_score
        
        return {
            "pos": pos_score,
            "neg": neg_score,
            "neu": neu_score,
            "compound": compound
        }
    
    def extract_keywords(self, text: str, top_n: int = 5) -> List[str]:
        """
        提取文本关键词
        
        Args:
            text: 待分析文本
            top_n: 返回的关键词数量
            
        Returns:
            关键词列表
        """
        if not text or text.strip() == "":
            return []
        
        # 使用spaCy提取关键词
        if self.use_spacy:
            try:
                doc = self.nlp(text)
                # 排除停用词、标点符号和数字
                keywords = [token.lemma_.lower() for token in doc 
                           if not token.is_stop and not token.is_punct and not token.is_digit
                           and len(token.text) > 2]
                
                # 统计词频
                keyword_freq = Counter(keywords)
                return [word for word, _ in keyword_freq.most_common(top_n)]
            except Exception as e:
                self.logger.error(f"spaCy关键词提取失败: {str(e)}")
        
        # 使用NLTK提取关键词
        if self.use_nltk:
            try:
                # 分词
                tokens = word_tokenize(text.lower())
                # 去除停用词和短词
                filtered_tokens = [word for word in tokens 
                                  if word not in self.stop_words
                                  and len(word) > 2
                                  and word.isalpha()]
                
                # 统计词频
                word_freq = Counter(filtered_tokens)
                return [word for word, _ in word_freq.most_common(top_n)]
            except Exception as e:
                self.logger.error(f"NLTK关键词提取失败: {str(e)}")
        
        # 简单的基于规则的回退方法
        # 去除标点和特殊字符
        cleaned_text = re.sub(r'[^\w\s]', '', text.lower())
        words = cleaned_text.split()
        
        # 简单的停用词列表
        simple_stopwords = ["the", "and", "is", "in", "to", "of", "that", "this", "for", "with",
                           "on", "at", "by", "an", "be", "are", "was", "were", "it", "as"]
        
        # 过滤停用词和短词
        filtered_words = [word for word in words if word not in simple_stopwords and len(word) > 2]
        
        # 统计词频
        word_counts = Counter(filtered_words)
        
        # 返回最常见的词
        return [word for word, _ in word_counts.most_common(top_n)]
    
    def analyze_post(self, post: Post) -> Post:
        """
        分析帖子数据，包括情感分析和关键词提取
        
        Args:
            post: 帖子对象
            
        Returns:
            分析后的帖子对象
        """
        # 分析帖子标题和内容
        title_sentiment = self.analyze_sentiment(post.title)
        content_sentiment = self.analyze_sentiment(post.content)
        
        # 提取关键词
        title_keywords = self.extract_keywords(post.title, top_n=3)
        content_keywords = self.extract_keywords(post.content, top_n=5)
        
        # 更新帖子对象的情感分析结果
        post.sentiment_analysis = {
            "title": title_sentiment,
            "content": content_sentiment,
            "overall": self._combine_sentiment_scores([title_sentiment, content_sentiment])
        }
        
        # 分析评论
        for comment in post.comments:
            comment_sentiment = self.analyze_sentiment(comment.content)
            comment.sentiment_score = comment_sentiment.get("compound", 0.0)
            comment.keywords = self.extract_keywords(comment.content, top_n=3)
        
        # 汇总评论情感
        if post.comments:
            comment_sentiments = [self.analyze_sentiment(c.content) for c in post.comments]
            post.sentiment_analysis["comments"] = self._combine_sentiment_scores(comment_sentiments)
        
        return post
    
    def _combine_sentiment_scores(self, sentiment_list: List[Dict[str, float]]) -> Dict[str, float]:
        """
        合并多个情感分析结果
        
        Args:
            sentiment_list: 情感分析结果列表
            
        Returns:
            合并后的情感分析结果
        """
        if not sentiment_list:
            return {"pos": 0.0, "neg": 0.0, "neu": 1.0, "compound": 0.0}
        
        # 计算平均值
        combined = {"pos": 0.0, "neg": 0.0, "neu": 0.0, "compound": 0.0}
        
        for sentiment in sentiment_list:
            for key in combined:
                combined[key] += sentiment.get(key, 0.0)
        
        # 取平均值
        count = len(sentiment_list)
        for key in combined:
            combined[key] /= count
        
        return combined
    
    def get_sentiment_label(self, compound_score: float) -> str:
        """
        根据复合情感得分返回情感标签
        
        Args:
            compound_score: 复合情感得分
            
        Returns:
            情感标签：积极、消极或中性
        """
        if compound_score >= 0.05:
            return "积极"
        elif compound_score <= -0.05:
            return "消极"
        else:
            return "中性"
    
    def analyze_post_batch(self, posts: List[Post]) -> List[Post]:
        """
        批量分析帖子数据
        
        Args:
            posts: 帖子对象列表
            
        Returns:
            分析后的帖子对象列表
        """
        self.logger.info(f"开始批量分析帖子，共 {len(posts)} 个帖子")
        
        analyzed_posts = []
        for post in posts:
            try:
                analyzed_post = self.analyze_post(post)
                analyzed_posts.append(analyzed_post)
            except Exception as e:
                self.logger.error(f"分析帖子失败: {str(e)}")
                analyzed_posts.append(post)  # 添加原始帖子，保持列表长度一致
        
        self.logger.info(f"完成批量分析帖子，成功分析 {len(analyzed_posts)} 个帖子")
        return analyzed_posts
    
    def get_most_positive_posts(self, posts: List[Post], limit: int = 5) -> List[Post]:
        """
        获取情感最积极的帖子
        
        Args:
            posts: 帖子对象列表
            limit: 返回的帖子数量
            
        Returns:
            情感最积极的帖子列表
        """
        # 确保帖子已经被分析
        analyzed_posts = [self.analyze_post(post) if "overall" not in post.sentiment_analysis else post 
                         for post in posts]
        
        # 按照复合情感得分排序
        sorted_posts = sorted(
            analyzed_posts,
            key=lambda p: p.sentiment_analysis.get("overall", {}).get("compound", 0),
            reverse=True
        )
        
        return sorted_posts[:limit]
    
    def get_most_negative_posts(self, posts: List[Post], limit: int = 5) -> List[Post]:
        """
        获取情感最消极的帖子
        
        Args:
            posts: 帖子对象列表
            limit: 返回的帖子数量
            
        Returns:
            情感最消极的帖子列表
        """
        # 确保帖子已经被分析
        analyzed_posts = [self.analyze_post(post) if "overall" not in post.sentiment_analysis else post 
                         for post in posts]
        
        # 按照复合情感得分排序
        sorted_posts = sorted(
            analyzed_posts,
            key=lambda p: p.sentiment_analysis.get("overall", {}).get("compound", 0)
        )
        
        return sorted_posts[:limit]
    
    def get_trending_keywords(self, posts: List[Post], limit: int = 10) -> List[Tuple[str, int]]:
        """
        获取所有帖子中的热门关键词
        
        Args:
            posts: 帖子对象列表
            limit: 返回的关键词数量
            
        Returns:
            热门关键词及其频率的列表
        """
        keyword_counter = Counter()
        
        # 收集所有帖子和评论中的关键词
        for post in posts:
            # 分析帖子标题和内容
            title_keywords = self.extract_keywords(post.title)
            content_keywords = self.extract_keywords(post.content)
            
            # 更新计数器
            keyword_counter.update(title_keywords)
            keyword_counter.update(content_keywords)
            
            # 收集评论关键词
            for comment in post.comments:
                # 如果评论对象有关键词属性且已填充
                if hasattr(comment, 'keywords') and comment.keywords:
                    keyword_counter.update(comment.keywords)
                else:
                    # 否则提取关键词
                    comment_keywords = self.extract_keywords(comment.content)
                    keyword_counter.update(comment_keywords)
        
        # 返回最常见的关键词
        return keyword_counter.most_common(limit) 