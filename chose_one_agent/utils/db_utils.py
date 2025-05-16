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
    
    def _preprocess_post_data(self, post: Dict[str, Any]) -> Dict[str, Any]:
        """
        预处理帖子数据，仅转换日期时间格式，其他字段直接使用原数据
        
        Args:
            post: 原始帖子数据
            
        Returns:
            处理后的帖子数据
        """
        # 转换日期时间格式
        post_date = self._parse_date(post.get('date', ''))
        post_time = self._parse_time(post.get('time', ''))
        
        # 直接使用原始数据中的所有字段
        processed_post = {
            'title': post.get('title', ''),
            'date': post_date,
            'time': post_time,
            'section': post.get('section', ''),
            'comment_count': post.get('comment_count', 0),
            'sentiment_type': post.get('sentiment_type', ''),  # 直接获取原始数据
            'sentiment_distribution': post.get('sentiment_distribution', ''),  # 直接获取原始数据
            'key_comments': post.get('key_comments', '')  # 直接获取原始数据
        }
        
        # 记录处理后的字段到日志
        logger.debug(f"处理后的帖子数据: {processed_post}")
        
        return processed_post
    
    def _execute_batch_insert(self, cursor, table_name: str, batch_values: List[Tuple]) -> None:
        """
        执行批量插入操作
        
        Args:
            cursor: 数据库游标
            table_name: 表名
            batch_values: 批量值列表
        """
        if not batch_values:
            return
            
        sql = f"""
            INSERT INTO {table_name} 
            (title, post_date, post_time, section, comment_count, 
            sentiment_type, sentiment_distribution, key_comments) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        cursor.executemany(sql, batch_values)
        
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
                batch_values = []
                latest_date = None
                latest_time = None
                
                for post in posts:
                    try:
                        # 记录处理的帖子信息
                        logger.info(f"处理帖子: {post.get('title', '')}，日期: {post.get('date', '')}, 时间: {post.get('time', '')}")
                        
                        # 跳过之前已处理的帖子
                        if last_checkpoint and self._is_post_processed(post, last_checkpoint):
                            logger.info(f"帖子已处理，跳过: {post.get('title', '')}，断点时间: {last_checkpoint.get('last_post_date')} {last_checkpoint.get('last_post_time')}")
                            continue
                        
                        # 预处理帖子数据
                        processed_post = self._preprocess_post_data(post)
                        
                        # 提取处理后的数据
                        post_date = processed_post['date']
                        post_time = processed_post['time']
                        
                        # 记录转换后的日期时间
                        logger.info(f"转换后的日期: {post_date} ({type(post_date).__name__}), 时间: {post_time} ({type(post_time).__name__})")
                        
                        # 统一将日期和时间转换为字符串进行比较
                        if isinstance(post_date, datetime.date):
                            post_date_str = post_date.strftime('%Y-%m-%d')
                        else:
                            post_date_str = str(post_date)
                            
                        if isinstance(post_time, datetime.time):
                            post_time_str = post_time.strftime('%H:%M:%S')
                        else:
                            post_time_str = str(post_time)
                            
                        logger.info(f"字符串形式的日期: {post_date_str}, 时间: {post_time_str}")
                        logger.info(f"当前latest_date: {latest_date} ({type(latest_date).__name__ if latest_date else 'None'}), latest_time: {latest_time} ({type(latest_time).__name__ if latest_time else 'None'})")
                        
                        # 更新最新日期和时间
                        if latest_date is None:
                            latest_date = post_date
                            logger.info(f"初始化latest_date: {latest_date} ({type(latest_date).__name__})")
                        else:
                            if isinstance(latest_date, datetime.date):
                                latest_date_str = latest_date.strftime('%Y-%m-%d')
                            else:
                                latest_date_str = str(latest_date)
                                
                            logger.info(f"比较日期: {post_date_str} > {latest_date_str} = {post_date_str > latest_date_str}")
                            if post_date_str > latest_date_str:
                                latest_date = post_date
                                logger.info(f"更新latest_date: {latest_date} ({type(latest_date).__name__})")
                                
                        if latest_time is None:
                            latest_time = post_time
                            logger.info(f"初始化latest_time: {latest_time} ({type(latest_time).__name__})")
                        else:
                            if isinstance(latest_time, datetime.time):
                                latest_time_str = latest_time.strftime('%H:%M:%S')
                            else:
                                latest_time_str = str(latest_time)
                                
                            logger.info(f"比较时间: {post_time_str} > {latest_time_str} = {post_time_str > latest_time_str}")
                            if post_time_str > latest_time_str:
                                latest_time = post_time
                                logger.info(f"更新latest_time: {latest_time} ({type(latest_time).__name__})")
                        
                        # 添加到批处理值
                        batch_values.append((
                            processed_post['title'],
                            post_date,
                            post_time,
                            processed_post['section'],
                            processed_post['comment_count'],
                            processed_post['sentiment_type'],
                            processed_post['sentiment_distribution'],
                            processed_post['key_comments']
                        ))
                        logger.info(f"添加到批处理值: {processed_post['title']}")
                        
                        # 每50条数据保存一次
                        if len(batch_values) >= self.batch_size:
                            # 执行批量插入
                            self._execute_batch_insert(cursor, table_name, batch_values)
                            success_count += len(batch_values)
                            
                            # 更新断点
                            if latest_date and latest_time:
                                # 确保日期和时间是字符串格式
                                if isinstance(latest_date, datetime.date):
                                    latest_date = latest_date.strftime('%Y-%m-%d')
                                if isinstance(latest_time, datetime.time):
                                    latest_time = latest_time.strftime('%H:%M:%S')
                                    
                                self.update_checkpoint(section, latest_date, latest_time, len(batch_values))
                            
                            # 清空批处理值
                            batch_values = []
                            
                            # 记录日志
                            logger.info(f"已保存 {success_count}/{len(posts)} 条帖子数据到 {section} 板块")
                        
                    except Exception as e:
                        logger.error(f"处理单个帖子时出错: {e}")
                        logger.error(f"帖子数据: {post}")
                        # 继续处理下一个帖子
                        continue
                
                # 处理剩余的批处理值
                if batch_values:
                    # 执行批量插入
                    self._execute_batch_insert(cursor, table_name, batch_values)
                    success_count += len(batch_values)
                    
                    # 更新断点
                    if latest_date and latest_time:
                        # 确保日期和时间是字符串格式
                        if isinstance(latest_date, datetime.date):
                            latest_date = latest_date.strftime('%Y-%m-%d')
                        if isinstance(latest_time, datetime.time):
                            latest_time = latest_time.strftime('%H:%M:%S')
                            
                        self.update_checkpoint(section, latest_date, latest_time, len(batch_values))
                    
                    # 记录日志
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
        
        # 确保日期是字符串格式进行比较
        if isinstance(last_date, datetime.date):
            last_date = last_date.strftime('%Y-%m-%d')
        else:
            last_date = str(last_date)
            
        if isinstance(last_time, datetime.time):
            last_time = last_time.strftime('%H:%M:%S')
        else:
            last_time = str(last_time)
            
        # 确保post_date和post_time也是字符串格式
        if isinstance(post_date, datetime.date):
            post_date = post_date.strftime('%Y-%m-%d')
        else:
            post_date = str(post_date)
            
        if isinstance(post_time, datetime.time):
            post_time = post_time.strftime('%H:%M:%S')
        else:
            post_time = str(post_time)
            
        # 格式化日期和时间确保格式一致，然后进行比较
        # 确保日期格式为'YYYY-MM-DD'
        if '-' in post_date and '-' in last_date:
            # 将日期转换为datetime.date对象进行比较
            try:
                post_date_obj = datetime.datetime.strptime(post_date, '%Y-%m-%d').date()
                last_date_obj = datetime.datetime.strptime(last_date, '%Y-%m-%d').date()
                
                # 日期不同，直接比较日期
                if post_date_obj != last_date_obj:
                    return post_date_obj < last_date_obj
                
                # 日期相同，比较时间
                post_time_obj = datetime.datetime.strptime(post_time, '%H:%M:%S').time()
                last_time_obj = datetime.datetime.strptime(last_time, '%H:%M:%S').time()
                return post_time_obj <= last_time_obj
            except ValueError as e:
                logger.warning(f"日期时间格式转换失败: {e}, 将使用字符串比较")
                # 如果转换失败，回退到字符串比较
                return (post_date < last_date) or (post_date == last_date and post_time <= last_time)
        
        # 如果格式不匹配，回退到字符串比较
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
            # 如果已经是datetime.date对象，直接转为字符串
            if isinstance(date_str, datetime.date):
                return date_str.strftime('%Y-%m-%d')
                
            # 处理常见的日期格式
            if not date_str:
                return datetime.date.today().strftime('%Y-%m-%d')
                
            # 替换分隔符为标准格式
            date_str = str(date_str).replace('.', '-').replace('/', '-')
            
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
            # 如果已经是datetime.time对象，直接转为字符串
            if isinstance(time_str, datetime.time):
                return time_str.strftime('%H:%M:%S')
                
            # 处理常见的时间格式
            if not time_str:
                return datetime.datetime.now().strftime('%H:%M:%S')
                
            # 转为字符串
            time_str = str(time_str)
                
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
            # 确保日期和时间是字符串格式
            if isinstance(last_post_date, datetime.date):
                last_post_date = last_post_date.strftime('%Y-%m-%d')
            else:
                last_post_date = str(last_post_date)
                
            if isinstance(last_post_time, datetime.time):
                last_post_time = last_post_time.strftime('%H:%M:%S')
            else:
                last_post_time = str(last_post_time)
            
            logger.info(f"更新断点: section={section}, last_post_date={last_post_date}, last_post_time={last_post_time}, total_posts={total_posts}")
            
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
                    logger.info(f"更新现有断点记录: {section}")
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
                    logger.info(f"创建新断点记录: {section}")
                
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