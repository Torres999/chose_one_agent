"""
配置模块，负责加载和管理项目配置
"""
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv(verbose=True)

# 导入常量
from chose_one_agent.utils.constants import BASE_URLS

# 网站基础URL
BASE_URL = BASE_URLS["main"]

# DeepSeek API配置
# 获取环境变量中的API密钥，如果不存在则使用默认值
# 注意：实际使用时请将.env.example复制为.env并填入你的真实API密钥
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")

# 日志配置
LOG_CONFIG = {
    "level": os.getenv("LOG_LEVEL", "INFO"),
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "file": os.getenv("LOG_FILE", "chose_one_agent.log")
}

# 爬虫配置
SCRAPER_CONFIG = {
    "default_headless": True,
    "default_timeout": 30000,
    "default_sections": ["看盘", "公司"]
}

# 可以在这里添加其他配置项 