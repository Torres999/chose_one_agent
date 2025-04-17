# -*- coding: utf-8 -*-
import logging
import os
import json
import requests
import re

# 配置日志
logger = logging.getLogger(__name__)

class DeepSeekSentimentAnalyzer(object):
    """
    使用DeepSeek API进行中文情感分析的类
    """
    
    def __init__(self, api_key=None, model="deepseek-chat"):
        """
        初始化DeepSeek情感分析器
        
        Args:
            api_key: DeepSeek API密钥，如果为None则从环境变量获取
            model: 使用的DeepSeek模型名称
        """
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY")
        if not self.api_key:
            logger.warning("未提供DeepSeek API密钥，将无法使用DeepSeek情感分析功能")
        
        self.model = model
        self.api_url = "https://api.deepseek.com/v1/chat/completions"
    
    def analyze_comments_batch(self, comments):
        """
        使用DeepSeek API批量分析多条评论
        
        Args:
            comments: 评论列表
            
        Returns:
            包含整体情感标签和得分的字典:
            {
                'label': 情感标签，为"正面"、"负面"或"中性",
                'score': 情感得分，0-5的整数（0表示无评论）
            }
        """
        if not comments:
            return {"label": "中性", "score": 0}
        
        if not self.api_key:
            logger.error("未设置DeepSeek API密钥，无法进行情感分析")
            return {"label": "中性", "score": 3}
        
        try:
            # 将评论合并为单个请求
            comments_text = "\n".join(["{0}. {1}".format(i+1, comment) for i, comment in enumerate(comments)])
            
            prompt = """
            请对以下多条评论进行整体情感分析，并返回如下格式的JSON：
            {{
                "label": "正面/负面/中性中的一个",
                "score": 0到5之间的整数评分（0表示无评论，1最消极，5最积极）
            }}
            只返回这个JSON对象，不要添加任何解释或其他文字。
            
            评论:
            {0}
            """.format(comments_text)
            
            # 发送请求到DeepSeek API
            response = requests.post(
                self.api_url,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": "Bearer {0}".format(self.api_key)
                },
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": "你是精通情感分析的大师，综合分析多条评论的整体情感倾向"},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.1,
                    "max_tokens": 50
                }
            )
            response.raise_for_status()
            
            # 解析响应
            content = response.json()["choices"][0]["message"]["content"].strip()
            return self._parse_sentiment_response(content)
                
        except Exception as e:
            logger.error("批量评论分析错误: {}".format(e))
            return {"label": "中性", "score": 3}
    
    def _parse_sentiment_response(self, content):
        """解析API返回的情感分析结果"""
        try:
            # 处理可能包含的Markdown代码块
            if "```" in content:
                # 提取代码块中的内容
                parts = content.split("```")
                if len(parts) >= 3:
                    # 去掉可能的语言标识符
                    code_block = parts[1].strip()
                    if code_block.startswith("json"):
                        code_block = code_block[4:].strip()
                    content = code_block
            
            # 尝试解析JSON
            sentiment_data = json.loads(content)
            sentiment_label = sentiment_data.get("label", "中性")
            sentiment_score = sentiment_data.get("score", 3)
            
            # 规范化标签
            if "正面" in sentiment_label:
                sentiment_label = "正面"
            elif "负面" in sentiment_label:
                sentiment_label = "负面"
            else:
                sentiment_label = "中性"
            
            # 确保分数在正确范围内
            sentiment_score = max(0, min(int(sentiment_score), 5))
            
            return {"label": sentiment_label, "score": sentiment_score}
            
        except (json.JSONDecodeError, ValueError):
            # 尝试从文本中提取信息
            score = 3  # 默认中性
            label = "中性"
            
            # 尝试提取得分
            score_match = re.search(r'(?:得分|分数|评分|score)[：:]\s*(\d)', content.lower())
            if score_match:
                score = int(score_match.group(1))
            
            # 根据关键词判断情感
            if "正面" in content.lower() or "积极" in content.lower():
                label = "正面"
                score = score if score > 3 else 4
            elif "负面" in content.lower() or "消极" in content.lower():
                label = "负面"
                score = score if score < 3 else 2
            
            return {"label": label, "score": score}
            
    def get_sentiment_score(self, sentiment):
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