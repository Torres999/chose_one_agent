# -*- coding: utf-8 -*-
"""
DeepSeek情感分析器，使用DeepSeek API进行评论的情感分析
"""
import os
import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

# 获取日志记录器
logger = logging.getLogger(__name__)

class DeepSeekSentimentAnalyzer:
    """使用DeepSeek API进行情感分析"""
    
    def __init__(self, api_key: str = None, debug: bool = False):
        """初始化分析器
        
        Args:
            api_key: DeepSeek API密钥，如果为None则从环境变量获取
            debug: 是否启用调试模式
        """
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY")
        self.debug = debug
        self.client = None
        
        if not self.api_key:
            logger.warning("未提供DeepSeek API密钥，情感分析功能将无法正常工作")
        else:
            # 初始化DeepSeek API客户端
            self.client = OpenAI(
                api_key=self.api_key,
                base_url="https://api.deepseek.com"
            )
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def analyze_comments(self, comments: List[str]) -> Dict[str, Any]:
        """分析评论情感
        
        Args:
            comments: 评论文本列表
            
        Returns:
            情感分析结果，包含评论情绪、情感分布和关键评论
        """
        if not comments or not self.client:
            return {
                "sentiment": "",
                "distribution": "",
                "key_comments": "",
                "total_comments": len(comments) if comments else 0
            }
        
        try:
            # 合并评论文本，限制长度
            combined_text = "\n".join([f"评论{i+1}: {comment}" for i, comment in enumerate(comments)])
            
            # 如果评论过多，截取前50条以避免超出API限制
            if len(comments) > 50:
                combined_text = "\n".join([f"评论{i+1}: {comment}" for i, comment in enumerate(comments[:50])])
                logger.info(f"评论数量过多，仅分析前50条评论，总共{len(comments)}条")
            
            # 系统提示词，指导DeepSeek进行情感分析
            system_prompt = """你是一个专业的财经评论情感分析专家。你需要分析一组财经评论的情感倾向，并输出三项分析结果：
1. 评论情绪：所有评论的整体情感倾向，分为"极度积极"、"积极"、"中性"、"消极"或"极度消极"五档。
2. 情感分布：统计所有评论的情感分布百分比，合并"极度积极"到"积极"，"极度消极"到"消极"，格式为"积极 X% | 中性 Y% | 消极 Z%"。
3. 关键评论：从评论中提取最有代表性的8个关键词或短语，用逗号分隔。

请以JSON格式返回结果：
{
  "sentiment": "极度积极|积极|中性|消极|极度消极",
  "distribution": "积极 X% | 中性 Y% | 消极 Z%",
  "key_comments": "关键词1, 关键词2, 关键词3, ..."
}
"""
            
            # 用户提示词，包含需要分析的评论
            user_prompt = f"请分析以下财经评论的情感倾向：\n\n{combined_text}\n\n请仅返回符合要求的JSON格式结果，不要包含其他解释性文字。"
            
            # 调用DeepSeek API进行情感分析
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.2  # 使用较低的温度以获得更确定的结果
            )
            
            # 提取响应内容
            content = response.choices[0].message.content
            
            # 从响应中提取JSON
            try:
                # 尝试直接解析为JSON
                result = json.loads(content)
            except json.JSONDecodeError:
                # 如果不是纯JSON，尝试从文本中提取JSON部分
                import re
                json_match = re.search(r'({[\s\S]*})', content)
                if json_match:
                    try:
                        result = json.loads(json_match.group(1))
                    except json.JSONDecodeError:
                        logger.error(f"无法解析DeepSeek响应中的JSON: {content}")
                        return {
                            "sentiment": "",
                            "distribution": "",
                            "key_comments": "",
                            "total_comments": len(comments)
                        }
                else:
                    logger.error(f"DeepSeek响应中未找到JSON: {content}")
                    return {
                        "sentiment": "",
                        "distribution": "",
                        "key_comments": "",
                        "total_comments": len(comments)
                    }
            
            # 添加评论总数
            result["total_comments"] = len(comments)
            
            if self.debug:
                logger.debug(f"DeepSeek API响应: {result}")
            
            return result
            
        except Exception as e:
            logger.error(f"调用DeepSeek API进行情感分析时出错: {str(e)}")
            return {
                "sentiment": "",
                "distribution": "",
                "key_comments": "",
                "total_comments": len(comments) if comments else 0
            } 