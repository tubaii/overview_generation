"""
学术综述大纲生成模块

此模块负责：
1. 根据参考文献数据生成综述大纲
2. 为各级标题分配相应的引用文献
3. 输出结构化的综述框架
"""

from openai import OpenAI
from datetime import datetime
import re

# Token计数
from token_counter import record_api_call, count_tokens

# 初始化OpenAI客户端（从配置中读取）
from config import get_openai_config, get_quality_config
openai_config = get_openai_config()
quality_config = get_quality_config()
# 大纲生成涉及大量文本，增加超时时间
default_timeout = max(openai_config['timeout'], 120)
client = OpenAI(
    base_url=openai_config['base_url'],
    api_key=openai_config['api_key'],
    timeout=default_timeout
)


# def generate_review_outline(reference_papers, keyword, mode='fast', citation_papers=None, citation_index_mapping=None):
#     """
#     使用大模型生成综述大纲，为各级标题分配引用文献
#
#     Args:
#         reference_papers: 参考文献列表（用于生成大纲内容）
#         keyword: 搜索关键词
#         mode: 生成模式，'fast'（快速，约5000字）或 'deep'（深度，约12500字）
#         citation_papers: 引用文献列表（用于分配给标题，如果为None则使用reference_papers）
#         citation_index_mapping: 序号映射字典 {新序号: 原始参考文献序号}，如果为None则自动生成
#
#     Returns:
#         tuple: (大纲文本, 序号映射字典)
#             - 大纲文本（包含各级标题和对应文献分配）
#             - 序号映射字典
#     """
#     print(f"\n正在生成综述大纲...")
#
#     if not reference_papers:
#         return "未提供任何论文，无法生成大纲。", {}
#
#     # 如果没有提供引用文献，使用参考文献
#     if citation_papers is None:
#         citation_papers = reference_papers
#         citation_index_mapping = {i: i for i in range(1, len(reference_papers) + 1)}
#
#     # 如果没有提供序号映射，自动生成
#     if citation_index_mapping is None:
#         citation_index_mapping = {i: i for i in range(1, len(citation_papers) + 1)}
#
#     try:
#         # 构建参考文献信息摘要（用于内容生成）
#         reference_content = ""
#         for i, paper in enumerate(reference_papers, 1):
#             title = paper.get('title') or '未知标题'
#             authors = paper.get('authors') or []
#             published = paper.get('published') or '未知'
#             venue = paper.get('venue') or ''
#             source = paper.get('source') or 'unknown'
#             citation_count = paper.get('citation_count') or 0
#             summary = paper.get('summary') or '无摘要'
#
#             reference_content += f"\n[参考文献 {i}]\n"
#             reference_content += f"标题: {title}\n"
#             reference_content += f"作者: {', '.join(authors) if authors else '未知'}\n"
#             reference_content += f"发表时间: {published}\n"
#             if venue:
#                 reference_content += f"来源: {venue} ({source})\n"
#             reference_content += f"引用数: {citation_count}\n"
#             # 只包含摘要的前300字符，避免prompt过长
#             if summary and isinstance(summary, str):
#                 summary_short = summary[:300] + "..." if len(summary) > 300 else summary
#             else:
#                 summary_short = '无摘要'
#             reference_content += f"摘要: {summary_short}\n"
#
#             # 添加全文内容信息（如果有）
#             full_text = paper.get('full_text', {})
#             if isinstance(full_text, dict) and full_text.get('content_type') != 'metadata_only' and full_text.get('content'):
#                 reference_content += f"包含全文内容: 是\n"
#             elif paper.get('latex_content'):
#                 reference_content += f"包含全文内容: 是\n"
#             else:
#                 reference_content += f"包含全文内容: 否\n"
#
#             reference_content += "-" * 60 + "\n"
#
#         # 构建引用文献编号映射（用于分配）- 显示新序号和原始参考文献序号的映射
#         citation_mapping = ""
#         for new_idx, paper in enumerate(citation_papers, 1):
#             original_ref_idx = citation_index_mapping.get(new_idx, new_idx)
#             title = paper.get('title') or '未知标题'
#             title_short = title[:100] + "..." if len(title) > 100 else title
#             citation_mapping += f"[引用序号{new_idx}]: {title_short}\n"
#
#         # 统计参考文献和引用文献数量
#         total_references = len(reference_papers)
#         total_citations = len(citation_papers)
#
#         fulltext_count = sum(1 for p in reference_papers if (
#             (isinstance(p.get('full_text', {}), dict) and
#              p.get('full_text', {}).get('content_type') != 'metadata_only' and
#              p.get('full_text', {}).get('content')) or
#             p.get('latex_content')
#         ))
#         recent_count = sum(1 for p in reference_papers if _is_recent_paper(p, quality_config))
#         high_citation_count = sum(1 for p in reference_papers if _is_high_citation_paper(p, quality_config))
#
#         print(f"  参考文献统计: 总计{total_references}篇，包含全文{fulltext_count}篇，最近发表{recent_count}篇，高引用{high_citation_count}篇")
#         print(f"  引用文献统计: {total_citations}篇（用于文中详细引用）")
#
#         # 根据模式设置字数分配
#         if mode == 'fast':
#             word_counts = {
#                 '摘要': 200, '关键词': 50, '引言': 400,
#                 '技术章节': 700, '趋势': 300, '展望': 300,
#             }
#             total_target = 5000
#             # 构建提示词
#             system_prompt = f"""你是一位专业的学术综述撰写专家，擅长为学术综述设计结构合理的中文大纲框架。
#
#             重要约束：
#             1. 你只能使用【引用文献】来分配给各章节标题
#             2. 必须使用引用文献的新序号（1, 2, 3...）进行分配
#             3. 绝对不能使用【参考文献】的编号！
#
#             大纲设计要求：
#             1. 结构完整性：
#                - 大纲必须包含以下完整结构：标题、摘要、关键词、引言、技术总结部分、研究趋势、未来展望，只需撰写各部分题目，无需生成正文内容
#                - 标题：为综述拟定一个合适的总标题
#                - 摘要：列出标题即可，无需生成
#                - 关键词：列出标题即可，无需生成
#                - 引言：## 引言
#                - 技术总结部分至少包含3-4个二级标题，每个二级标题要有具体的技术名称和方法，不应该有"技术总结部分..."的字样，要一个真正的标题，拟出标题即可，无需生成内容，技术总结部分的二级标题应当符合技术的时间发展
#                - 研究趋势：## 当前研究趋势与热点
#                - 未来展望：## 未来发展方向与挑战
#
#             2. 标题要求：
#                - 全文总标题为一级标题，前面添加 #
#                - 摘要为二级标题，前面添加 ##
#                - 关键为二级标题，前面添加 ##
#                - 引言为二级标题，前面添加 ##
#                - 技术总结部分至少包含3-4个二级标题，每个二级标题要有具体的技术名称和方法，前面均添加 ##
#                - 每个二级标题下不允许再起标题
#                - 研究趋势为二级标题，前面添加 ##
#                - 未来展望为二级标题，前面添加 ##
#
#             3. 文献分配规则（非常重要）：
#                - 摘要和关键词无需分配论文，但是摘要需要分配字数
#                - 引言需要选择最具代表性的论文
#                - 技术总结部分是文献分配的重点，每个二级标题分配5-8篇相关论文，技术总结部分的二级标题所对应技术应当符合时间发展顺序
#                - 研究趋势和未来展望可以重复使用技术总结中的论文，但要控制在2-3篇以内
#                - 优先保证技术总结部分的文献分配充足，避免重复分配
#                - 只分配【引用文献】列表中的论文，使用新序号进行分配
#
#             3. 字数分配要求：
#                - 摘要{word_counts['摘要']}字，引言{word_counts['引言']}字，各技术章节{word_counts['技术章节']}字，趋势和展望各{word_counts['趋势']}字
#                - 每个标题后标注字数要求，如：[3,5,8](800字)
#                - 关键词不计算字数，只生成关键词列表
#
#             4. 文献分配原则：
#                - 根据论文的内容、质量和相关性分配到合适的标题下
#                - 关键词：无需分配论文
#                - 优先将高质量论文（高引用、近期发表、包含全文）分配给重要章节
#                - 每个标题下至少分配1-2篇相关论文
#                - 技术总结部分每个二级标题下分配3-10篇相关论文，技术总结部分的二级标题所对应技术应当符合时间发展顺序
#                - 引言分配具有代表性论文
#                - 研究趋势和未来展望从技术总结中选择代表性论文
#                - 论文编号：使用1,2,3,4...等引用文献新序号
#
#             5. 重要约束：
#                - 论文编号范围：1 到 {total_citations}
#                - 不允许分配超出此范围的编号
#                - 所有论文编号必须在1-{total_citations}范围内
#
#             6. 输出格式要求：
#                - 先输出完整的中文大纲结构（包含标题和关键词）
#                - 然后为每个标题标注对应的论文编号（用[编号]格式，如[1,2,3]）
#                - 重要：论文编号必须是引用文献的新序号（1-{total_citations}）
#             """
#             user_prompt = f"""请为关于"{keyword}"的学术综述设计完整的中文学术大纲结构，并为每个标题分配相关的引用文献。
#
#             生成模式：{mode}模式（目标总字数：{total_target}字）
#
#             【参考文献列表】（包含引用文献的所有参考文献，除引用文献之外不允许分配给各标题）：
#             {reference_content}
#
#             【引用文献列表】（用于分配给各标题的引用论文，必须使用引用序号1-{total_citations}进行分配）：
#             {citation_mapping}
#
#             请设计一个结构合理的中文大纲，确保：
#             1. 只使用【引用文献】中的论文编号进行分配
#             2. 必须使用新序号（1 到 {total_citations}）进行分配
#
#             2. 字数分配：严格按照摘要：{word_counts['摘要']}，引言：{word_counts['引言']}，技术章节：{word_counts['技术章节']}，当前研究趋势与热点：{word_counts['趋势']}，未来发展方向与挑战：{word_counts['展望']}字分配
#             3. 输出格式要求：
#                - 标题使用Markdown格式
#                - 关键词写出题目即可，无需生成内容
#                - 其他部分使用：具体标题名称 + [论文编号](字数)
#                - 格式示例：
#                  # 综述标题
#
#                  ## 摘要(350字)
#
#                  ## 关键词
#
#                  ## 引言 [1,2](350字)
#
#                  ## 技术部分1 [3,4，5](350字)
#                  ...
#             重要提醒：只能使用引用文献列表中的论文！必须使用新序号（1 到 {total_citations}）！不允许使用参考文献的原始序号！
#             请输出完整的大纲结构："""
#         else:  # deep mode
#             word_counts = {
#                 '摘要': 300, '关键词': 50, '引言': 600,
#                 '技术章节': 1400, '趋势': 500, '展望': 500,
#             }
#             total_target = 12500
#             # 构建提示词
#             system_prompt = f"""你是一位专业的学术综述撰写专家，擅长为学术综述设计结构合理的中文大纲框架。
#
#             重要约束：
#             1. 你只能使用【引用文献】来分配给各章节标题
#             2. 必须使用引用文献的新序号（1, 2, 3...）进行分配
#             3. 绝对不能使用【参考文献】的编号！
#
#             大纲设计要求：
#             1. 结构完整性：
#                - 大纲必须包含以下完整结构：标题、摘要、关键词、引言、技术总结部分、研究趋势、未来展望，只需撰写各部分题目，无需生成正文内容
#                - 标题：为综述拟定一个合适的总标题
#                - 摘要：列出标题即可，无需生成
#                - 关键词：列出标题即可，无需生成
#                - 引言：## 引言
#                - 技术总结部分至少包含3-4个二级标题，每个二级标题要有具体的技术名称和方法，不应该有"技术总结部分..."的字样，要一个真正的标题，拟出标题即可，无需生成内容，技术总结部分的二级标题应当符合技术的时间发展，二级标题下需要根据内容生成两到三个所属的三级标题
#                - 研究趋势：## 当前研究趋势与热点
#                - 未来展望：## 未来发展方向与挑战
#
#             2. 标题要求：
#                - 全文总标题为一级标题，前面添加 #
#                - 摘要为二级标题，前面添加 ##
#                - 关键为二级标题，前面添加 ##
#                - 引言为二级标题，前面添加 ##
#                - 技术总结部分至少包含3-4个二级标题，每个二级标题要有具体的技术名称和方法，前面均添加 ##
#                - 技术总结部分的每个二级标题下只允许起2-3个三级标题，每个三级标题要有具体的技术名称和方法，前面均添加 ###
#                - 研究趋势为二级标题，前面添加 ##
#                - 未来展望为二级标题，前面添加 ##
#
#             3. 文献分配规则（非常重要）：
#                - 摘要和关键词无需分配论文，但是摘要需要分配字数
#                - 引言需要选择最具代表性的论文
#                - 技术总结部分是文献分配的重点，每个二级标题分配3-10篇相关论文，技术总结部分的二级标题所对应技术应当符合时间发展顺序
#                - 技术总结部分的二级标题所分配的文献应当全部分配给其下的三级标题，三级标题不应当有上一个二级标题没有的论文，三级标题不应当有其他二级标题的论文，仅仅只能有其所属的二级标题的论文
#                - 研究趋势和未来展望可以重复使用技术总结中的论文，但要控制在2-3篇以内
#                - 优先保证技术总结部分的文献分配充足，避免重复分配
#                - 只分配【引用文献】列表中的论文，使用新序号进行分配
#
#             3. 字数分配要求：
#                - 摘要{word_counts['摘要']}字，引言{word_counts['引言']}字，各技术章节{word_counts['技术章节']}字，趋势和展望各{word_counts['趋势']}字
#                - 每个标题后标注字数要求，如：[3,5,8](800字)
#                - 关键词不计算字数，只生成关键词列表
#                - 将技术章节的字数分别分配给其下的三级标题，但是在二级标题下应分配200到300字对此部分技术进行总述引出
#
#             4. 文献分配原则：
#                - 根据论文的内容、质量和相关性分配到合适的标题下
#                - 关键词：无需分配论文
#                - 优先将高质量论文（高引用、近期发表、包含全文）分配给重要章节
#                - 技术总结部分每个二级标题下分配3-10篇相关论文,然后将二级标题的论文分配给其下的各个三级标题，技术总结部分的二级标题所对应技术应当符合时间发展顺序
#                - 引言分配具有代表性论文
#                - 研究趋势和未来展望从技术总结中选择代表性论文
#                - 论文编号：使用1,2,3,4...等引用文献新序号
#
#             5. 重要约束：
#                - 论文编号范围：1 到 {total_citations}
#                - 不允许分配超出此范围的编号
#                - 所有论文编号必须在1-{total_citations}范围内
#
#             6. 输出格式要求：
#                - 先输出完整的中文大纲结构（包含标题和关键词）
#                - 然后为每个标题标注对应的论文编号（用[编号]格式，如[1,2,3]）
#                - 重要：论文编号必须是引用文献的新序号（1-{total_citations}）
#             """
#             user_prompt = f"""请为关于"{keyword}"的学术综述设计完整的中文学术大纲结构，并为每个标题分配相关的引用文献。
#
#             生成模式：{mode}模式（目标总字数：{total_target}字）
#
#             【参考文献列表】（包含引用文献的所有参考文献，除引用文献之外不允许分配给各标题）：
#             {reference_content}
#
#             【引用文献列表】（用于分配给各标题的引用论文，必须使用引用序号进行分配）：
#             {citation_mapping}
#
#             请设计一个结构合理的中文大纲，确保：
#             1. 只使用【引用文献】中的论文编号进行分配
#             2. 必须使用新序号（1 到 {total_citations}）进行分配
#             3.每个二级标题下只能起2-3个三级标题！
#             4. 字数分配：严格按照{word_counts['摘要']}/{word_counts['引言']}/{word_counts['技术章节']}/{word_counts['趋势']}/{word_counts['展望']}字分配,每个技术章节的二级和三级标题字数加起来应该为{word_counts['技术章节']}，二级标题下应该分配200-300字即可，其他字数应当分配在三级标题下
#             5. 将技术章节的字数分别分配给其下的多个三级标题，但是在二级标题下应分配200到300字对此部分技术进行总述引出
#             6. 重要！！将每个技术章节的二级标题所分配的文献应当全部分配给所属的三级标题，三级标题不应当有上级二级标题没有的论文和其他二级标题的论文，仅仅只能分配得到其所属的二级标题的论文
#             7. 输出格式要求：
#                - 标题使用Markdown格式
#                - 关键词写出题目即可，无需生成内容
#                - 其他部分使用：具体标题名称 + [论文编号](字数)
#                - 格式示例：
#                  # 综述标题
#
#                  ## 摘要(350字)
#
#                  ## 关键词
#
#                  ## 引言 [1,2](350字)
#
#                  ## 技术部分1 [3,4，5](200字)
#                  ### 三级标题1 [3,4](300字)
#                  ...
#             重要提醒：只能使用引用文献列表中的论文！必须使用新序号（1 到 {total_citations}）！不允许使用参考文献的原始序号！每个二级标题下只能起2-3个三级标题！！不允许每个分配的论文都起一个三级标题！
#             再次重申！重要提醒：将每个技术章节的二级标题所分配的论文分别分配且仅分配给所属的多个三级标题，三级标题不应当分配上一级二级标题没有分配的论文和其他二级标题的论文，仅仅只能分配的到其所属的二级标题的论文，而不应该有其他二级标题的论文！
#             请输出完整的大纲结构："""
#
#         response = client.chat.completions.create(
#             model=openai_config['model'],
#             messages=[
#                 {
#                     'role': 'system',
#                     'content': system_prompt
#                 },
#                 {
#                     'role': 'user',
#                     'content': user_prompt
#                 }
#             ],
#             stream=False,
#             temperature=0.1,  # 大纲生成使用低温度，保持稳定性
#             max_tokens=openai_config.get('max_tokens', 8000),
#             timeout=default_timeout
#         )
#
#         # 计算并记录Token使用
#         input_tokens = count_tokens(system_prompt) + count_tokens(user_prompt)
#         if response and response.choices:
#             output_text = response.choices[0].message.content or ""
#             output_tokens = count_tokens(output_text)
#         else:
#             output_tokens = 0
#         record_api_call(input_tokens, output_tokens, "outline", f"生成大纲 ({mode}模式)")
#
#         if response and response.choices and len(response.choices) > 0:
#             outline = response.choices[0].message.content.strip()
#
#             if outline:
#                 # 验证并过滤论文编号
#                 outline = _validate_and_filter_citations(outline, total_citations)
#
#                 # 检查所有引用文献是否都被分配
#                 is_assigned, unallocated = _check_all_citations_assigned(outline, total_citations)
#
#                 if not is_assigned:
#                     print(f"  ⚠️ 警告：有 {len(unallocated)} 篇引用文献未被分配到章节")
#                     print(f"     未分配的序号: {unallocated}")
#
#                     # 尝试重新生成大纲，确保所有引用文献都被分配
#                     print(f"  🔄 重新生成大纲以确保所有引用文献都被分配...")
#
#                     # 更新提示词，强调必须分配所有引用文献
#                     retry_prompt = f"""
#
# 重要补充要求（必须严格遵守）：
# 在前面的基础上，必须确保【所有{total_citations}篇引用文献】都被分配到各个章节！
#
# 当前已分配的文献：已分配
# 当前未分配的文献：{unallocated}
#
# 请重新设计大纲，确保：
# 1. 所有{total_citations}篇引用文献必须全部被分配
# 2. 未分配的文献[{', '.join(map(str, unallocated))}] 必须分配到合适的章节
# 3. 每个章节至少分配1篇论文
# 4. 保持原有的大纲结构和字数要求
#
# 请输出修正后的大纲："""
#
#                     # 调用大模型重新生成
#                     retry_response = client.chat.completions.create(
#                         model=openai_config['model'],
#                         messages=[
#                             {'role': 'system', 'content': system_prompt},
#                             {'role': 'user', 'content': user_prompt + retry_prompt}
#                         ],
#                         stream=False,
#                         temperature=0.3,
#                         timeout=default_timeout
#                     )
#
#                     if retry_response and retry_response.choices and len(retry_response.choices) > 0:
#                         new_outline = retry_response.choices[0].message.content.strip()
#                         if new_outline:
#                             outline = new_outline
#                             # 再次验证
#                             outline = _validate_and_filter_citations(outline, total_citations)
#                             is_assigned, unallocated = _check_all_citations_assigned(outline, total_citations)
#
#                 print(f"  ✓ 大纲生成完成 (输入:{input_tokens} tokens, 输出:{output_tokens} tokens)")
#                 if is_assigned:
#                     print(f"  ✓ 所有 {total_citations} 篇引用文献均已分配到章节")
#                 else:
#                     print(f"  ⚠️ 仍有 {len(unallocated)} 篇引用文献未分配: {unallocated}")
#                 return outline, citation_index_mapping
#             else:
#                 return "大纲生成失败：返回内容为空。", citation_index_mapping
#         else:
#             return "大纲生成失败：API返回格式异常。", citation_index_mapping
#
#     except Exception as e:
#         error_msg = f"生成大纲时出错: {e}"
#         print(error_msg)
#         return error_msg, citation_index_mapping if 'citation_index_mapping' in dir() else {}
def generate_review_outline(reference_papers, keyword, mode='fast', citation_papers=None, citation_index_mapping=None):
    """
    使用大模型生成综述大纲，为各级标题分配引用文献

    Args:
        reference_papers: 参考文献列表（用于生成大纲内容）
        keyword: 搜索关键词
        mode: 生成模式，'fast'（快速，约5000字）或 'deep'（深度，约12500字）
        citation_papers: 引用文献列表（用于分配给标题，如果为None则使用reference_papers）
        citation_index_mapping: 序号映射字典 {新序号: 原始参考文献序号}，如果为None则自动生成

    Returns:
        tuple: (大纲文本, 序号映射字典)
            - 大纲文本（包含各级标题和对应文献分配）
            - 序号映射字典
    """
    print(f"\n正在生成综述大纲...")

    if not reference_papers:
        return "未提供任何论文，无法生成大纲。", {}

    # 如果没有提供引用文献，使用参考文献
    if citation_papers is None:
        citation_papers = reference_papers
        citation_index_mapping = {i: i for i in range(1, len(reference_papers) + 1)}

    # 如果没有提供序号映射，自动生成
    if citation_index_mapping is None:
        citation_index_mapping = {i: i for i in range(1, len(citation_papers) + 1)}

    try:
        # 构建参考文献信息摘要（用于内容生成）
        reference_content = ""
        for i, paper in enumerate(reference_papers, 1):
            title = paper.get('title') or '未知标题'
            authors = paper.get('authors') or []
            published = paper.get('published') or '未知'
            venue = paper.get('venue') or ''
            source = paper.get('source') or 'unknown'
            citation_count = paper.get('citation_count') or 0
            summary = paper.get('summary') or '无摘要'

            reference_content += f"\n[参考文献 {i}]\n"
            reference_content += f"标题: {title}\n"
            reference_content += f"作者: {', '.join(authors) if authors else '未知'}\n"
            reference_content += f"发表时间: {published}\n"
            if venue:
                reference_content += f"来源: {venue} ({source})\n"
            reference_content += f"引用数: {citation_count}\n"
            # 只包含摘要的前300字符，避免prompt过长
            if summary and isinstance(summary, str):
                summary_short = summary[:300] + "..." if len(summary) > 300 else summary
            else:
                summary_short = '无摘要'
            reference_content += f"摘要: {summary_short}\n"

            # 添加全文内容信息（如果有）
            full_text = paper.get('full_text', {})
            if isinstance(full_text, dict) and full_text.get('content_type') != 'metadata_only' and full_text.get('content'):
                reference_content += f"包含全文内容: 是\n"
            elif paper.get('latex_content'):
                reference_content += f"包含全文内容: 是\n"
            else:
                reference_content += f"包含全文内容: 否\n"

            reference_content += "-" * 60 + "\n"

        # 构建引用文献编号映射（用于分配）- 显示新序号和原始参考文献序号的映射
        citation_mapping = ""
        for new_idx, paper in enumerate(citation_papers, 1):
            original_ref_idx = citation_index_mapping.get(new_idx, new_idx)
            title = paper.get('title') or '未知标题'
            title_short = title[:100] + "..." if len(title) > 100 else title
            citation_mapping += f"[引用序号{new_idx}]: {title_short}\n"

        # 统计参考文献和引用文献数量
        total_references = len(reference_papers)
        total_citations = len(citation_papers)

        fulltext_count = sum(1 for p in reference_papers if (
            (isinstance(p.get('full_text', {}), dict) and
             p.get('full_text', {}).get('content_type') != 'metadata_only' and
             p.get('full_text', {}).get('content')) or
            p.get('latex_content')
        ))
        recent_count = sum(1 for p in reference_papers if _is_recent_paper(p, quality_config))
        high_citation_count = sum(1 for p in reference_papers if _is_high_citation_paper(p, quality_config))

        print(f"  参考文献统计: 总计{total_references}篇，包含全文{fulltext_count}篇，最近发表{recent_count}篇，高引用{high_citation_count}篇")
        print(f"  引用文献统计: {total_citations}篇（用于文中详细引用）")

        # 根据模式设置字数分配
        if mode == 'fast':
            # 快速模式原有逻辑保持不变
            word_counts = {
                '摘要': 200, '关键词': 50, '引言': 400,
                '技术章节': 700, '趋势': 300, '展望': 300,
            }
            total_target = 5000
            # 构建提示词
            system_prompt = f"""你是一位专业的学术综述撰写专家，擅长为学术综述设计结构合理的中文大纲框架。

            重要约束：
            1. 你只能使用【引用文献】来分配给各章节标题
            2. 必须使用引用文献的新序号（1, 2, 3...）进行分配
            3. 绝对不能使用【参考文献】的编号！

            大纲设计要求：
            1. 结构完整性：
               - 大纲必须包含以下完整结构：标题、摘要、关键词、引言、技术总结部分、研究趋势、未来展望，只需撰写各部分题目，无需生成正文内容
               - 标题：为综述拟定一个合适的总标题
               - 摘要：列出标题即可，无需生成
               - 关键词：列出标题即可，无需生成
               - 引言：## 引言
               - 技术总结部分至少包含3-4个二级标题，每个二级标题要有具体的技术名称和方法，不应该有"技术总结部分..."的字样，要一个真正的标题，拟出标题即可，无需生成内容，技术总结部分的二级标题应当符合技术的时间发展
               - 研究趋势：## 当前研究趋势与热点
               - 未来展望：## 未来发展方向与挑战

            2. 标题要求：
               - 全文总标题为一级标题，前面添加 #
               - 摘要为二级标题，前面添加 ##
               - 关键为二级标题，前面添加 ##
               - 引言为二级标题，前面添加 ##
               - 技术总结部分至少包含3-4个二级标题，每个二级标题要有具体的技术名称和方法，前面均添加 ##
               - 每个二级标题下不允许再起标题
               - 研究趋势为二级标题，前面添加 ##
               - 未来展望为二级标题，前面添加 ##

            3. 文献分配规则（非常重要）：
               - 摘要和关键词无需分配论文，但是摘要需要分配字数
               - 引言需要选择最具代表性的论文
               - 技术总结部分是文献分配的重点，每个二级标题分配5-8篇相关论文，技术总结部分的二级标题所对应技术应当符合时间发展顺序
               - 研究趋势和未来展望可以重复使用技术总结中的论文，但要控制在2-3篇以内
               - 优先保证技术总结部分的文献分配充足，避免重复分配
               - 只分配【引用文献】列表中的论文，使用新序号进行分配

            3. 字数分配要求：
               - 摘要{word_counts['摘要']}字，引言{word_counts['引言']}字，各技术章节{word_counts['技术章节']}字，趋势和展望各{word_counts['趋势']}字
               - 每个标题后标注字数要求，如：[3,5,8](800字)
               - 关键词不计算字数，只生成关键词列表

            4. 文献分配原则：
               - 根据论文的内容、质量和相关性分配到合适的标题下
               - 关键词：无需分配论文
               - 优先将高质量论文（高引用、近期发表、包含全文）分配给重要章节
               - 每个标题下至少分配1-2篇相关论文
               - 技术总结部分每个二级标题下分配3-10篇相关论文，技术总结部分的二级标题所对应技术应当符合时间发展顺序
               - 引言分配具有代表性论文
               - 研究趋势和未来展望从技术总结中选择代表性论文
               - 论文编号：使用1,2,3,4...等引用文献新序号

            5. 重要约束：
               - 论文编号范围：1 到 {total_citations}
               - 不允许分配超出此范围的编号
               - 所有论文编号必须在1-{total_citations}范围内

            6. 输出格式要求：
               - 先输出完整的中文大纲结构（包含标题和关键词）
               - 然后为每个标题标注对应的论文编号（用[编号]格式，如[1,2,3]）
               - 重要：论文编号必须是引用文献的新序号（1-{total_citations}）
            """
            user_prompt = f"""请为关于"{keyword}"的学术综述设计完整的中文学术大纲结构，并为每个标题分配相关的引用文献。

            生成模式：{mode}模式（目标总字数：{total_target}字）

            【参考文献列表】（包含引用文献的所有参考文献，除引用文献之外不允许分配给各标题）：
            {reference_content}

            【引用文献列表】（用于分配给各标题的引用论文，必须使用引用序号1-{total_citations}进行分配）：
            {citation_mapping}

            请设计一个结构合理的中文大纲，确保：
            1. 只使用【引用文献】中的论文编号进行分配
            2. 必须使用新序号（1 到 {total_citations}）进行分配

            2. 字数分配：严格按照摘要：{word_counts['摘要']}，引言：{word_counts['引言']}，技术章节：{word_counts['技术章节']}，当前研究趋势与热点：{word_counts['趋势']}，未来发展方向与挑战：{word_counts['展望']}字分配
            3. 输出格式要求：
               - 标题使用Markdown格式
               - 关键词写出题目即可，无需生成内容
               - 其他部分使用：具体标题名称 + [论文编号](字数)
               - 格式示例：
                 # 综述标题

                 ## 摘要(350字)

                 ## 关键词

                 ## 引言 [1,2](350字)

                 ## 技术部分1 [3,4，5](350字)
                 ...
            重要提醒：只能使用引用文献列表中的论文！必须使用新序号（1 到 {total_citations}）！不允许使用参考文献的原始序号！
            请输出完整的大纲结构："""
            response = client.chat.completions.create(
                model=openai_config['model'],
                messages=[
                    {
                        'role': 'system',
                        'content': system_prompt
                    },
                    {
                        'role': 'user',
                        'content': user_prompt
                    }
                ],
                stream=False,
                temperature=0.1,  # 大纲生成使用低温度，保持稳定性
                max_tokens=openai_config.get('max_tokens', 8000),
                timeout=default_timeout
            )

            # 计算并记录Token使用
            input_tokens = count_tokens(system_prompt) + count_tokens(user_prompt)
            if response and response.choices:
                output_text = response.choices[0].message.content or ""
                output_tokens = count_tokens(output_text)
            else:
                output_tokens = 0
            record_api_call(input_tokens, output_tokens, "outline", f"生成大纲 ({mode}模式)")

            if response and response.choices and len(response.choices) > 0:
                outline = response.choices[0].message.content.strip()

                if outline:
                    # 验证并过滤论文编号
                    outline = _validate_and_filter_citations(outline, total_citations)

                    # 检查所有引用文献是否都被分配
                    is_assigned, unallocated = _check_all_citations_assigned(outline, total_citations)

                    if not is_assigned:
                        print(f"  ⚠️ 警告：有 {len(unallocated)} 篇引用文献未被分配到章节")
                        print(f"     未分配的序号: {unallocated}")

                        # 尝试重新生成大纲，确保所有引用文献都被分配
                        print(f"  🔄 重新生成大纲以确保所有引用文献都被分配...")

                        # 更新提示词，强调必须分配所有引用文献
                        retry_prompt = f"""

            重要补充要求（必须严格遵守）：
            在前面的基础上，必须确保【所有{total_citations}篇引用文献】都被分配到各个章节！

            当前已分配的文献：已分配
            当前未分配的文献：{unallocated}

            请重新设计大纲，确保：
            1. 所有{total_citations}篇引用文献必须全部被分配
            2. 未分配的文献[{', '.join(map(str, unallocated))}] 必须分配到合适的章节
            3. 每个章节至少分配1篇论文
            4. 保持原有的大纲结构和字数要求

            请输出修正后的大纲："""

                        # 调用大模型重新生成
                        retry_response = client.chat.completions.create(
                            model=openai_config['model'],
                            messages=[
                                {'role': 'system', 'content': system_prompt},
                                {'role': 'user', 'content': user_prompt + retry_prompt}
                            ],
                            stream=False,
                            temperature=0.3,
                            timeout=default_timeout
                        )

                        if retry_response and retry_response.choices and len(retry_response.choices) > 0:
                            new_outline = retry_response.choices[0].message.content.strip()
                            if new_outline:
                                outline = new_outline
                                # 再次验证
                                outline = _validate_and_filter_citations(outline, total_citations)
                                is_assigned, unallocated = _check_all_citations_assigned(outline, total_citations)

                    print(f"  ✓ 大纲生成完成 (输入:{input_tokens} tokens, 输出:{output_tokens} tokens)")
                    if is_assigned:
                        print(f"  ✓ 所有 {total_citations} 篇引用文献均已分配到章节")
                    else:
                        print(f"  ⚠️ 仍有 {len(unallocated)} 篇引用文献未分配: {unallocated}")
                    return outline, citation_index_mapping
                else:
                    return "大纲生成失败：返回内容为空。", citation_index_mapping
            else:
                return "大纲生成失败：API返回格式异常。", citation_index_mapping

        else:  # deep mode - 分步生成
            word_counts = {
                '摘要': 300, '关键词': 50, '引言': 600,
                '技术章节': 1400,  # 每个技术二级标题的字数
                '趋势': 500, '展望': 500,
            }
            total_target = 12500

            # ==================== 第一步：生成二级标题结构 ====================
            print("  步骤1：生成综述二级标题结构...")

            # 构建系统提示
            system_prompt_step1 = f"""你是一位专业的学术综述撰写专家，擅长为学术综述设计结构合理的中文大纲框架。

            重要约束：
            1. 你只能使用【引用文献】来分配给各章节标题
            2. 必须使用引用文献的新序号（1, 2, 3...）进行分配
            3. 绝对不能使用【参考文献】的编号！

            大纲设计要求：
            1. 结构完整性：
               - 大纲必须包含以下完整结构：标题、摘要、关键词、引言、技术总结部分、研究趋势、未来展望，只需撰写各部分题目，无需生成正文内容
               - 标题：为综述拟定一个合适的总标题
               - 摘要：列出标题即可，无需生成
               - 关键词：列出标题即可，无需生成
               - 引言：## 引言
               - 技术总结部分至少包含3-4个二级标题，每个二级标题要有具体的技术名称和方法，不应该有"技术总结部分..."的字样，要一个真正的标题，拟出标题即可，无需生成内容，技术总结部分的二级标题应当符合技术的时间发展
               - 研究趋势：## 当前研究趋势与热点
               - 未来展望：## 未来发展方向与挑战

            2. 标题要求：
               - 全文总标题为一级标题，前面添加 #
               - 摘要为二级标题，前面添加 ##
               - 关键为二级标题，前面添加 ##
               - 引言为二级标题，前面添加 ##
               - 技术总结部分至少包含3-4个二级标题，每个二级标题要有具体的技术名称和方法，前面均添加 ##
               - 每个二级标题下不允许再起标题
               - 研究趋势为二级标题，前面添加 ##
               - 未来展望为二级标题，前面添加 ##

            3. 文献分配规则（非常重要）：
               - 摘要和关键词无需分配论文，但是摘要需要分配字数
               - 引言需要选择最具代表性的论文
               - 技术总结部分是文献分配的重点，每个二级标题分配5-8篇相关论文，技术总结部分的二级标题所对应技术应当符合时间发展顺序
               - 研究趋势和未来展望可以重复使用技术总结中的论文，但要控制在2-3篇以内
               - 优先保证技术总结部分的文献分配充足，避免重复分配
               - 只分配【引用文献】列表中的论文，使用新序号进行分配

            3. 字数分配要求：
               - 摘要{word_counts['摘要']}字，引言{word_counts['引言']}字，各技术章节{word_counts['技术章节']}字，趋势和展望各{word_counts['趋势']}字
               - 每个标题后标注字数要求，如：[3,5,8](800字)
               - 关键词不计算字数，只生成关键词列表

            4. 文献分配原则：
               - 根据论文的内容、质量和相关性分配到合适的标题下
               - 关键词：无需分配论文
               - 优先将高质量论文（高引用、近期发表、包含全文）分配给重要章节
               - 每个标题下至少分配1-2篇相关论文
               - 技术总结部分每个二级标题下分配3-10篇相关论文，技术总结部分的二级标题所对应技术应当符合时间发展顺序
               - 引言分配具有代表性论文
               - 研究趋势和未来展望从技术总结中选择代表性论文
               - 论文编号：使用1,2,3,4...等引用文献新序号

            5. 重要约束：
               - 论文编号范围：1 到 {total_citations}
               - 不允许分配超出此范围的编号
               - 所有论文编号必须在1-{total_citations}范围内

            6. 输出格式要求：
               - 先输出完整的中文大纲结构（包含标题和关键词）
               - 然后为每个标题标注对应的论文编号（用[编号]格式，如[1,2,3]）
               - 重要：论文编号必须是引用文献的新序号（1-{total_citations}）
            """
            user_prompt_step1 = f"""请为关于"{keyword}"的学术综述设计完整的中文学术大纲结构，并为每个标题分配相关的引用文献。

            生成模式：{mode}模式（目标总字数：{total_target}字）

            【参考文献列表】（包含引用文献的所有参考文献，除引用文献之外不允许分配给各标题）：
            {reference_content}

            【引用文献列表】（用于分配给各标题的引用论文，必须使用引用序号1-{total_citations}进行分配）：
            {citation_mapping}

            请设计一个结构合理的中文大纲，确保：
            1. 只使用【引用文献】中的论文编号进行分配
            2. 必须使用新序号（1 到 {total_citations}）进行分配

            2. 字数分配：严格按照摘要：{word_counts['摘要']}，引言：{word_counts['引言']}，技术章节：{word_counts['技术章节']}，当前研究趋势与热点：{word_counts['趋势']}，未来发展方向与挑战：{word_counts['展望']}字分配
            3. 输出格式要求：
               - 标题使用Markdown格式
               - 关键词写出题目即可，无需生成内容
               - 其他部分使用：具体标题名称 + [论文编号](字数)
               - 格式示例：
                 # 综述标题

                 ## 摘要(350字)

                 ## 关键词

                 ## 引言 [1,2](350字)

                 ## 技术部分1 [3,4，5](350字)
                 ...
            重要提醒：只能使用引用文献列表中的论文！必须使用新序号（1 到 {total_citations}）！不允许使用参考文献的原始序号！
            请输出完整的大纲结构：除此之外，不允许输出其他任何内容"""
            # 调用大模型
            response_step1 = client.chat.completions.create(
                model=openai_config['model'],
                messages=[
                    {'role': 'system', 'content': system_prompt_step1},
                    {'role': 'user', 'content': user_prompt_step1}
                ],
                stream=False,
                temperature=0.1,
                max_tokens=openai_config.get('max_tokens', 4000),
                timeout=default_timeout
            )

            if not response_step1 or not response_step1.choices:
                return "大纲生成失败：第一步API返回异常。", citation_index_mapping

            outline_step1 = response_step1.choices[0].message.content.strip()
            print('outline_step1')
            print(outline_step1)
            # 记录Token使用
            input_tokens_step1 = count_tokens(system_prompt_step1) + count_tokens(user_prompt_step1)
            output_tokens_step1 = count_tokens(outline_step1)
            record_api_call(input_tokens_step1, output_tokens_step1, "outline_step1", "生成二级标题结构")

            # ==================== 解析第一步输出 ====================
            import re

            # 提取总标题（第一个一级标题）
            main_title_match = re.search(r'^#\s+(.+?)(?:\n|$)', outline_step1, re.MULTILINE)
            main_title = main_title_match.group(1).strip() if main_title_match else f"{keyword}研究综述"

            # 提取摘要字数
            abstract_match = re.search(r'##\s*摘要\((\d+)字\)', outline_step1)
            abstract_words = int(abstract_match.group(1)) if abstract_match else word_counts['摘要']

            # 提取关键词（直接保留）
            keywords_section = "## 关键词"  # 关键词没有字数，直接使用

            # 提取引言
            intro_match = re.search(r'##\s*引言\s*\[([\d,，\s]+)\]\((\d+)字\)', outline_step1)
            if intro_match:
                intro_papers_str = intro_match.group(1).replace('，', ',').replace(' ', '')
                intro_papers = [int(x) for x in intro_papers_str.split(',') if x.strip().isdigit()]
                intro_words = int(intro_match.group(2))
            else:
                intro_papers = []
                intro_words = word_counts['引言']

            # 提取所有技术二级标题（格式：## 标题 [文献](1400字)）
            tech_heading_pattern = r'##\s+(.+?)\s*\[([\d,，\s]+)\]\((\d+)字\)'
            tech_headings = []
            for match in re.finditer(tech_heading_pattern, outline_step1):
                title = match.group(1).strip()
                # 排除已知的固定标题（引言、研究趋势、未来展望）
                if title in ['引言', '当前研究趋势与热点', '未来发展方向与挑战']:
                    continue
                papers_str = match.group(2).replace('，', ',').replace(' ', '')
                papers = [int(x) for x in papers_str.split(',') if x.strip().isdigit()]
                words = int(match.group(3))
                tech_headings.append({
                    'title': title,
                    'papers': papers,
                    'words': words
                })
            # print('tech_headings')
            # print(tech_headings)
            # 提取研究趋势
            trend_match = re.search(r'##\s*当前研究趋势与热点\s*\[([\d,，\s]+)\]\((\d+)字\)', outline_step1)
            if trend_match:
                trend_papers_str = trend_match.group(1).replace('，', ',').replace(' ', '')
                trend_papers = [int(x) for x in trend_papers_str.split(',') if x.strip().isdigit()]
                trend_words = int(trend_match.group(2))
            else:
                trend_papers = []
                trend_words = word_counts['趋势']

            # 提取未来展望
            future_match = re.search(r'##\s*未来发展方向与挑战\s*\[([\d,，\s]+)\]\((\d+)字\)', outline_step1)
            if future_match:
                future_papers_str = future_match.group(1).replace('，', ',').replace(' ', '')
                future_papers = [int(x) for x in future_papers_str.split(',') if x.strip().isdigit()]
                future_words = int(future_match.group(2))
            else:
                future_papers = []
                future_words = word_counts['展望']

            # 检查技术二级标题数量
            if len(tech_headings) < 3:
                print(f"  ⚠️ 警告：生成的技术二级标题不足3个，将补充处理")
                # 可以尝试简单重试或使用默认标题，这里简化处理：如果太少则用默认标题
                while len(tech_headings) < 3:
                    tech_headings.append({
                        'title': f"技术部分{len(tech_headings)+1}",
                        'papers': [],
                        'words': word_counts['技术章节']
                    })

            # 检查文献分配完整性：所有引用文献必须至少出现在一个技术二级标题中
            all_assigned_papers = set()
            for th in tech_headings:
                all_assigned_papers.update(th['papers'])
            missing_papers = set(range(1, total_citations+1)) - all_assigned_papers
            if missing_papers:
                print(f"  ⚠️ 警告：有 {len(missing_papers)} 篇引用文献未被分配到技术章节: {sorted(missing_papers)}")
                # 可以尝试重新生成，但为简化，我们将未分配的文献随机添加到第一个技术标题中
                if missing_papers:
                    tech_headings[0]['papers'].extend(sorted(missing_papers))
                    print(f"     已将未分配文献添加到第一个技术标题中")

            # ==================== 第二步：为每个技术二级标题生成三级标题 ====================
            print("  步骤2：为各技术部分生成三级标题...")

            # 二级标题总述字数固定（可根据需要调整）
            SUMMARY_WORDS_PER_TECH = 250

            for idx, tech in enumerate(tech_headings):
                print(f"    处理技术部分 {idx+1}: {tech['title']}")

                # 获取该技术部分的文献列表
                paper_ids = tech['papers']
                if not paper_ids:
                    print(f"      该技术部分没有分配文献，跳过三级标题生成")
                    tech['subheadings'] = []
                    continue

                # 从citation_papers中提取这些文献的详细信息
                tech_papers_info = ""
                for pid in paper_ids:
                    # 序号从1开始，对应列表索引 pid-1
                    paper = citation_papers[pid-1] if 0 < pid <= len(citation_papers) else None
                    if paper:
                        title = paper.get('title', '未知标题')
                        summary = paper.get('summary', '无摘要')
                        summary_short = summary[:200] + "..." if len(summary) > 200 else summary
                        tech_papers_info += f"[{pid}] 标题: {title}\n摘要: {summary_short}\n\n"
                    else:
                        tech_papers_info += f"[{pid}] 文献信息缺失\n\n"

                # 计算三级标题总字数
                sub_total_words = tech['words'] - SUMMARY_WORDS_PER_TECH
                if sub_total_words < 100:
                    sub_total_words = 100  # 最少分配100字给三级标题

                # 构建三级标题生成提示
                sub_system_prompt = f"""你是一位专业的学术综述撰写专家，负责为技术部分的二级标题生成下属的三级标题，并合理分配文献和字数。

要求：
1. 为该技术部分生成2-3个三级标题（###）。
2. 三级标题必须从提供的文献列表中分配文献，每个文献只能分配到一个三级标题（即所有文献必须被分配完）。
3. 二级标题本身分配 {SUMMARY_WORDS_PER_TECH} 字作为总述，剩余 {sub_total_words} 字分配给三级标题。
4. 每个三级标题需标注所分配的文献编号和字数，如：
   ### 三级标题1 [1,2,3](600字)
   ### 三级标题2 [4,5,6](550字)
5. 确保三级标题的字数之和等于 {sub_total_words}。
6. 文献编号必须使用提供的序号（1-{total_citations}）。"""

                sub_user_prompt = f"""请为技术部分“{tech['title']}”生成2-3个三级标题，并从以下文献中为每个三级标题分配相关文献，确保所有文献都被分配。

技术部分总字数：{tech['words']}字（其中二级标题总述占 {SUMMARY_WORDS_PER_TECH}字，三级标题总字数应为 {sub_total_words}字）

文献列表：
{tech_papers_info}

请输出格式：
### 标题1 [文献编号](字数)
### 标题2 [文献编号](字数)
### 标题3 [文献编号](字数)  （如只有2个则输出2行）

重要：必须使用提供的文献编号，且所有文献都要被分配。字数总和必须为 {sub_total_words},三级标题生成2到3个即可，不允许生成过多,三级标题应为真正的一个题目，不允许有“标题”等字样。"""

                # 调用大模型生成三级标题
                sub_response = client.chat.completions.create(
                    model=openai_config['model'],
                    messages=[
                        {'role': 'system', 'content': sub_system_prompt},
                        {'role': 'user', 'content': sub_user_prompt}
                    ],
                    stream=False,
                    temperature=0.2,
                    max_tokens=3000,
                    timeout=default_timeout
                )

                if not sub_response or not sub_response.choices:
                    print(f"      三级标题生成失败，将使用默认占位")
                    tech['subheadings'] = []
                    continue

                sub_outline = sub_response.choices[0].message.content.strip()

                # 解析三级标题
                subheading_pattern = r'###\s+(.+?)\s*\[([\d,，\s]+)\]\((\d+)字\)'
                subheadings = []
                total_sub_words = 0
                assigned_papers_in_sub = set()
                for match in re.finditer(subheading_pattern, sub_outline):
                    sub_title = match.group(1).strip()
                    papers_str = match.group(2).replace('，', ',').replace(' ', '')
                    sub_papers = [int(x) for x in papers_str.split(',') if x.strip().isdigit()]
                    sub_words = int(match.group(3))
                    subheadings.append({
                        'title': sub_title,
                        'papers': sub_papers,
                        'papers_str': f"[{','.join(map(str, sub_papers))}]",
                        'words': sub_words
                    })
                    total_sub_words += sub_words
                    assigned_papers_in_sub.update(sub_papers)

                # 验证文献覆盖和字数
                expected_papers = set(paper_ids)
                if assigned_papers_in_sub != expected_papers:
                    print(f"      警告：三级标题文献分配不完全，期望 {expected_papers}，实际 {assigned_papers_in_sub}")
                    # 尝试修正：如果少了文献，随机补充到第一个三级标题（简化）
                    missing = expected_papers - assigned_papers_in_sub
                    if missing and subheadings:
                        subheadings[0]['papers'].extend(list(missing))
                        subheadings[0]['papers_str'] = f"[{','.join(map(str, subheadings[0]['papers']))}]"
                        print(f"          已将缺失文献 {missing} 添加到第一个三级标题")

                if abs(total_sub_words - sub_total_words) > 10:
                    print(f"      警告：三级标题字数总和 {total_sub_words} 与期望 {sub_total_words} 不符")
                    # 简单调整：按比例缩放字数（这里省略，保持原样）

                tech['subheadings'] = subheadings

                # 记录Token使用
                record_api_call(
                    count_tokens(sub_system_prompt) + count_tokens(sub_user_prompt),
                    count_tokens(sub_outline),
                    "outline_step2",
                    f"生成三级标题-{tech['title'][:20]}"
                )

            # ==================== 第三步：拼接完整大纲 ====================
            print("  步骤3：拼接完整大纲...")

            # 构建完整大纲
            full_outline = f"# {main_title}\n\n"
            full_outline += f"## 摘要({abstract_words}字)\n\n"
            full_outline += f"## 关键词\n\n"
            intro_papers_str = f"[{','.join(map(str, intro_papers))}]" if intro_papers else ""
            full_outline += f"## 引言 {intro_papers_str}({intro_words}字)\n\n"

            for tech in tech_headings:
                tech_papers_str = f"[{','.join(map(str, tech['papers']))}]"
                full_outline += f"## {tech['title']} {tech_papers_str}({SUMMARY_WORDS_PER_TECH}字)\n"
                if tech.get('subheadings'):
                    for sub in tech['subheadings']:
                        full_outline += f"### {sub['title']} {sub['papers_str']}({sub['words']}字)\n"
                else:
                    # 如果没有三级标题，可以添加一个默认的三级标题，或留空
                    full_outline += f"### （待补充）\n"
                full_outline += "\n"

            trend_papers_str = f"[{','.join(map(str, trend_papers))}]" if trend_papers else ""
            full_outline += f"## 当前研究趋势与热点 {trend_papers_str}({trend_words}字)\n\n"
            future_papers_str = f"[{','.join(map(str, future_papers))}]" if future_papers else ""
            full_outline += f"## 未来发展方向与挑战 {future_papers_str}({future_words}字)\n"

            outline = full_outline

            # 最终检查文献分配（可选）
            # 验证并过滤论文编号（确保所有编号在有效范围内）
            outline = _validate_and_filter_citations(outline, total_citations)

            print(f"  ✓ 深度模式大纲生成完成")
            return outline, citation_index_mapping

    except Exception as e:
        error_msg = f"生成大纲时出错: {e}"
        print(error_msg)
        import traceback
        traceback.print_exc()
        return error_msg, citation_index_mapping if 'citation_index_mapping' in dir() else {}

def _validate_and_filter_citations(outline_text, max_citation):
    """
    验证并过滤大纲中的论文编号，确保所有编号都在有效范围内

    Args:
        outline_text: 大纲文本
        max_citation: 最大允许的论文编号

    Returns:
        过滤后的大纲文本
    """
    lines = outline_text.split('\n')
    filtered_lines = []

    for line in lines:
        # 检查是否包含论文引用 [数字,数字,...]
        if re.search(r'\[\d+(?:,\s*\d+)*\]', line):
            # 提取所有编号
            citation_pattern = r'\[([^\]]+)\]'
            matches = re.findall(citation_pattern, line)

            for match in matches:
                # 提取数字
                numbers = re.findall(r'\d+', match)
                valid_numbers = []

                for num in numbers:
                    n = int(num)
                    if 1 <= n <= max_citation:
                        valid_numbers.append(str(n))

                if valid_numbers:
                    # 替换原引用为有效的引用
                    new_citation = '[' + ','.join(valid_numbers) + ']'
                    line = line.replace('[' + match + ']', new_citation)

        filtered_lines.append(line)

    return '\n'.join(filtered_lines)


def _check_all_citations_assigned(outline_text, total_citations):
    """
    检查大纲中是否所有引用文献都被分配到章节

    Args:
        outline_text: 大纲文本
        total_citations: 引用文献总数

    Returns:
        tuple: (是否全部分配, 未分配的序号列表)
    """
    # 提取大纲中所有被分配的论文编号
    allocated_citations = set()
    lines = outline_text.split('\n')

    for line in lines:
        # 检查是否包含论文引用 [数字,数字,...]
        if re.search(r'\[\d+(?:,\s*\d+)*\]', line):
            # 提取所有编号
            citation_pattern = r'\[([^\]]+)\]'
            matches = re.findall(citation_pattern, line)

            for match in matches:
                numbers = re.findall(r'\d+', match)
                for num in numbers:
                    n = int(num)
                    if 1 <= n <= total_citations:
                        allocated_citations.add(n)

    # 检查未分配的论文
    all_citations = set(range(1, total_citations + 1))
    unallocated = all_citations - allocated_citations

    if unallocated:
        return False, sorted(list(unallocated))
    return True, []


def _redistribute_unallocated_citations(outline_text, unallocated_citations, allocated_info, total_chapters=5):
    """
    重新分配未被分配的引用文献到已有章节

    Args:
        outline_text: 大纲文本
        unallocated_citations: 未分配的论文序号列表
        allocated_info: 已分配的论文信息 {章节标题: [论文序号列表]}
        total_chapters: 大致章节数，用于均匀分配

    Returns:
        修改后的大纲文本
    """
    if not unallocated_citations:
        return outline_text

    lines = outline_text.split('\n')
    modified_lines = []

    # 为每个未分配的论文找到最适合的章节
    # 策略：优先分配到技术总结章节（通常章节数较多）
    chapter_types = {
        '技术总结': [],
        '引言': [],
        '趋势': [],
        '展望': [],
        '其他': []
    }

    for title, papers in allocated_info.items():
        title_lower = title.lower()
        if '技术' in title or '方法' in title or '算法' in title or '模型' in title:
            chapter_types['技术总结'].extend(papers)
        elif '引言' in title_lower or 'introduction' in title_lower:
            chapter_types['引言'].extend(papers)
        elif '趋势' in title_lower or '热点' in title_lower:
            chapter_types['趋势'].extend(papers)
        elif '展望' in title_lower or '挑战' in title_lower or '发展' in title_lower:
            chapter_types['展望'].extend(papers)
        else:
            chapter_types['其他'].extend(papers)

    # 优先选择论文数最少的章节类型进行分配
    import random
    remaining = unallocated_citations.copy()

    for citation in remaining:
        # 找出当前论文数最少的章节类型
        min_type = min(chapter_types.keys(), key=lambda x: len(chapter_types[x]))
        chapter_types[min_type].append(citation)

    # 构建新的分配方案
    new_allocations = {}
    for title, papers in allocated_info.items():
        title_lower = title.lower()
        if '技术' in title or '方法' in title or '算法' in title or '模型' in title:
            new_allocations[title] = chapter_types['技术总结']
        elif '引言' in title_lower or 'introduction' in title_lower:
            new_allocations[title] = chapter_types['引言']
        elif '趋势' in title_lower or '热点' in title_lower:
            new_allocations[title] = chapter_types['趋势']
        elif '展望' in title_lower or '挑战' in title_lower or '发展' in title_lower:
            new_allocations[title] = chapter_types['展望']
        else:
            new_allocations[title] = chapter_types['其他']

    return outline_text


def _is_recent_paper(paper, quality_config=None):
    """判断是否为近期论文"""
    if quality_config is None:
        from config import get_quality_config
        quality_config = get_quality_config()

    current_year = datetime.now().year
    published = paper.get('published', '')
    if not published:
        return False

    try:
        # 尝试提取年份
        year_match = re.search(r'(\d{4})', str(published))
        if year_match:
            year = int(year_match.group(1))
            return year >= current_year - quality_config['recent_paper_years']
    except:
        pass
    return False


def _is_high_citation_paper(paper, quality_config=None):
    """判断是否为高引用论文"""
    if quality_config is None:
        from config import get_quality_config
        quality_config = get_quality_config()

    citation_count = paper.get('citation_count')
    if citation_count is not None:
        try:
            return int(citation_count) >= quality_config['high_citation_threshold']
        except:
            pass
    return False


def parse_outline_structure(outline_text):
    """
    解析大纲文本，提取标题结构、论文编号和内容

    Args:
        outline_text: 大纲文本

    Returns:
        章节结构列表，每个章节包含title、papers、level、word_count和content
    """
    sections = []
    lines = outline_text.split('\n')

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        # 检查是否是标题行（以#开头）
        if line.startswith('#'):
            # 改进的正则表达式，处理三种情况：
            # 1. 只有标题
            # 2. 标题后跟括号字数：标题(200字)
            # 3. 标题后跟论文编号和括号字数：标题 [1,2,3](400字)
            title_match = re.match(r'^#+\s+(.+?)(?:(?:\s*\[([^\]]+)\])?\s*\((\d+)字\))?$', line)
            if title_match:
                title_full = title_match.group(1).strip()
                paper_refs = title_match.group(2)
                word_count_str = title_match.group(3)

                # 提取纯标题（去除可能的括号数字）
                title = re.sub(r'\s*\(\d+字\)$', '', title_full)

                # 解析论文编号
                paper_indices = []
                if paper_refs:
                    # 提取所有数字，包括逗号分隔的和数字范围
                    refs = re.findall(r'\d+', paper_refs)
                    paper_indices = [int(n) for n in refs]

                # 解析字数
                word_count = None
                if word_count_str:
                    word_count = int(word_count_str)

                # 如果字数没有在正则中匹配到，检查标题中是否包含(数字字)格式
                if not word_count:
                    word_match = re.search(r'\((\d+)字\)', title_full)
                    if word_match:
                        word_count = int(word_match.group(1))
                        # 从title中移除字数信息
                        title = re.sub(r'\s*\(\d+字\)$', '', title)

                # 初始化章节信息
                section_info = {
                    'title': title,
                    'papers': paper_indices,
                    'level': line.count('#'),
                    'word_count': word_count,
                    'content': None  # 默认无内容
                }

                # 特殊处理关键词部分
                if title.lower() in ['关键词', 'keywords', 'keyword']:
                    # 收集关键词内容（直到下一个标题或空行）
                    content_lines = []
                    j = i + 1
                    while j < len(lines):
                        next_line = lines[j].strip()
                        if not next_line or next_line.startswith('#'):
                            break
                        content_lines.append(lines[j])  # 保留原始格式
                        j += 1

                    if content_lines:
                        section_info['content'] = '\n'.join(content_lines)
                        i = j - 1  # 跳过已处理的行

                # 检查下一行是否是论文编号列表
                elif i + 1 < len(lines) and not lines[i + 1].startswith('#') and lines[i + 1].strip():
                    # 检查下一行是否以"- 论文编号"或"论文编号"开头
                    next_line = lines[i + 1].strip()
                    if (next_line.startswith('- 论文编号') or
                            next_line.startswith('论文编号') or
                            next_line.startswith('• 论文编号')):

                        content_lines = []
                        j = i + 1
                        while j < len(lines):
                            curr_line = lines[j].strip()
                            if not curr_line or curr_line.startswith('#'):
                                break
                            content_lines.append(lines[j])  # 保留原始格式
                            j += 1

                        if content_lines:
                            section_info['content'] = '\n'.join(content_lines)
                            i = j - 1  # 跳过已处理的行

                sections.append(section_info)
        i += 1

    return sections


def parse_outline_structure_0(outline_text):
    """
    解析大纲文本，提取标题结构、论文编号和内容

    Args:
        outline_text: 大纲文本

    Returns:
        章节结构列表，每个章节包含title、papers、level、word_count和content
    """
    sections = []
    lines = outline_text.split('\n')

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        # 检查是否是标题行
        if line.startswith('#'):
            # 解析标题、论文编号和字数
            title_match = re.match(r'^#+\s+(.+?)(?:\s*\[([^\]]+)\](?:\s*\((\d+字)\))?)?$', line)
            if title_match:
                title = title_match.group(1).strip()
                paper_refs = title_match.group(2)
                word_count_str = title_match.group(3)

                # 解析论文编号 - 保持原始全局序号不变
                paper_indices = []
                if paper_refs:
                    numbers = re.findall(r'\d+', paper_refs)
                    paper_indices = [int(n) for n in numbers]

                # 解析字数
                word_count = None
                if word_count_str:
                    word_match = re.match(r'(\d+)字', word_count_str)
                    if word_match:
                        word_count = int(word_match.group(1))

                # 初始化章节信息
                section_info = {
                    'title': title,
                    'papers': paper_indices,
                    'level': line.count('#'),
                    'word_count': word_count,
                    'content': None  # 默认无内容
                }

                # 特殊处理关键词：检查下一行是否有内容
                if title.lower() in ['关键词', 'keywords', 'keyword']:
                    # 收集关键词内容（直到下一个标题或空行）
                    content_lines = []
                    j = i + 1
                    while j < len(lines):
                        next_line = lines[j].strip()
                        if not next_line or next_line.startswith('#'):
                            break
                        content_lines.append(next_line)
                        j += 1

                    if content_lines:
                        section_info['content'] = '\n'.join(content_lines)
                        i = j - 1  # 跳过已处理的行

                sections.append(section_info)

        i += 1

    return sections
