import logging
import os
import json
import requests
import re
from typing import List, Tuple, Dict, Any

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
    
    def analyze_comments_batch(self, comments: List[str]) -> Dict[str, Any]:
        """
        使用单次API调用批量分析多条评论
        
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
            comments_text = "\n".join([f"{i+1}. {comment}" for i, comment in enumerate(comments)])
            
            prompt = f"""
            请对以下多条评论进行整体情感分析，并返回如下格式的JSON：
            {{
                "label": "正面/负面/中性中的一个",
                "score": 0到5之间的整数评分（0表示无评论，1最消极，5最积极）
            }}
            只返回这个JSON对象，不要添加任何解释或其他文字。
            
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
                    {"role": "system", "content": "你是精通情感分析与投资分析大师，任务是综合多条中文评论分析整体情感倾向（'正面'、'负面'或'中性'）及情感得分（0-5分共六档，0 是无评论、1 是消极、5 是积极）"},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.1,
                "max_tokens": 50
            }
            
            # 发送请求到DeepSeek API
            response = requests.post(self.api_url, headers=headers, json=data)
            response.raise_for_status()
            
            # 解析响应
            result = response.json()
            content = result["choices"][0]["message"]["content"].strip()
            
            # 尝试解析JSON响应
            try:
                # 处理可能包含的Markdown代码块标记
                if content.startswith("```") and "```" in content[3:]:
                    # 提取代码块中的内容
                    content = content.split("```", 2)[1]
                    # 移除可能的语言标识符
                    if content.startswith("json"):
                        content = content[4:].strip()
                    else:
                        content = content.strip()
                    # 去掉结尾的标记
                    if content.endswith("```"):
                        content = content[:content.rfind("```")].strip()
                
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
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"无法解析DeepSeek响应为JSON: {content}，错误: {e}")
                
                # 尝试从文本中提取得分
                # 查找数字模式，例如"得分：4"或"分数：3"等
                score_match = re.search(r'(?:得分|分数|评分|score)[：:]\s*(\d)', content.lower())
                if score_match:
                    try:
                        extracted_score = int(score_match.group(1))
                        # 根据提取的得分确定情感标签
                        if extracted_score >= 4:
                            return {"label": "正面", "score": extracted_score}
                        elif extracted_score <= 2:
                            return {"label": "负面", "score": extracted_score}
                        else:
                            return {"label": "中性", "score": extracted_score}
                    except ValueError:
                        pass
                
                # 如果无法提取得分，根据文本关键词判断情感并分配合理的得分
                if "正面" in content.lower() or "积极" in content.lower() or "看好" in content.lower():
                    return {"label": "正面", "score": 4}
                elif "负面" in content.lower() or "消极" in content.lower() or "看空" in content.lower():
                    return {"label": "负面", "score": 2}
                else:
                    return {"label": "中性", "score": 3}
                
        except Exception as e:
            logger.error(f"批量评论分析错误: {e}")
            return {"label": "中性", "score": 3}
            
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