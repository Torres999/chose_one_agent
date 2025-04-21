# 财经网站分析智能体

这是一个自动化工具，用于抓取并分析财经网站BASE_URL的内容。

## 项目的主要功能和组件：
根据项目需求，各目录的功能定位如下：
- analyzers: 负责文本分析
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
- `--cutoff_date`: 指定截止日期时间，格式为"YYYY-MM-DD HH:MM"
- `--sections`: 指定要运行的模块，可选值：
  - `看盘`: 只运行看盘板块
  - `公司`: 只运行公司板块
- `--sentiment-analyzer`: 选择情感分析器，可选值：默认是0分/无评论，如果程序报错不用显示“分析失败”直接终止程序运行。评论的情感分析有0、1、2、3、4、5六档，0代表没有评论、1代表消极、5代表积极。
  - `snownlp`: 使用本地SnowNLP进行情感分析（默认）
  - `deepseek`: 使用DeepSeek API进行更准确的情感分析
- `--deepseek-api-key`: DeepSeek API密钥，当使用deepseek分析器时必需

## 输出格式

```
标题：xxx公司发布季度财报
日期：2023-05-20
时间：10:15:12
所属板块：公司
评论数量：18
评论情绪：极度积极 | 积极 | 中性 | 消极 | 极度消极
情感分布：积极 75.0% | 中性 20.0% | 消极 5.0%
评论洞察：利好, 增长, 突破, 稳健, 看好
--------------------------------------------------
```