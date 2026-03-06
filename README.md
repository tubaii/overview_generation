# 学术综述生成系统
## 使用步骤

### 1.配置环境
```
1. 创建虚拟环境，推荐虚拟环境python版本为3.11
2. 下载所有依赖包：pip install -r requirements.txt
```
### 2.配置config
```
1. 替换config.py中OPENAI_CONFIG的'base_url'，‘api_key’，'model'三个键，model推荐使用qwen-long系列
2. 可根据需要调整快速模式和深度模式所对应的文献搜索个数，SEARCH_CONFIG和SEARCH_CONFIG2，快速模式主要根据摘要书写综述，深度模式将试图提取技术章节所对应的论文的全文用于书写综述的技术部分
```
### 3.给openalex库的申请信息加邮箱后缀用于返回摘要
```
1. 在paper_search_filter.py文件中修改OpenAlexClient类的self.email数据为自己的邮箱
```
## 注意事项
```
1. semantic scholar库需要进行认证申请，否则速度较慢
2. 关键词仅支持英文
3. 请确保已配置有效的OpenAI API密钥
4. 深度模式生成时间较长，请耐心等待
```
# Web界面使用说明
## 简介

本系统提供两种运行方式：
1. **命令行界面** - 通过终端运行
2. **Web界面** - 通过浏览器访问

## Web界面使用

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 启动Web服务器

```bash
python app.py
打开浏览器，访问：http://localhost:5000
或者直接运行main.py可直接下载所得论文的docx版本，格式已经调好，参考文献的来源可能出现Unknown需要人工补充
```
## Web界面功能

### 输入参数

| 参数 | 说明 |
|------|------|
| 搜索关键词 | 输入要搜索的学术主题，如 "transformer", "deep learning" |
| 生成模式 | 快速模式（约5000字）或深度模式（约12500字） |

### 操作流程

1. 在输入框中输入搜索关键词
2. 选择生成模式（快速/深度）
3. 点击"开始生成综述"按钮
4. 等待生成完成（可在进度条查看状态）
5. 生成完成后，点击"下载DOCX文件"保存结果

## 进度说明

生成过程包含以下步骤：
- 搜索论文（从Arxiv、OpenAlex等数据源）
- 合并去重
- 生成大纲
- 撰写综述正文
- 保存文件

根据数据量和网络情况，整个过程可能需要3-10分钟。

## 文件结构

```
Overview_generation_r/
├── app.py              # Flask Web应用
├── templates/
│   └── index.html      # Web界面模板
├── main.py             # 命令行主程序
├── config.py           # 配置文件
├── paper_search_filter.py  # 论文搜索模块
├── outline_generator.py    # 大纲生成模块
├── review_writer.py        # 综述撰写模块
├── format_check.py         # 格式检查模块
├── hallucination_check.py  # 幻觉检测模块
├── token_counter.py        # Token计数模块
├── check_modules.py        # 模块导入检查脚本
├── test_token_counter.py        # Token计数器测试脚本
├── debug_citations.py        # 调试引用问题的脚本
├── system_check.py         # 系统检查工具
├── requirements.txt        # 依赖列表
└── README.md              # 本说明文档
```

## 技术栈

- **后端**: Flask + OpenAI API
- **前端**: HTML5 + CSS3 + JavaScript
- **文档**: python-docx











