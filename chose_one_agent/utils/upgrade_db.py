# -*- coding: utf-8 -*-
"""
数据库升级脚本，为现有表添加股票信息字段
"""
import pymysql
import logging
from typing import Dict, List, Any
from chose_one_agent.utils.logging_utils import get_logger
from chose_one_agent.utils.db_config import DB_CONFIG

# 设置日志
logger = get_logger(__name__)

class DatabaseUpgrader:
    """数据库升级器"""
    
    def __init__(self, config: Dict = None):
        """
        初始化数据库升级器
        
        Args:
            config: 数据库连接配置，默认使用DB_CONFIG
        """
        self.config = config or DB_CONFIG
        self.conn = None
    
    def _get_connection(self):
        """获取数据库连接"""
        try:
            if self.conn is None or not self.conn.open:
                self.conn = pymysql.connect(**self.config)
            return self.conn
        except Exception as e:
            logger.error(f"数据库连接失败: {e}")
            raise ConnectionError(f"数据库连接失败: {e}")
    
    def upgrade_tables(self) -> bool:
        """
        升级数据库表结构，添加股票信息字段
        
        Returns:
            升级是否成功
        """
        try:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                # 升级公司板块表
                self._upgrade_table(cursor, 'company_posts')
                
                # 升级看盘板块表
                self._upgrade_table(cursor, 'watch_plate_posts')
            
            conn.commit()
            logger.info("数据库表升级完成")
            return True
            
        except Exception as e:
            logger.error(f"升级数据库表失败: {e}")
            if conn:
                conn.rollback()
            return False
    
    def _upgrade_table(self, cursor, table_name: str):
        """
        升级单个表
        
        Args:
            cursor: 数据库游标
            table_name: 表名
        """
        try:
            # 检查stock_name字段是否存在
            cursor.execute(f"SHOW COLUMNS FROM {table_name} LIKE 'stock_name'")
            if not cursor.fetchone():
                logger.info(f"为表 {table_name} 添加 stock_name 字段")
                cursor.execute(f"""
                    ALTER TABLE {table_name} 
                    ADD COLUMN stock_name VARCHAR(128) COMMENT '股票名称' AFTER key_comments
                """)
            else:
                logger.info(f"表 {table_name} 的 stock_name 字段已存在")
            
            # 检查stock_code字段是否存在
            cursor.execute(f"SHOW COLUMNS FROM {table_name} LIKE 'stock_code'")
            if not cursor.fetchone():
                logger.info(f"为表 {table_name} 添加 stock_code 字段")
                cursor.execute(f"""
                    ALTER TABLE {table_name} 
                    ADD COLUMN stock_code VARCHAR(32) COMMENT '股票代码' AFTER stock_name
                """)
            else:
                logger.info(f"表 {table_name} 的 stock_code 字段已存在")
                
        except Exception as e:
            logger.error(f"升级表 {table_name} 失败: {e}")
            raise
    
    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            self.conn = None

def main():
    """主函数"""
    try:
        logger.info("开始升级数据库表结构...")
        
        upgrader = DatabaseUpgrader()
        success = upgrader.upgrade_tables()
        
        if success:
            logger.info("数据库升级成功完成")
            print("✅ 数据库升级成功完成")
        else:
            logger.error("数据库升级失败")
            print("❌ 数据库升级失败")
            
        upgrader.close()
        
    except Exception as e:
        logger.error(f"数据库升级过程中出错: {e}")
        print(f"❌ 数据库升级过程中出错: {e}")

if __name__ == "__main__":
    main()
