# 财经网站分析智能体

这是一个自动化工具，用于抓取并分析财经网站BASE_URL的内容。

## 项目的主要功能和组件：
根据项目需求，各目录的功能定位如下：
- analyzers: 负责文本分析
- modules: 负责解析电报和评论
- scrapers: 负责页面的导航、翻页等功能（导航、选择器）
- utils: 工具类
具体的内容如下：
1. 主程序 (main.py):
   - 解析命令行参数（截止日期、无头模式、爬取板块、调试模式、情感分析器类型等）
   - 配置日志记录
   - 解析截止日期
   - 初始化爬虫
   - 格式化和输出结果
   
2. 爬虫模块 (scrapers/):
   - base_scraper.py: 爬虫基类，提供基础爬虫功能、浏览器管理和组件初始化
   - base_navigator.py: 导航基类，负责页面导航、元素定位与交互、内容加载等功能
   
3. 模块化组件 (modules/):
   - post_extractor.py: 专注于帖子信息提取和有效性判断
   - comment_extractor.py: 专注于评论提取及评论计数获取
   - section.py: 板块配置和处理
   - data_models.py: 定义数据模型和结构

4. 文本分析模块 (analyzers/):
   - text_analyzer.py: 统一的文本分析器，整合情感分析和关键词提取功能
   - deepseek_sentiment_analyzer.py: DeepSeek API集成，提供高级情感分析功能

5. 工具模块 (utils/):
   - datetime_utils.py: 日期和时间处理工具
   - logging_utils.py: 日志记录工具
   - constants.py: 常量定义，包括财经术语列表和情感标签
   - extraction.py: 文本提取和格式化工具
   - config.py: 配置管理


## 使用方法

运行主程序:
```
python3 run.py --cutoff_date "2025-04-11 15:53" --sections "看盘" "公司"
```

或者使用提供的运行脚本:
```
./run.py --cutoff_date "2025-04-11 00:00" --sections "看盘" "公司"
```

使用DeepSeek API进行情感分析:
```
python3 run.py --cutoff_date "2025-04-11 00:00" --sections "看盘" "公司" --sentiment-analyzer deepseek --deepseek-api-key your_api_key_here
```

参数说明:
- `--cutoff_date`: 指定截止日期时间，格式为"YYYY-MM-DD HH:MM"
- `--sections`: 指定要运行的模块，可选值：
  - `看盘`: 只运行看盘板块
  - `公司`: 只运行公司板块
- `--sentiment-analyzer`: 选择情感分析器，可选值：
  - `snownlp`: 使用本地SnowNLP进行情感分析（默认）
  - `deepseek`: 使用DeepSeek API进行更准确的情感分析
- `--deepseek-api-key`: DeepSeek API密钥，当使用deepseek分析器时必需

## 系统要求
- Python 3.6及以上版本
- 支持Playwright的操作系统
- 互联网连接（使用DeepSeek API时需要）

## 输出格式

对于无评论的内容:
```
标题：xxx股票大涨
日期：2023-05-20
时间：14:30:12
所属板块：公司
--------------------------------------------------
```

对于有评论的内容:
```
标题：xxx公司发布季度财报
日期：2023-05-20
时间：10:15:12
评论情绪：正面
所属板块：公司
--------------------------------------------------
```

对于有评论的内容且使用Deepseek分析的内容:
```
标题：xxx公司发布季度财报
日期：2023-05-20
时间：10:15:12
评论情绪：正面
所属板块：公司
Deepseek情感分析：正面 (得分: 0.85)
情感分布：正面 75.0% | 中性 20.0% | 负面 5.0%
情感关键词：利好, 增长, 突破, 稳健, 看好
分析：整体评论呈现积极态度，投资者对公司业绩表现满意...
市场情绪：看多
主要观点：业绩超出市场预期，下半年有望继续增长
相关股票：xxx公司(看多), yyy公司(中性)
建议：可关注公司后续产品发布会进展
--------------------------------------------------
```