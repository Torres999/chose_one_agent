# -*- coding: utf-8 -*-
"""
数据库工具模块，提供与MySQL数据库的交互功能
"""
import pymysql
import datetime
import logging
from typing import Dict, List, Any, Tuple, Optional

from chose_one_agent.utils.logging_utils import get_logger
from chose_one_agent.utils.db_config import DB_CONFIG, TABLE_MAPPING, BATCH_SIZE

# 设置日志
logger = get_logger(__name__)

class MySQLManager:
    """MySQL数据库管理器，提供统一的数据库操作接口"""
    
    def __init__(self, config: Dict = None, batch_size: int = None):
        """
        初始化数据库管理器
        
        Args:
            config: 数据库连接配置，默认使用DB_CONFIG
            batch_size: 批量插入的大小，默认使用BATCH_SIZE
        """
        self.config = config or DB_CONFIG
        self.batch_size = batch_size or BATCH_SIZE
        self.conn = None
        self._init_tables()
    
    def _get_connection(self):
        """获取数据库连接"""
        try:
            if self.conn is None or not self.conn.open:
                self.conn = pymysql.connect(**self.config)
            return self.conn
        except Exception as e:
            logger.error(f"数据库连接失败: {e}")
            # 添加更详细的错误信息，包含连接信息（移除敏感信息）
            config_safe = self.config.copy()
            if 'password' in config_safe:
                config_safe['password'] = '******'  # 隐藏密码
            error_msg = f"无法连接到数据库 {config_safe.get('host')}:{config_safe.get('port')}/{config_safe.get('database')}，请检查数据库配置和连接"
            logger.error(error_msg)
            # 重新抛出异常，包含详细信息
            raise ConnectionError(f"数据库连接失败: {error_msg}") from e
    
    def _init_tables(self):
        """初始化数据库表"""
        try:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                # 公司板块表
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS company_posts (
                        id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
                        title VARCHAR(256) COMMENT '标题',
                        post_date DATE COMMENT '日期',
                        post_time TIME COMMENT '时间',
                        section VARCHAR(32) COMMENT '所属板块',
                        comment_count INT DEFAULT 0 COMMENT '评论数量',
                        sentiment_type VARCHAR(32) COMMENT '评论情绪',
                        sentiment_distribution VARCHAR(256) COMMENT '情感分布',
                        key_comments TEXT COMMENT '关键评论',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间'
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='公司板块帖子表';
                """)
                
                # 看盘板块表
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS watch_plate_posts (
                        id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
                        title VARCHAR(256) COMMENT '标题',
                        post_date DATE COMMENT '日期',
                        post_time TIME COMMENT '时间',
                        section VARCHAR(32) COMMENT '所属板块',
                        comment_count INT DEFAULT 0 COMMENT '评论数量',
                        sentiment_type VARCHAR(32) COMMENT '评论情绪',
                        sentiment_distribution VARCHAR(256) COMMENT '情感分布',
                        key_comments TEXT COMMENT '关键评论',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间'
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='看盘板块帖子表';
                """)
                
                # 断点续爬表
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS scrape_checkpoints (
                        id INT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
                        section VARCHAR(32) UNIQUE COMMENT '所属板块',
                        last_post_date DATE COMMENT '最后爬取的帖子日期',
                        last_post_time TIME COMMENT '最后爬取的帖子时间',
                        last_scrape_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后爬取时间',
                        total_posts_scraped BIGINT DEFAULT 0 COMMENT '已爬取帖子总数'
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='爬取断点记录表';
                """)
            
            conn.commit()
            logger.info("数据库表初始化成功")
        except Exception as e:
            logger.error(f"初始化数据库表失败: {e}")
            if conn:
                conn.rollback()
    
    def save_posts(self, posts: List[Dict[str, Any]], section: str) -> int:
        """
        批量保存帖子数据
        
        Args:
            posts: 帖子数据列表
            section: 板块名称，'公司' 或 '看盘'
            
        Returns:
            成功插入的记录数
        """
        if not posts:
            logger.info(f"没有新的帖子数据需要保存，板块: {section}")
            return 0
        
        # 获取表名
        table_name = TABLE_MAPPING.get(section)
        if not table_name:
            logger.error(f"未知的板块名称: {section}")
            return 0
        
        # 获取上次断点
        last_checkpoint = self.get_last_checkpoint(section)
        
        conn = self._get_connection()
        success_count = 0
        
        try:
            with conn.cursor() as cursor:
                # 分批处理
                for i in range(0, len(posts), self.batch_size):
                    batch = posts[i:i+self.batch_size]
                    batch_values = []
                    latest_date = None
                    latest_time = None
                    
                    for post in batch:
                        # 跳过之前已处理的帖子
                        if last_checkpoint and self._is_post_processed(post, last_checkpoint):
                            continue
                        
                        # 转换日期时间格式
                        post_date = self._parse_date(post.get('date', ''))
                        post_time = self._parse_time(post.get('time', ''))
                        
                        # 处理情感分析数据
                        sentiment_analysis = post.get('sentiment_analysis', {})
                        comment_count = post.get('comment_count', 0)
                        
                        # 提取情感类型
                        sentiment_type = "中性"  # 默认为中性
                        if sentiment_analysis:
                            positive = sentiment_analysis.get('positive_ratio', 0)
                            negative = sentiment_analysis.get('negative_ratio', 0)
                            if positive > 0.6:
                                sentiment_type = "极度积极" if positive > 0.8 else "积极"
                            elif negative > 0.6:
                                sentiment_type = "极度消极" if negative > 0.8 else "消极"
                        
                        # 提取情感分布
                        sentiment_distribution = ""
                        if sentiment_analysis:
                            positive = sentiment_analysis.get('positive_ratio', 0) * 100
                            neutral = sentiment_analysis.get('neutral_ratio', 0) * 100
                            negative = sentiment_analysis.get('negative_ratio', 0) * 100
                            sentiment_distribution = f"积极 {positive:.1f}% | 中性 {neutral:.1f}% | 消极 {negative:.1f}%"
                        
                        # 提取关键评论
                        key_comments = ", ".join(sentiment_analysis.get('key_words', []))
                        
                        # 记录最新的日期和时间
                        if latest_date is None or post_date > latest_date:
                            latest_date = post_date
                        if latest_time is None or post_time > latest_time:
                            latest_time = post_time
                        
                        # 添加到批处理值
                        batch_values.append((
                            post.get('title', ''),
                            post_date,
                            post_time,
                            section,
                            comment_count,
                            sentiment_type,
                            sentiment_distribution,
                            key_comments
                        ))
                    
                    # 执行批量插入
                    if batch_values:
                        sql = f"""
                            INSERT INTO {table_name} 
                            (title, post_date, post_time, section, comment_count, 
                            sentiment_type, sentiment_distribution, key_comments) 
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """
                        cursor.executemany(sql, batch_values)
                        inserted_count = len(batch_values)
                        success_count += inserted_count
                        
                        # 更新断点
                        if latest_date and latest_time:
                            self.update_checkpoint(section, latest_date, latest_time, success_count)
                        
                        # 记录日志
                        if success_count % BATCH_SIZE == 0 or success_count == len(posts):
                            logger.info(f"已保存 {success_count}/{len(posts)} 条帖子数据到 {section} 板块")
                
                conn.commit()
                logger.info(f"成功保存 {success_count} 条帖子数据到 {section} 板块")
                return success_count
                
        except Exception as e:
            logger.error(f"保存帖子数据失败: {e}")
            if conn:
                conn.rollback()
            return success_count
    
    def _is_post_processed(self, post: Dict[str, Any], checkpoint: Dict[str, Any]) -> bool:
        """
        检查帖子是否已处理过
        
        Args:
            post: 帖子数据
            checkpoint: 断点信息
            
        Returns:
            是否已处理
        """
        if not checkpoint or not post:
            return False
            
        last_date = checkpoint.get('last_post_date')
        last_time = checkpoint.get('last_post_time')
        
        if not last_date or not last_time:
            return False
            
        post_date = self._parse_date(post.get('date', ''))
        post_time = self._parse_time(post.get('time', ''))
        
        # 如果帖子日期早于断点日期，或者日期相同但时间早于断点时间，则认为已处理
        return (post_date < last_date) or (post_date == last_date and post_time <= last_time)
    
    def _parse_date(self, date_str: str) -> str:
        """
        解析日期字符串为MySQL DATE格式
        
        Args:
            date_str: 日期字符串，如 "2023.05.20" 或 "2023-05-20"
            
        Returns:
            MySQL DATE格式的日期字符串，如 "2023-05-20"
        """
        try:
            # 处理常见的日期格式
            if not date_str:
                return datetime.date.today().strftime('%Y-%m-%d')
                
            # 替换分隔符为标准格式
            date_str = date_str.replace('.', '-').replace('/', '-')
            
            # 尝试解析日期
            if '-' in date_str:
                parts = date_str.split('-')
                if len(parts) >= 3:
                    year, month, day = parts[0], parts[1], parts[2]
                    # 确保年月日格式正确
                    if len(year) == 2:  # 处理两位数年份
                        year = f"20{year}"
                    # 返回标准格式
                    return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
            
            # 如果无法解析，返回当前日期
            return datetime.date.today().strftime('%Y-%m-%d')
        except Exception as e:
            logger.warning(f"解析日期失败: {date_str}, 错误: {e}")
            return datetime.date.today().strftime('%Y-%m-%d')
    
    def _parse_time(self, time_str: str) -> str:
        """
        解析时间字符串为MySQL TIME格式
        
        Args:
            time_str: 时间字符串，如 "10:15:12" 或 "10:15"
            
        Returns:
            MySQL TIME格式的时间字符串，如 "10:15:12"
        """
        try:
            # 处理常见的时间格式
            if not time_str:
                return datetime.datetime.now().strftime('%H:%M:%S')
                
            # 添加缺少的秒数
            if time_str.count(':') == 1:
                time_str = f"{time_str}:00"
                
            # 检查格式是否正确
            if ':' in time_str and len(time_str.split(':')) == 3:
                return time_str
                
            # 如果格式不正确，返回当前时间
            return datetime.datetime.now().strftime('%H:%M:%S')
        except Exception as e:
            logger.warning(f"解析时间失败: {time_str}, 错误: {e}")
            return datetime.datetime.now().strftime('%H:%M:%S')
    
    def update_checkpoint(self, section: str, last_post_date: str, last_post_time: str, total_posts: int = 0) -> bool:
        """
        更新断点信息
        
        Args:
            section: 板块名称
            last_post_date: 最后爬取的帖子日期
            last_post_time: 最后爬取的帖子时间
            total_posts: 已爬取的帖子总数
            
        Returns:
            是否更新成功
        """
        try:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                # 检查是否已存在
                cursor.execute(
                    "SELECT * FROM scrape_checkpoints WHERE section = %s",
                    (section,)
                )
                exists = cursor.fetchone()
                
                if exists:
                    # 更新现有记录
                    cursor.execute(
                        """
                        UPDATE scrape_checkpoints 
                        SET last_post_date = %s, last_post_time = %s, 
                            total_posts_scraped = total_posts_scraped + %s 
                        WHERE section = %s
                        """,
                        (last_post_date, last_post_time, total_posts, section)
                    )
                else:
                    # 创建新记录
                    cursor.execute(
                        """
                        INSERT INTO scrape_checkpoints 
                        (section, last_post_date, last_post_time, total_posts_scraped) 
                        VALUES (%s, %s, %s, %s)
                        """,
                        (section, last_post_date, last_post_time, total_posts)
                    )
                
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"更新断点信息失败: {e}")
            if conn:
                conn.rollback()
            return False
    
    def get_last_checkpoint(self, section: str) -> Optional[Dict[str, Any]]:
        """
        获取最后的断点信息
        
        Args:
            section: 板块名称
            
        Returns:
            断点信息，如果不存在则返回None
        """
        try:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT last_post_date, last_post_time, total_posts_scraped FROM scrape_checkpoints WHERE section = %s",
                    (section,)
                )
                result = cursor.fetchone()
                
                if result:
                    return {
                        'last_post_date': result[0],
                        'last_post_time': result[1],
                        'total_posts_scraped': result[2]
                    }
                return None
        except Exception as e:
            logger.error(f"获取断点信息失败: {e}")
            return None
    
    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            self.conn = None 