# -*- coding: utf-8 -*-
"""
股票信息提取器模块，用于从电报标题中提取股票名称和代码
"""
import re
import logging
import pymysql
from typing import Dict, List, Tuple, Optional
from chose_one_agent.utils.logging_utils import get_logger
from chose_one_agent.utils.db_config import DB_CONFIG

# 获取日志记录器
logger = get_logger(__name__)

class StockExtractor:
    """股票信息提取器"""
    
    def __init__(self):
        """初始化股票提取器"""
        # 股票代码正则表达式模式
        self.stock_patterns = {
            # A股：6位数字，以60、00、30开头
            'a_stock': r'([60]\d{5}|00\d{4}|30\d{4})',
            # 港股：4-5位数字，可能带.HK后缀
            'hk_stock': r'(\d{4,5}(?:\.HK)?)',
            # 美股：1-5位字母，可能带.NASDAQ或.NYSE后缀
            'us_stock': r'([A-Z]{1,5}(?:\.NASDAQ|\.NYSE)?)',
            # 科创板：以688开头的6位数字
            'star_board': r'(688\d{3})',
            # 创业板：以300、301开头的6位数字
            'gem_board': r'(30[01]\d{3})'
        }
        
        # 股票代码缓存：从数据库加载并缓存所有股票代码
        self.stock_cache = self._load_stock_cache()
        
        # 常见股票名称关键词
        self.stock_keywords = [
            '股份', '集团', '科技', '生物', '医药', '医疗', '电子', '半导体', '新能源',
            '汽车', '银行', '保险', '证券', '地产', '房地产', '建筑', '钢铁', '煤炭',
            '石油', '化工', '农业', '食品', '饮料', '服装', '零售', '物流', '运输'
        ]
        
        # 股票名称后缀
        self.stock_suffixes = [
            '股份', '集团', '有限', '公司', '企业', '实业', '投资', '控股', '科技',
            '生物', '医药', '医疗', '电子', '半导体', '新能源', '汽车', '银行',
            '保险', '证券', '地产', '房地产', '建筑', '钢铁', '煤炭', '石油',
            '化工', '农业', '食品', '饮料', '服装', '零售', '物流', '运输'
        ]
    
    def extract_stock_info(self, title: str) -> Dict[str, Optional[str]]:
        """
        从标题中提取股票信息
        
        Args:
            title: 电报标题
            
        Returns:
            包含股票名称和代码的字典
        """
        if not title:
            return {'stock_name': None, 'stock_code': None}
        
        # 先提取股票名称
        stock_name = self._extract_stock_name(title)
        
        # 如果提取到股票名称，从缓存中查找股票代码
        stock_code = None
        if stock_name:
            stock_code = self._get_stock_code_from_cache(stock_name)
        
        result = {
            'stock_name': stock_name,
            'stock_code': stock_code
        }
        
        if stock_name:
            if stock_code and stock_code != "失败":
                logger.info(f"从标题 '{title}' 中提取到股票信息: {result}")
            else:
                result['stock_code'] = "失败"
                logger.info(f"从标题 '{title}' 中提取到股票信息: {result}")
        
        return result
    
    def _extract_stock_code(self, title: str) -> Optional[str]:
        """
        从标题中提取股票代码（已废弃，保留方法签名以兼容现有代码）
        
        Args:
            title: 电报标题
            
        Returns:
            股票代码，如果未找到则返回None
        """
        # 原有的股票代码提取逻辑已删除，因为公司板块标题通常不包含股票代码
        # 股票代码现在通过公司名称从数据库缓存中获取
        return None
    
    def _extract_stock_name(self, title: str) -> Optional[str]:
        """
        从标题中提取股票名称
        
        Args:
            title: 电报标题
            
        Returns:
            股票名称，如果未找到则返回None
        """
        # 策略1：基于冒号分割的精确提取（最高优先级）
        colon_name = self._extract_name_by_colon(title)
        if colon_name:
            return colon_name
        
        # 策略2：基于ST标记的识别
        st_name = self._extract_name_by_st_mark(title)
        if st_name:
            return st_name
        
        # 策略3：基于数字板模式的识别
        board_name = self._extract_name_by_board_pattern(title)
        if board_name:
            return board_name
        
        # 策略4：如果标题中包含股票代码，尝试提取代码前的公司名称
        # 注意：此策略已简化，不再依赖股票代码参数
        code_name = self._extract_name_by_stock_code(title, None)
        if code_name:
            return code_name
        
        # 策略5：基于股票关键词的智能识别
        keyword_name = self._extract_name_by_keywords(title)
        if keyword_name:
            return keyword_name
        
        # 策略6：提取标题中的中文公司名称（最后手段）
        chinese_name = self._extract_chinese_company_name(title)
        if chinese_name:
            return chinese_name
        
        return None
    
    def _clean_stock_name(self, name: str) -> str:
        """
        清理股票名称
        
        Args:
            name: 原始名称
            
        Returns:
            清理后的名称
        """
        if not name:
            return ""
        
        # 移除特殊字符和标点符号
        cleaned = re.sub(r'[^\u4e00-\u9fff\w\s]', '', name)
        
        # 移除多余空格
        cleaned = re.sub(r'\s+', '', cleaned)
        
        # 移除常见的无关词汇
        remove_words = ['关于', '公告', '通知', '报告', '分析', '点评', '解读', '快讯', '新闻']
        for word in remove_words:
            cleaned = cleaned.replace(word, '')
        
        return cleaned.strip()
    
    def _extract_chinese_company_name(self, title: str) -> Optional[str]:
        """
        从标题中提取中文公司名称
        
        Args:
            title: 电报标题
            
        Returns:
            公司名称，如果未找到则返回None
        """
        # 查找连续的中文字符（2-10个字符）
        chinese_pattern = r'[\u4e00-\u9fff]{2,10}'
        matches = re.findall(chinese_pattern, title)
        
        if matches:
            # 过滤掉常见的非公司名称词汇
            filtered_matches = []
            for match in matches:
                if not self._is_common_word(match):
                    filtered_matches.append(match)
            
            if filtered_matches:
                # 返回最长的匹配项
                return max(filtered_matches, key=len)
        
        return None
    
    def _is_common_word(self, word: str) -> bool:
        """
        判断是否为常见词汇（非公司名称）
        
        Args:
            word: 待判断的词汇
            
        Returns:
            如果是常见词汇返回True，否则返回False
        """
        common_words = {
            '今日', '昨日', '明天', '本周', '本月', '今年', '去年',
            '上午', '下午', '晚上', '凌晨', '中午',
            '开盘', '收盘', '涨停', '跌停', '上涨', '下跌', '震荡',
            '市场', '股市', 'A股', '港股', '美股', '科创板', '创业板',
            '板块', '概念', '题材', '热点', '龙头', '龙头股',
            '分析师', '专家', '机构', '基金', '券商', '银行',
            '政策', '消息', '利好', '利空', '影响', '预期', '展望'
        }
        
        return word in common_words
    
    def batch_extract(self, titles: List[str]) -> List[Dict[str, Optional[str]]]:
        """
        批量提取股票信息
        
        Args:
            titles: 标题列表
            
        Returns:
            股票信息列表
        """
        results = []
        for title in titles:
            stock_info = self.extract_stock_info(title)
            results.append(stock_info)
        
        return results
    
    def _load_stock_cache(self) -> Dict[str, str]:
        """
        从数据库加载所有股票代码并缓存
        
        Returns:
            股票名称到股票代码的映射字典
        """
        cache = {}
        try:
            conn = pymysql.connect(**DB_CONFIG)
            with conn.cursor() as cursor:
                cursor.execute("SELECT stock_name, stock_code FROM stocks")
                results = cursor.fetchall()
                
                for stock_name, stock_code in results:
                    if stock_name and stock_code:
                        cache[stock_name] = stock_code
                        
            conn.close()
            logger.info(f"从数据库加载了 {len(cache)} 只股票的代码缓存")
            
        except Exception as e:
            logger.error(f"从数据库加载股票代码缓存失败: {e}")
            
        return cache
    
    def _get_stock_code_from_cache(self, company_name: str) -> str:
        """
        从缓存中查找股票代码
        
        Args:
            company_name: 公司名称
            
        Returns:
            股票代码，如果未找到则返回"失败"
        """
        if not company_name:
            return "失败"
            
        # 精确匹配
        if company_name in self.stock_cache:
            return self.stock_cache[company_name]
            
        # 模糊匹配：查找包含公司名称的股票
        for stock_name, stock_code in self.stock_cache.items():
            if company_name in stock_name or stock_name in company_name:
                return stock_code
                
        logger.warning(f"未在数据库中找到公司 '{company_name}' 的股票代码")
        return "失败"
    

    
    def _extract_name_by_colon(self, title: str) -> Optional[str]:
        """
        策略1：基于冒号分割的精确提取
        
        Args:
            title: 电报标题
            
        Returns:
            股票名称，如果未找到则返回None
        """
        try:
            # 查找冒号位置
            colon_index = title.find('：')
            if colon_index > 0:
                # 提取冒号前的文本
                before_colon = title[:colon_index].strip()
                
                # 移除【】符号
                before_colon = before_colon.replace('【', '').replace('】', '').strip()
                
                # 验证提取的名称是否符合要求
                if self._is_valid_stock_name(before_colon):
                    logger.debug(f"冒号分割法提取到股票名称: {before_colon}")
                    return before_colon
        except Exception as e:
            logger.debug(f"冒号分割法提取失败: {e}")
        
        return None
    
    def _extract_name_by_st_mark(self, title: str) -> Optional[str]:
        """
        策略2：基于ST标记的识别
        
        Args:
            title: 电报标题
            
        Returns:
            股票名称，如果未找到则返回None
        """
        try:
            # ST标记的正则表达式
            st_patterns = [
                r'【\*?ST\s*([^：]+)：',  # 【*ST新元：或【ST新元：
                r'\*?ST\s*([^：\s]+)',   # *ST新元 或 ST新元
            ]
            
            for pattern in st_patterns:
                matches = re.findall(pattern, title)
                if matches:
                    stock_name = matches[0].strip()
                    if self._is_valid_stock_name(stock_name):
                        logger.debug(f"ST标记法提取到股票名称: {stock_name}")
                        return stock_name
        except Exception as e:
            logger.debug(f"ST标记法提取失败: {e}")
        
        return None
    
    def _extract_name_by_board_pattern(self, title: str) -> Optional[str]:
        """
        策略3：基于数字板模式的识别
        
        Args:
            title: 电报标题
            
        Returns:
            股票名称，如果未找到则返回None
        """
        try:
            # 数字板模式：如"4天3板南京商旅"
            board_patterns = [
                r'【\d+天\d+板([^：]+)：',  # 【4天3板南京商旅：
                r'\d+天\d+板([^：\s]+)',   # 4天3板南京商旅
            ]
            
            for pattern in board_patterns:
                matches = re.findall(pattern, title)
                if matches:
                    full_text = matches[0].strip()
                    
                    # 进一步提取数字板后面的公司名称
                    # 移除"X天X板"部分，只保留公司名称
                    company_name = re.sub(r'^\d+天\d+板', '', full_text).strip()
                    
                    if self._is_valid_stock_name(company_name):
                        logger.debug(f"数字板模式法提取到股票名称: {company_name}")
                        return company_name
                    elif self._is_valid_stock_name(full_text):
                        # 如果移除后无效，返回原文本
                        logger.debug(f"数字板模式法提取到股票名称: {full_text}")
                        return full_text
        except Exception as e:
            logger.debug(f"数字板模式法提取失败: {e}")
        
        return None
    
    def _extract_name_by_stock_code(self, title: str, stock_code: str) -> Optional[str]:
        """
        策略4：基于股票代码提取公司名称
        
        Args:
            title: 电报标题
            stock_code: 股票代码
            
        Returns:
            股票名称，如果未找到则返回None
        """
        try:
            # 查找代码在标题中的位置
            code_index = title.find(stock_code)
            if code_index > 0:
                # 提取代码前的文本作为可能的公司名称
                before_code = title[:code_index].strip()
                if before_code:
                    # 清理文本，移除特殊字符
                    cleaned_name = self._clean_stock_name(before_code)
                    if self._is_valid_stock_name(cleaned_name):
                        logger.debug(f"股票代码法提取到股票名称: {cleaned_name}")
                        return cleaned_name
        except Exception as e:
            logger.debug(f"股票代码法提取失败: {e}")
        
        return None
    
    def _extract_name_by_keywords(self, title: str) -> Optional[str]:
        """
        策略5：基于股票关键词的智能识别
        
        Args:
            title: 电报标题
            
        Returns:
            股票名称，如果未找到则返回None
        """
        try:
            for keyword in self.stock_keywords:
                if keyword in title:
                    # 查找关键词周围的文本
                    keyword_index = title.find(keyword)
                    if keyword_index >= 0:
                        # 提取关键词前后的文本
                        start_pos = max(0, keyword_index - 10)
                        end_pos = min(len(title), keyword_index + len(keyword) + 10)
                        
                        potential_name = title[start_pos:end_pos].strip()
                        cleaned_name = self._clean_stock_name(potential_name)
                        
                        if self._is_valid_stock_name(cleaned_name):
                            logger.debug(f"关键词法提取到股票名称: {cleaned_name}")
                            return cleaned_name
        except Exception as e:
            logger.debug(f"关键词法提取失败: {e}")
        
        return None
    
    def _is_valid_stock_name(self, name: str) -> bool:
        """
        验证股票名称是否有效
        
        Args:
            name: 待验证的股票名称
            
        Returns:
            是否有效
        """
        if not name or len(name) < 2 or len(name) > 8:
            return False
        
        # 排除包含负面词汇的名称
        negative_words = [
            '涉嫌', '违规', '立案', '调查', '处罚', '风险', '问题', '异常',
            '下跌', '跌停', '亏损', '亏损', '退市', 'ST', '暂停', '终止',
            '只', '披露', '上半年', '业绩', '预告', '环比', '预增', '超',
            '今日', '市场', '整体', '上涨', '指数', '大涨', '情绪', '回暖',
            '投资者', '信心', '增强', '政策', '利好', '频出', '预期', '改善'
        ]
        
        for word in negative_words:
            if word in name:
                return False
        
        # 排除纯数字或纯英文
        if name.isdigit() or name.isascii():
            return False
        
        # 确保包含中文字符
        if not re.search(r'[\u4e00-\u9fff]', name):
            return False
        
        # 排除包含过多数字的名称
        if len(re.findall(r'\d', name)) > 1:
            return False
        
        return True
