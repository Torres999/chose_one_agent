# 网站信息分析智能体

这是一个自动化工具，用于抓取并分析财经网站BASE_URL的内容。

## 项目的主要功能和组件：
根据项目需求，各目录的功能定位如下：
- analyzers: 负责文本情感分析
- modules: 负责解析电报和评论
- scrapers: 负责页面的导航、翻页等功能（导航、选择器）
- utils: 工具类


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
- `--cutoff_date`: 指定截止日期时间，格式为"YYYY-MM-DD HH:MM:SS"
- `--end_date`: 指定开始日期时间，格式为"YYYY-MM-DD HH:MM:SS"
- `--sections`: 指定要运行的模块，可选值：
  - `看盘`: 只运行看盘板块
  - `公司`: 只运行公司板块
- `--sentiment-analyzer`: 选择情感分析器，可选值：有评论是调用DS按【输出格式】输出。
  - `snownlp`: 使用本地SnowNLP进行情感分析（移除了）
  - `deepseek`: 使用DeepSeek API进行更准确的情感分析
- `--deepseek-api-key`: DeepSeek API密钥，当使用deepseek分析器时必需
- `--use-db`: 是否启用数据库存储功能


## 输出格式

```
标题：xxx公司发布季度财报
日期：2023-05-20
时间：10:15:12
所属板块：公司
评论数量：18
评论情绪：极度积极 | 积极 | 中性 | 消极 | 极度消极
情感分布：积极 75.0% | 中性 20.0% | 消极 5.0%
关键评论：利好, 增长, 突破, 稳健, 看好
--------------------------------------------------
```