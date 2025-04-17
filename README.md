# 财经网站分析智能体

这是一个自动化工具，用于抓取并分析财经网站BASE_URL的内容。

## 功能

- 自动访问ChoseOne.cn网站并导航至"电报"和"盯盘"板块
- 逐个读取内容直到达到指定日期时间
- 对所有内容记录标题、日期、时间
- 对有评论的内容获取评论并进行情感分析
  - 支持使用本地SnowNLP进行情感分析
  - 支持使用DeepSeek API进行更准确的情感分析
- 输出格式化的结果

## 项目的主要功能和组件：
1. 主程序 (main.py):
   - 解析命令行参数
   - 配置日志记录
   - 解析截止日期
   - 初始化爬虫
   - 格式化和输出结果
   
2. 爬虫基础模块 (scrapers/):
   - 提供所有爬虫的基类和通用功能
   - 定义通用选择器和页面交互方法

3. 电报爬虫模块 (modules/)
   - post_extractor.py: 专注于帖子信息提取
   - comment_extractor.py: 专注于评论提取

5. 情感分析模块 (modules/sentiment/)
   - base_analyzer.py: 情感分析基类
   - snownlp_analyzer.py: 简单情感分析实现
   - deepseek_analyzer.py: DeepSeek API集成
   - 关键词分析模块 (analyzers/keyword_analyzer.py)

6. 工具模块 (utils/)
   - 日期处理
   - 文本处理
   - 辅助函数

## 安装

1. 克隆仓库
```
git clone <repository_url>
cd ChoseOneAgent
```

2. 安装依赖
```
pip3 install -r requirements.txt
```

3. 安装Playwright浏览器
```
python3 -m playwright install
```

4. 设置DeepSeek API (可选)
```
cp .env.example .env
```
然后编辑.env文件，添加你的DeepSeek API密钥:
```
DEEPSEEK_API_KEY=your_api_key_here
```

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

或者设置好.env文件后，只需指定使用DeepSeek:
```
python3 run.py --cutoff_date "2025-04-11 00:00" --sections "看盘" "公司" --sentiment-analyzer deepseek
```

参数说明:
- `--cutoff_date`: 指定截止日期时间，格式为"YYYY-MM-DD HH:MM"
- `--sections`: 指定要运行的模块，可选值：
  - `看盘`: 只运行看盘板块
  - `公司`: 只运行公司板块
- `--sentiment-analyzer`: 选择情感分析器，可选值：
  - `snownlp`: 使用本地SnowNLP进行情感分析（默认）
  - `deepseek`: 使用DeepSeek API进行更准确的情感分析
- `--deepseek-api-key`: DeepSeek API密钥，当使用deepseek分析器时必需，也可通过.env文件设置

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

# 代码重构说明

## 文本分析器重构

为了减少代码行数和文件数量，我们对文本分析相关的代码进行了重构：

### 主要变更

1. 将以下三个文件整合为一个文件：
   - `chose_one_agent/analyzers/base_analyzer.py`
   - `chose_one_agent/analyzers/keyword_analyzer.py`
   - `chose_one_agent/modules/telegraph/analyzer.py` (部分功能)

2. 新创建了统一的文本分析器类：
   - `chose_one_agent/analyzers/text_analyzer.py` 包含 `TextAnalyzer` 类

3. 重写了 Telegraph 分析器：
   - 现在 `TelegraphAnalyzer` 使用 `TextAnalyzer` 作为分析引擎

### 使用方法变更

如果您之前直接使用 `BaseAnalyzer` 或 `KeywordAnalyzer`，需要更新导入路径：

```python
# 旧的导入方式
from chose_one_agent.analyzers.base_analyzer import BaseAnalyzer
from chose_one_agent.analyzers.keyword_analyzer import KeywordAnalyzer, FINANCIAL_TERMS

# 新的导入方式
from chose_one_agent.analyzers.text_analyzer import TextAnalyzer, FINANCIAL_TERMS
```

### 功能调用示例

```python
# 创建文本分析器
analyzer = TextAnalyzer(
    sentiment_analyzer_type="snownlp",  # 可选: "snownlp", "deepseek", "simple"
    deepseek_api_key=None,  # DeepSeek API密钥，可选
    min_keyword_length=2,  # 关键词最小长度
    max_keywords=10,  # 最大关键词数量
    custom_stopwords=None,  # 自定义停用词
    custom_keywords=None,  # 自定义关键词
    debug=False  # 是否开启调试模式
)

# 关键词分析
keywords = analyzer.extract_keywords("这是一段测试文本，关于股票市场的分析", top_n=5)
keyword_results = analyzer.analyze_text("这是一段测试文本，关于股票市场的分析")

# 情感分析
sentiment = analyzer.analyze_sentiment("股市上涨，投资者信心增强")
```