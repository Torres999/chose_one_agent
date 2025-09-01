#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股票代码和名称爬虫
从爱金股网站获取所有A股股票代码和名称并保存到数据库
"""

import requests
import time
import re
import pymysql
from bs4 import BeautifulSoup
from chose_one_agent.utils.db_config import DB_CONFIG
from chose_one_agent.utils.logging_utils import get_logger

# 设置日志
logger = get_logger(__name__)

def create_stock_table():
    """创建股票数据表"""
    try:
        conn = pymysql.connect(**DB_CONFIG)
        with conn.cursor() as cursor:
            # 创建股票表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS stocks (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
                    stock_code VARCHAR(32) UNIQUE NOT NULL COMMENT '股票代码',
                    stock_name VARCHAR(128) NOT NULL COMMENT '股票名称',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='股票代码表';
            """)
            
            # 创建索引
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_stock_code ON stocks(stock_code);
            """)
            
        conn.commit()
        conn.close()
        logger.info("股票数据表创建成功")
        return True
    except Exception as e:
        logger.error(f"创建股票数据表失败: {e}")
        return False

def scrape_stocks_from_page(page_num):
    """从指定页面抓取股票数据"""
    url = f"https://www.aijingu.com/stock/list-{page_num}.html"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1'
    }
    
    try:
        logger.info(f"正在抓取第 {page_num} 页股票数据: {url}")
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = 'utf-8'
        
        if response.status_code != 200:
            logger.error(f"页面 {page_num} 请求失败，状态码: {response.status_code}")
            return []
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 查找股票列表
        stocks = []
        
        # 根据网站结构，股票代码和名称在li标签中
        stock_items = soup.find_all('li')
        
        for item in stock_items:
            text = item.get_text().strip()
            if text and len(text) > 6:  # 过滤掉空白和太短的文本
                # 使用正则表达式提取股票代码和名称
                # 格式通常是：000001 平安银行
                match = re.match(r'^(\d{6})\s+(.+)$', text)
                if match:
                    stock_code = match.group(1)
                    stock_name = match.group(2).strip()
                    # 去除股票名称中的所有空格
                    stock_name = stock_name.replace(' ', '')
                    stocks.append({
                        'code': stock_code,
                        'name': stock_name
                    })
                    logger.debug(f"提取股票: {stock_code} - {stock_name}")
        
        logger.info(f"第 {page_num} 页提取到 {len(stocks)} 只股票")
        return stocks
        
    except Exception as e:
        logger.error(f"抓取第 {page_num} 页失败: {e}")
        return []

def save_stocks_to_db(stocks):
    """将股票数据保存到数据库"""
    if not stocks:
        return 0
        
    try:
        conn = pymysql.connect(**DB_CONFIG)
        success_count = 0
        
        with conn.cursor() as cursor:
            for stock in stocks:
                try:
                    # 使用 INSERT ... ON DUPLICATE KEY UPDATE 来处理重复和更新
                    sql = """
                        INSERT INTO stocks (stock_code, stock_name) 
                        VALUES (%s, %s)
                        ON DUPLICATE KEY UPDATE 
                        stock_name = VALUES(stock_name),
                        updated_at = CURRENT_TIMESTAMP
                    """
                    cursor.execute(sql, (stock['code'], stock['name']))
                    success_count += 1
                except Exception as e:
                    logger.error(f"保存股票 {stock['code']} 失败: {e}")
                    continue
        
        conn.commit()
        conn.close()
        logger.info(f"成功保存/更新 {success_count} 只股票")
        return success_count
        
    except Exception as e:
        logger.error(f"保存股票到数据库失败: {e}")
        return 0

def main():
    """主函数"""
    logger.info("开始执行股票爬虫")
    
    # 创建数据表
    if not create_stock_table():
        logger.error("创建股票数据表失败，退出程序")
        return
    
    total_stocks = 0
    total_pages = 44  # 根据网站信息，共44页
    
    for page_num in range(1, total_pages + 1):
        try:
            # 抓取当前页面的股票数据
            stocks = scrape_stocks_from_page(page_num)
            
            if stocks:
                # 保存到数据库
                saved_count = save_stocks_to_db(stocks)
                total_stocks += saved_count
                logger.info(f"第 {page_num}/{total_pages} 页完成，本页保存 {saved_count} 只股票")
            else:
                logger.warning(f"第 {page_num} 页没有获取到股票数据")
            
            # 添加延时避免被封
            time.sleep(1)
            
        except Exception as e:
            logger.error(f"处理第 {page_num} 页时出错: {e}")
            continue
    
    logger.info(f"股票爬虫执行完成，共处理 {total_stocks} 只股票")
    
    # 查询数据库中的股票总数
    try:
        conn = pymysql.connect(**DB_CONFIG)
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM stocks")
            db_count = cursor.fetchone()[0]
            logger.info(f"数据库中现有股票总数: {db_count}")
        conn.close()
    except Exception as e:
        logger.error(f"查询数据库股票总数失败: {e}")

if __name__ == "__main__":
    main()
