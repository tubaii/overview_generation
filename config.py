"""
学术综述生成系统配置文件

此文件包含系统运行所需的所有配置参数。
用户可以通过修改此文件来调整系统行为，而无需修改代码。
"""

# =============================================================================
# 大模型配置
# =============================================================================

# OpenAI兼容API配置
OPENAI_CONFIG = {
    'base_url': 'https://...',  # API基础URL
    'api_key': '...',  # API密钥
    'model': 'qwen-long',  # 使用的模型名称，可替换
    'temperature': 0.7,  # 生成温度（0.0-1.0，越高越随机）
    'max_tokens': 8000,  # 最大token数
    'timeout': 180  # 请求超时时间（秒）
}

# =============================================================================
# 论文搜索配置
# =============================================================================

# 各数据源的搜索数量配置
#用于快速模式
SEARCH_CONFIG = {
    'arxiv_count': 50,  # Arxiv搜索数量
    'openalex_latest': 100,  # OpenAlex最新论文数量
    'openalex_cited': 100,  # OpenAlex高引用论文数量
    'semantic_latest':0,  # Semantic Scholar最新论文数量
    'semantic_cited': 0,  # Semantic Scholar高引用论文数量
    'reference_paper_count': 30,  # 参考文献数量（用于综述撰写）
    'citation_paper_count': 15,  # 引用文献数量（用于文中详细引用叙述）
}
#用于深度模式
SEARCH_CONFIG2 = {
    'arxiv_count': 50,  # Arxiv搜索数量
    'openalex_latest': 100,  # OpenAlex最新论文数量
    'openalex_cited': 100,  # OpenAlex高引用论文数量
    'semantic_latest':0,  # Semantic Scholar最新论文数量
    'semantic_cited': 0,  # Semantic Scholar高引用论文数量
    'reference_paper_count': 50,  # 参考文献数量（用于综述撰写）
    'citation_paper_count': 30,  # 引用文献数量（用于文中详细引用叙述）
}
# =============================================================================
# 全文获取配置
# =============================================================================

# 智能全文获取配置
FULLTEXT_CONFIG = {
    'smart_fulltext_enabled': True,  # 是否默认启用智能全文获取
    'max_retries': 15,  # 最大重试次数
    'retry_delay': 2,  # 重试延迟（秒）
    'timeout': 30,  # 请求超时时间（秒）
}

# =============================================================================
# 系统配置
# =============================================================================

# 系统运行配置
SYSTEM_CONFIG = {
    'log_level': 'INFO',  # 日志级别
    'max_workers': 4,  # 并发工作线程数
    'cache_enabled': True,  # 是否启用缓存
    'cache_dir': './cache',  # 缓存目录
}

# =============================================================================
# 论文质量评估阈值
# =============================================================================

# 论文评估配置
QUALITY_CONFIG = {
    'recent_paper_years': 2,  # 近期论文年限（年）
    'high_citation_threshold': 20,  # 高引用论文阈值
    'min_summary_length': 50,  # 摘要最小长度
}

# =============================================================================
# 输出配置
# =============================================================================

# 文档输出配置
OUTPUT_CONFIG = {
    'output_dir': './output',  # 输出目录
    'docx_template': None,  # Word模板文件路径（None表示使用默认）
    'font_name': '仿宋',  # 中文字体
    'english_font': 'Times New Roman',  # 英文字体
    'font_size': 12,  # 字体大小
}

# =============================================================================
# 运行时配置
# =============================================================================

# 运行时行为配置
RUNTIME_CONFIG = {
    'enable_debug': False,  # 是否启用调试模式
    'use_default_config': False,  # 是否使用默认配置（不询问用户）
    'verbose_output': True,  # 是否显示详细输出
    'save_intermediate_files': False,  # 是否保存中间文件
    'generation_mode': 'fast',  # 生成模式：'fast'（快速，约5000字）或 'deep'（深度，约12500字）
}

# =============================================================================
# 用户输入配置
# =============================================================================

# 用户输入参数配置（默认情况下需要问询用户的参数）
USER_INPUT_CONFIG = {
    'search_keyword': 'transformer',  # 搜索关键词（默认值）
    'enable_parameter_config': False,  # 是否启用参数配置询问（如果为True，则运行时仍会询问用户）
    'enable_keyword_input': True,  # 是否启用关键词输入询问（如果为True，则运行时仍会询问用户）
    'enable_fulltext_config': True,  # 是否启用全文获取配置询问（如果为True，则运行时仍会询问用户）
    'enable_save_config': True,  # 是否启用保存文件询问（如果为False，则自动保存）
}

# =============================================================================
# 路径配置
# =============================================================================

# 文件路径配置
PATH_CONFIG = {
    'output_dir': './output',  # 输出目录
    'cache_dir': './cache',  # 缓存目录
    'log_dir': './logs',  # 日志目录
    'temp_dir': './temp',  # 临时文件目录
}

# =============================================================================
# 配置获取函数
# =============================================================================

def get_openai_config():
    """
    获取OpenAI配置

    Returns:
        dict: OpenAI配置字典
    """
    return OPENAI_CONFIG.copy()


def get_search_config():
    """
    获取搜索配置

    Returns:
        dict: 搜索配置字典
    """
    return SEARCH_CONFIG.copy()
def get_search_config2():
    """
    获取搜索配置

    Returns:
        dict: 搜索配置字典
    """
    return SEARCH_CONFIG2.copy()

def get_fulltext_config():
    """
    获取全文获取配置

    Returns:
        dict: 全文获取配置字典
    """
    return FULLTEXT_CONFIG.copy()


def get_system_config():
    """
    获取系统配置

    Returns:
        dict: 系统配置字典
    """
    return SYSTEM_CONFIG.copy()


def get_quality_config():
    """
    获取质量评估配置

    Returns:
        dict: 质量评估配置字典
    """
    return QUALITY_CONFIG.copy()


def get_output_config():
    """
    获取输出配置

    Returns:
        dict: 输出配置字典
    """
    return OUTPUT_CONFIG.copy()


def get_runtime_config():
    """
    获取运行时配置

    Returns:
        dict: 运行时配置字典
    """
    return RUNTIME_CONFIG.copy()


def get_path_config():
    """
    获取路径配置

    Returns:
        dict: 路径配置字典
    """
    return PATH_CONFIG.copy()


def get_user_input_config():
    """
    获取用户输入配置

    Returns:
        dict: 用户输入配置字典
    """
    return USER_INPUT_CONFIG.copy()


# =============================================================================
# 配置验证函数
# =============================================================================

def validate_config():
    """
    验证配置文件的正确性

    Returns:
        tuple: (is_valid, error_messages)
    """
    errors = []

    # 验证OpenAI配置
    if not OPENAI_CONFIG.get('base_url'):
        errors.append("OpenAI base_url 不能为空")

    if not OPENAI_CONFIG.get('api_key'):
        errors.append("OpenAI api_key 不能为空")

    if not OPENAI_CONFIG.get('model'):
        errors.append("OpenAI model 不能为空")

    # 验证搜索配置
    search_total = SEARCH_CONFIG['arxiv_count'] + SEARCH_CONFIG['openalex_latest'] + \
                   SEARCH_CONFIG['openalex_cited'] + SEARCH_CONFIG['semantic_latest'] + \
                   SEARCH_CONFIG['semantic_cited']

    if search_total < 10:
        errors.append("总搜索论文数量过少，建议至少10篇")

    if SEARCH_CONFIG['citation_paper_count'] > search_total:
        errors.append("引用文献数量不能超过总搜索数量")

    # 验证质量配置
    if QUALITY_CONFIG['recent_paper_years'] < 1:
        errors.append("近期论文年限至少为1年")

    if QUALITY_CONFIG['high_citation_threshold'] < 1:
        errors.append("高引用阈值至少为1")

    # 验证用户输入配置
    if not USER_INPUT_CONFIG.get('search_keyword'):
        errors.append("搜索关键词不能为空")

    return len(errors) == 0, errors


def print_config_summary():
    """
    打印配置摘要
    """
    print("=" * 60)
    print("学术综述生成系统配置摘要")
    print("=" * 60)

    print("大模型配置:")
    print(f"  模型: {OPENAI_CONFIG['model']}")
    print(f"  温度: {OPENAI_CONFIG['temperature']}")
    print(f"  最大token: {OPENAI_CONFIG['max_tokens']}")

    print("\n搜索配置:")
    print(f"  Arxiv: {SEARCH_CONFIG['arxiv_count']}篇")
    print(f"  OpenAlex: {SEARCH_CONFIG['openalex_latest']}篇最新 + {SEARCH_CONFIG['openalex_cited']}篇高引用")
    print(f"  Semantic Scholar: {SEARCH_CONFIG['semantic_latest']}篇最新 + {SEARCH_CONFIG['semantic_cited']}篇高引用")
    print(f"  参考文献: {SEARCH_CONFIG['reference_paper_count']}篇（用于综述撰写）")
    print(f"  引用文献: {SEARCH_CONFIG['citation_paper_count']}篇（用于文中详细引用）")

    print(f"\n全文获取: {'启用' if FULLTEXT_CONFIG['smart_fulltext_enabled'] else '禁用'}")

    print(f"\n输出目录: {OUTPUT_CONFIG['output_dir']}")
    print("=" * 60)


def print_current_config():
    """
    打印当前所有配置信息
    """
    print("=" * 80)
    print("学术综述生成系统 - 当前配置")
    print("=" * 80)

    print("\n【大模型配置】")
    print(f"  API地址: {OPENAI_CONFIG['base_url']}")
    print(f"  模型: {OPENAI_CONFIG['model']}")
    print(f"  温度: {OPENAI_CONFIG['temperature']}")
    print(f"  最大Token: {OPENAI_CONFIG['max_tokens']}")
    print(f"  超时时间: {OPENAI_CONFIG['timeout']}秒")

    print("\n【搜索配置】")
    print(f"  Arxiv论文数: {SEARCH_CONFIG['arxiv_count']}")
    print(f"  OpenAlex最新论文数: {SEARCH_CONFIG['openalex_latest']}")
    print(f"  OpenAlex高引用论文数: {SEARCH_CONFIG['openalex_cited']}")
    print(f"  Semantic Scholar最新论文数: {SEARCH_CONFIG['semantic_latest']}")
    print(f"  Semantic Scholar高引用论文数: {SEARCH_CONFIG['semantic_cited']}")
    print(f"  参考文献数: {SEARCH_CONFIG['reference_paper_count']}（用于综述撰写）")
    print(f"  引用文献数: {SEARCH_CONFIG['citation_paper_count']}（用于文中详细引用）")

    print("\n【全文获取配置】")
    print(f"  默认启用智能全文获取: {'是' if FULLTEXT_CONFIG['smart_fulltext_enabled'] else '否'}")
    print(f"  最大重试次数: {FULLTEXT_CONFIG['max_retries']}")
    print(f"  重试延迟: {FULLTEXT_CONFIG['retry_delay']}秒")
    print(f"  请求超时: {FULLTEXT_CONFIG['timeout']}秒")

    print("\n【系统配置】")
    print(f"  日志级别: {SYSTEM_CONFIG['log_level']}")
    print(f"  并发线程数: {SYSTEM_CONFIG['max_workers']}")
    print(f"  启用缓存: {'是' if SYSTEM_CONFIG['cache_enabled'] else '否'}")
    print(f"  缓存目录: {SYSTEM_CONFIG['cache_dir']}")

    print("\n【质量评估配置】")
    print(f"  近期论文年限: {QUALITY_CONFIG['recent_paper_years']}年")
    print(f"  高引用阈值: {QUALITY_CONFIG['high_citation_threshold']}")
    print(f"  摘要最小长度: {QUALITY_CONFIG['min_summary_length']}")

    print("\n【输出配置】")
    print(f"  输出目录: {OUTPUT_CONFIG['output_dir']}")
    print(f"  中文字体: {OUTPUT_CONFIG['font_name']}")
    print(f"  英文字体: {OUTPUT_CONFIG['english_font']}")
    print(f"  字体大小: {OUTPUT_CONFIG['font_size']}")

    print("\n【运行时配置】")
    print(f"  调试模式: {'启用' if RUNTIME_CONFIG['enable_debug'] else '禁用'}")
    print(f"  使用默认配置: {'是' if RUNTIME_CONFIG['use_default_config'] else '否'}")
    print(f"  详细输出: {'启用' if RUNTIME_CONFIG['verbose_output'] else '禁用'}")
    print(f"  保存中间文件: {'是' if RUNTIME_CONFIG['save_intermediate_files'] else '否'}")

    print("\n【用户输入配置】")
    print(f"  默认搜索关键词: {USER_INPUT_CONFIG['search_keyword']}")
    print(f"  启用参数配置询问: {'是' if USER_INPUT_CONFIG['enable_parameter_config'] else '否'}")
    print(f"  启用关键词输入询问: {'是' if USER_INPUT_CONFIG['enable_keyword_input'] else '否'}")
    print(f"  启用全文获取配置询问: {'是' if USER_INPUT_CONFIG['enable_fulltext_config'] else '否'}")
    print(f"  启用保存文件询问: {'是' if USER_INPUT_CONFIG['enable_save_config'] else '否'}")

    print("\n【路径配置】")
    print(f"  输出目录: {PATH_CONFIG['output_dir']}")
    print(f"  缓存目录: {PATH_CONFIG['cache_dir']}")
    print(f"  日志目录: {PATH_CONFIG['log_dir']}")
    print(f"  临时文件目录: {PATH_CONFIG['temp_dir']}")

    print("=" * 80)


def print_command_line_help():
    """
    打印命令行帮助信息
    """
    help_text = """
学术综述生成系统 - 命令行帮助

使用方法:
    python main.py

配置说明:
    本系统使用配置文件(config.py)管理所有参数，无需命令行参数。

主要配置参数:
    1. 大模型配置 (OPENAI_CONFIG)
       - base_url: API基础URL
       - api_key: API密钥
       - model: 使用的模型名称
       - temperature: 生成温度(0.0-1.0)
       - max_tokens: 最大token数
       - timeout: 请求超时时间(秒)

    2. 搜索配置 (SEARCH_CONFIG)
       - arxiv_count: Arxiv搜索数量
       - openalex_latest: OpenAlex最新论文数量
       - openalex_cited: OpenAlex高引用论文数量
       - semantic_latest: Semantic Scholar最新论文数量
       - semantic_cited: Semantic Scholar高引用论文数量
       - reference_paper_count: 参考文献数量（用于综述撰写）
       - citation_paper_count: 引用文献数量（用于文中详细引用）

    3. 全文获取配置 (FULLTEXT_CONFIG)
       - smart_fulltext_enabled: 是否默认启用智能全文获取
       - max_retries: 最大重试次数
       - retry_delay: 重试延迟(秒)
       - timeout: 请求超时时间(秒)

    4. 系统配置 (SYSTEM_CONFIG)
       - log_level: 日志级别
       - max_workers: 并发工作线程数
       - cache_enabled: 是否启用缓存
       - cache_dir: 缓存目录

    5. 质量评估配置 (QUALITY_CONFIG)
       - recent_paper_years: 近期论文年限(年)
       - high_citation_threshold: 高引用论文阈值
       - min_summary_length: 摘要最小长度

    6. 输出配置 (OUTPUT_CONFIG)
       - output_dir: 输出目录
       - font_name: 中文字体
       - english_font: 英文字体
       - font_size: 字体大小

    7. 运行时配置 (RUNTIME_CONFIG)
       - enable_debug: 是否启用调试模式
       - use_default_config: 是否使用默认配置
       - verbose_output: 是否显示详细输出
       - save_intermediate_files: 是否保存中间文件

    8. 用户输入配置 (USER_INPUT_CONFIG)
       - search_keyword: 默认搜索关键词
       - enable_parameter_config: 是否启用参数配置询问
       - enable_keyword_input: 是否启用关键词输入询问
       - enable_fulltext_config: 是否启用全文获取配置询问
       - enable_save_config: 是否启用保存文件询问

    9. 路径配置 (PATH_CONFIG)
       - output_dir: 输出目录
       - cache_dir: 缓存目录
       - log_dir: 日志目录
       - temp_dir: 临时文件目录

修改配置:
    编辑 config.py 文件修改各项配置参数。

验证配置:
    python config.py

获取帮助:
    在代码中调用 print_command_line_help()
    """
    print(help_text)


# =============================================================================
# 初始化验证
# =============================================================================

if __name__ == "__main__":
    # 验证配置
    is_valid, errors = validate_config()

    if is_valid:
        print("[OK] 配置文件验证通过")
        print_config_summary()
    else:
        print("[ERROR] 配置文件验证失败:")
        for error in errors:
            print(f"  - {error}")