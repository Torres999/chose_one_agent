# -*- coding: utf-8 -*-
"""
配置文件，包含系统配置参数
"""
import os
from dotenv import load_dotenv

# 尝试加载.env文件中的环境变量
# 如果.env文件不存在，则使用默认值
load_dotenv(verbose=True)

# 网站基础URL
BASE_URL = "https://www.cls.cn"

# DeepSeek API配置
# 获取环境变量中的API密钥，如果不存在则使用默认值
# 注意：实际使用时请将.env.example复制为.env并填入你的真实API密钥
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "your_deepseek_api_key_here")

# 可以在这里添加其他配置项 