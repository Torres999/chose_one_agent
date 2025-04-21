# -*- coding: utf-8 -*-
"""
数据库配置模块，负责加载和管理数据库连接参数
"""
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# MySQL数据库配置
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', 3306)),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', '123456'),
    'database': os.getenv('DB_NAME', 'choseone'),
    'charset': 'utf8mb4'
}

# 数据库表名映射
TABLE_MAPPING = {
    '公司': 'company_posts',
    '看盘': 'watch_plate_posts'
}

# 批处理配置
BATCH_SIZE = 50  # 批量插入的大小
LOG_INTERVAL = 100  # 日志记录间隔 