import logging
import os
import json
import requests
from typing import List, Tuple

# 配置日志
logger = logging.getLogger(__name__)

class DeepSeekSentimentAnalyzer:
    """
    使用DeepSeek API进行中文情感分析的类
    """
    
    def __init__(self, 
                 api_key: str = None,
                 model: str = "deepseek-chat",
                 positive_threshold: float = 0.6, 
                 negative_threshold: float = 0.4):
        """
        初始化DeepSeek情感分析器
        
        Args:
            api_key: DeepSeek API密钥，如果为None则从环境变量获取
            model: 使用的DeepSeek模型名称
            positive_threshold: 积极情感的阈值，高于此值被视为积极
            negative_threshold: 消极情感的阈值，低于此值被视为消极
        """
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY")
        if not self.api_key:
            logger.warning("未提供DeepSeek API密钥，将无法使用DeepSeek情感分析功能")
        
        self.model = model
        self.positive_threshold = positive_threshold
        self.negative_threshold = negative_threshold
        self.api_url = "https://api.deepseek.com/v1/chat/completions"
    
    def analyze_text(self, text: str) -> Tuple[str, float]:
        """
        分析单条文本的情感
        
        Args:
            text: 待分析的文本
            
        Returns:
            (情感标签, 情感得分)的元组，情感标签为"正面"、"负面"或"中性"
        """
        if not self.api_key:
            logger.error("未设置DeepSeek API密钥，无法进行情感分析")
            return "中性", 0.5
        
        try:
            # 构建分析请求
            prompt = f"""
            请对以下文本进行情感分析，返回一个0到1之间的得分，其中0表示极度负面，0.5表示中性，1表示极度正面。
            只返回一个浮点数，不要添加任何解释或其他文字。
            
            文本: "{text}"
            """
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            data = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": "你是一个专业的情感分析助手，你的任务是分析中文文本的情感倾向，并给出0到1之间的得分。"},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.1,  # 低温度以获得更一致的结果
                "max_tokens": 10  # 只需要简短回复
            }
            
            # 发送请求到DeepSeek API
            response = requests.post(self.api_url, headers=headers, json=data)
            response.raise_for_status()
            
            # 解析响应
            result = response.json()
            score_text = result["choices"][0]["message"]["content"].strip()
            
            # 尝试将结果转换为浮点数
            try:
                score = float(score_text)
                # 确保得分在0-1范围内
                score = max(0, min(score, 1))
            except ValueError:
                logger.warning(f"无法将API返回的值解析为浮点数: {score_text}，使用默认值0.5")
                score = 0.5
                
            # 根据得分确定情感标签
            if score >= self.positive_threshold:
                sentiment = "正面"
            elif score <= self.negative_threshold:
                sentiment = "负面"
            else:
                sentiment = "中性"
                
            return sentiment, score
        
        except Exception as e:
            logger.error(f"通过DeepSeek API分析情感时出错: {e}")
            return "中性", 0.5
    
    def analyze_comments(self, comments: List[str]) -> str:
        """
        分析多条评论，综合得出整体情感
        
        Args:
            comments: 评论列表
            
        Returns:
            整体情感标签，为"正面"、"负面"或"中性"
        """
        if not comments:
            return "中性"
        
        if not self.api_key:
            logger.error("未设置DeepSeek API密钥，无法进行情感分析")
            return "中性"
        
        try:
            # 批量分析所有评论
            sentiments_with_scores = [self.analyze_text(comment) for comment in comments]
            
            # 计算平均得分
            total_score = sum(score for _, score in sentiments_with_scores)
            avg_score = total_score / len(sentiments_with_scores)
            
            # 统计各类情感数量
            sentiment_counts = {
                "正面": sum(1 for sentiment, _ in sentiments_with_scores if sentiment == "正面"),
                "负面": sum(1 for sentiment, _ in sentiments_with_scores if sentiment == "负面"),
                "中性": sum(1 for sentiment, _ in sentiments_with_scores if sentiment == "中性")
            }
            
            # 如果某类情感占比超过60%，则采用该情感
            max_sentiment = max(sentiment_counts, key=sentiment_counts.get)
            max_count = sentiment_counts[max_sentiment]
            
            if max_count / len(comments) >= 0.6:
                return max_sentiment
            
            # 否则，根据平均得分判断
            if avg_score >= self.positive_threshold:
                return "正面"
            elif avg_score <= self.negative_threshold:
                return "负面"
            else:
                return "中性"
                
        except Exception as e:
            logger.error(f"评论综合分析错误: {e}")
            return "中性"
    
    def analyze_comments_batch(self, comments: List[str]) -> str:
        """
        使用单次API调用批量分析多条评论，这样更高效
        
        Args:
            comments: 评论列表
            
        Returns:
            整体情感标签，为"正面"、"负面"或"中性"
        """
        if not comments:
            return "中性"
        
        if not self.api_key:
            logger.error("未设置DeepSeek API密钥，无法进行情感分析")
            return "中性"
        
        try:
            # 将评论合并为单个请求
            comments_text = "\n".join([f"{i+1}. {comment}" for i, comment in enumerate(comments)])
            
            prompt = f"""
            请对以下多条评论进行整体情感分析，判断整体评论倾向是"正面"、"负面"还是"中性"。
            只返回一个词："正面"、"负面"或"中性"，不要添加任何其他解释或文字。
            
            评论:
            {comments_text}
            """
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            data = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": "你是一个专业的情感分析助手，你的任务是综合分析多条中文评论的整体情感倾向，并给出'正面'、'负面'或'中性'的判断。"},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.1,
                "max_tokens": 10
            }
            
            # 发送请求到DeepSeek API
            response = requests.post(self.api_url, headers=headers, json=data)
            response.raise_for_status()
            
            # 解析响应
            result = response.json()
            sentiment = result["choices"][0]["message"]["content"].strip()
            
            # 规范化输出
            sentiment = sentiment.replace("'", "").replace('"', "")
            if "正面" in sentiment:
                return "正面"
            elif "负面" in sentiment:
                return "负面"
            else:
                return "中性"
                
        except Exception as e:
            logger.error(f"批量评论分析错误: {e}")
            return "中性"
            
    def get_sentiment_score(self, sentiment: str) -> int:
        """
        将情感标签转换为0-5的评分
        
        Args:
            sentiment: 情感标签，为"正面"、"负面"或"中性"
            
        Returns:
            情感评分: 1(最消极)-5(最积极)，0表示无评论
        """
        sentiment_mapping = {
            "极度负面": 1,
            "负面": 2,
            "中性": 3,
            "正面": 4,
            "极度正面": 5
        }
        return sentiment_mapping.get(sentiment, 3)  # 默认返回中性(3) 