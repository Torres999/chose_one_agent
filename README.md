# ChoseOne财经网站分析智能体

这是一个自动化工具，用于抓取并分析财经网站ChoseOne.cn的内容。

## 功能

- 自动访问ChoseOne.cn网站并导航至"电报"和"盯盘"板块
- 逐个读取内容直到达到指定日期时间
- 对所有内容记录标题、日期、时间
- 对有评论的内容获取评论并进行情感分析
- 输出格式化的结果

## 项目的主要功能和组件：
1. 基础爬虫模块 (base_scraper.py):
   - 提供共用的网页交互功能
   - 可被不同功能模块继承使用
   - 创建了基础爬虫类"BaseScraper"作为公共基类

2. 模块化系统设计:
   - 采用模块化设计，增加了"modules"目录
   - 将电报功能放在"telegraph"模块中
   - 添加了"watch_plate"模块用于盯盘功能
   - 更新了主程序以支持选择运行特定模块

3. 电报模块 (telegraph_scraper.py):
   - 自动导航到ChoseOne.cn网站的"电报"下的"看盘"和"公司"板块
   - 逐个读取电报内容，直到达到指定的截止日期
   - 对有评论的电报进行评论抓取和情感分析

4. 盯盘模块 (watch_plate_scraper.py):
   - 自动导航到ChoseOne.cn网站的"盯盘"板块
   - 分析盯盘内容和评论

5. 情感分析模块 (sentiment_analyzer.py):
   - 使用SnowNLP进行中文情感分析
   - 对多条评论进行综合分析，得出整体情感倾向

6. 辅助工具模块 (helpers.py):
   - 日期时间处理
   - 格式化输出结果

7. 主程序 (main.py):
   - 处理命令行参数
   - 协调各个模块的运行
   - 格式化并输出最终结果

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

## 使用方法

运行主程序:
```
python3 -m chose_one_agent.main --cutoff_date "2025-04-11 00:00" --module all
```

或者使用提供的运行脚本:
```
./run.py --cutoff_date "2025-04-11 00:00" --module all
```

参数说明:
- `--cutoff_date`: 指定截止日期时间，格式为"YYYY-MM-DD HH:MM"
- `--module`: 指定要运行的模块，可选值：
  - `telegraph`: 只运行电报模块
  - `watch_plate`: 只运行盯盘模块
  - `all`: 运行所有模块（默认）

## 系统要求
- Python 3.6及以上版本
- 支持Playwright的操作系统

## 输出格式

对于无评论的内容:
```
标题：xxx股票大涨
日期：2023-05-20
时间：14:30
--------------------------------------------------
```

对于有评论的内容:
```
标题：xxx公司发布季度财报
日期：2023-05-20
时间：10:15
评论情绪：正面
--------------------------------------------------
```
