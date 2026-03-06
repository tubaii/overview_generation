"""
学术综述正文撰写模块

此模块负责：
1. 基于大纲逐标题撰写综述正文
2. 为研究趋势和未来展望提供上下文
3. 对生成的综述进行审阅和修改
"""

from openai import OpenAI
from datetime import datetime
import re

# Token计数
from token_counter import record_api_call, count_tokens

# 初始化OpenAI客户端（从配置中读取）
from config import get_openai_config
openai_config = get_openai_config()
# 综述撰写涉及大量文本，增加超时时间
default_timeout = max(openai_config['timeout'], 120)
client = OpenAI(
    base_url=openai_config['base_url'],
    api_key=openai_config['api_key'],
    timeout=default_timeout
)


def generate_abstract(titles, contents, abstract_section, papers):
    """
    基于其他所有章节内容生成摘要

    Args:
        titles: 已完成章节的标题列表
        contents: 已完成章节的内容列表
        abstract_section: 摘要章节信息
        papers: 论文列表
        keyword: 关键词

    Returns:
        生成的摘要内容
    """
    print(f"  正在基于{len(titles)}个章节的内容生成摘要...")

    try:
        # 组合其他所有章节的内容作为上下文
        other_content = ""
        for title, content in zip(titles, contents):
            other_content += f"\n## {title}\n{content}"

        # 摘要的论文分配
        paper_indices = abstract_section.get('papers', [])
        allowed_citations = paper_indices

        # 构建摘要生成提示词
        system_prompt = f"""你是一位专业的综述摘要撰写专家，擅长根据综述内容撰写高质量的学术摘要。

摘要撰写要求：
1. 基于提供的文章各章节内容，提炼出全文的核心内容和主题，并加以介绍
2. 摘要应该对综述内容有总览性全局性的介绍，不应该介绍详细的技术内容
3. 语言要简洁、准确、学术化
4. 字数控制在200-300字左右
5. 摘要内容是综述全文的浓缩，无需引用论文


请直接输出摘要内容，不要包含"摘要"标题。"""

        # 准备论文信息（如果需要引用）
        relevant_content = ""
        for paper_idx in paper_indices:
            if 1 <= paper_idx <= len(papers):
                paper = papers[paper_idx - 1]
                title = paper.get('title', '未知标题')
                relevant_content += f"\n论文[{paper_idx}]: {title}"

        user_prompt = f"""请基于以下文章内容撰写学术摘要：

文章各章节内容：
{other_content}

相关参考文献：
{relevant_content}

要求：
- 提炼核心内容和关键分析
- 字数：200-300字
- 学术化语言

请直接输出摘要内容："""

        # 调用AI生成摘要，添加超时控制
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
            temperature=0.3,  # 摘要生成使用较低温度，确保稳定
            timeout=default_timeout
        )

        # 计算并记录Token使用
        input_tokens = count_tokens(system_prompt) + count_tokens(user_prompt)
        if response and response.choices:
            output_text = response.choices[0].message.content or ""
            output_tokens = count_tokens(output_text)
        else:
            output_tokens = 0
        record_api_call(input_tokens, output_tokens, "abstract", "生成摘要")

        if response and response.choices and len(response.choices) > 0:
            abstract_content = response.choices[0].message.content.strip()
            print(f"  [OK] 摘要生成完成 (输入:{input_tokens}, 输出:{output_tokens})")
            return abstract_content
        else:
            print("  [ERROR] 摘要生成失败")
            return "摘要生成失败，请手动完善。"

    except Exception as e:
        print(f"  [ERROR] 摘要生成出错: {e}")
        return "摘要生成失败，请手动完善。"

def generate_keywords(titles, contents, keyword_section, papers):
    """
    基于其他所有章节内容生成摘要

    Args:
        titles: 已完成章节的标题列表
        contents: 已完成章节的内容列表
        abstract_section: 摘要章节信息
        papers: 论文列表
        keyword: 关键词

    Returns:
        生成的摘要内容
    """
    print(f"  正在基于{len(titles)}个章节的内容生成关键词...")

    try:
        # 组合其他所有章节的内容作为上下文
        other_content = ""
        for title, content in zip(titles, contents):
            other_content += f"\n## {title}\n{content}"

        # 摘要的论文分配
        paper_indices = keyword_section.get('papers', [])
        allowed_citations = paper_indices

        # 构建摘要生成提示词
        system_prompt = f"""你是一位专业的综述关键词撰写专家，擅长根据文章内容撰写合适的三到六个关键词。

摘要撰写要求：
基于提供的文章各章节内容，提炼出全文的核心，生成三到六个关键词


请直接输出关键词，不要包含"关键词"标题。"""

        # 准备论文信息（如果需要引用）
        relevant_content = ""
        for paper_idx in paper_indices:
            if 1 <= paper_idx <= len(papers):
                paper = papers[paper_idx - 1]
                title = paper.get('title', '未知标题')
                relevant_content += f"\n论文[{paper_idx}]: {title}"

        user_prompt = f"""请基于以下文章内容撰写三到六个关键词：

文章各章节内容：
{other_content}

相关参考文献：
{relevant_content}

要求：
- 提炼核心内容和主要贡献，生成适合全文的三到六个关键词
- 输出格式为： 关键词1，关键词2，...

请直接输出关键词内容："""

        # 调用AI生成摘要，添加超时控制
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
            temperature=0.3,  # 摘要生成使用较低温度，确保稳定
            timeout=default_timeout
        )

        # 计算并记录Token使用
        input_tokens = count_tokens(system_prompt) + count_tokens(user_prompt)
        if response and response.choices:
            output_text = response.choices[0].message.content or ""
            output_tokens = count_tokens(output_text)
        else:
            output_tokens = 0
        record_api_call(input_tokens, output_tokens, "keywords", "生成关键词")

        if response and response.choices and len(response.choices) > 0:
            abstract_content = response.choices[0].message.content.strip()
            print(f"  [OK] 关键词生成完成 (输入:{input_tokens}, 输出:{output_tokens})")
            return abstract_content
        else:
            print("  [ERROR] 关键词生成失败")
            return "摘要生成失败，请手动完善。"

    except Exception as e:
        print(f"  [ERROR] 关键词生成出错: {e}")
        return "关键词生成失败，请手动完善。"

def validate_citation_compliance(text, allowed_paper_indices):
    """
    验证生成的文本是否只使用了允许的引用序号

    Args:
        text: 生成的文本内容
        allowed_paper_indices: 允许的论文索引列表（0-based）

    Returns:
        bool: 是否符合引用要求
    """
    result, invalid_citations = validate_citation_compliance_detailed(text, allowed_paper_indices)
    return result

def validate_citation_compliance_detailed(text, allowed_paper_indices):
    """
    详细验证生成的文本中的引用序号

    Args:
        text: 生成的文本内容
        allowed_paper_indices: 允许的论文索引列表（0-based）

    Returns:
        tuple: (是否符合要求, 不符合要求的序号列表)
    """
    import re

    # 找到文本中的所有引用
    citation_pattern = r'\[(\d+(?:,\s*\d+)*)\]'
    citations = re.findall(citation_pattern, text)

    # 转换为数字列表
    used_citations = []
    for citation in citations:
        numbers = re.findall(r'\d+', citation)
        used_citations.extend([int(n) for n in numbers])

    # 去除重复
    used_citations = list(set(used_citations))

    # 检查是否只使用了允许的序号（全局序号）
    allowed_citations = allowed_paper_indices  # 直接使用全局序号
    invalid_citations = []

    for citation in used_citations:
        if citation not in allowed_citations:
            invalid_citations.append(citation)

    if invalid_citations:
        print(f"    发现不允许的引用序号: {invalid_citations}，允许的序号: {allowed_citations}")
        return False, invalid_citations

    return True, []

def write_review_from_outline(outline, reference_papers, keyword, citation_papers=None):
    """
    基于大纲逐标题撰写综述正文

    Args:
        outline: 综述大纲文本（包含标题和对应论文分配）
        reference_papers: 所有参考文献列表（用于了解全文背景）
        keyword: 关键词
        citation_papers: 引用文献列表（用于文中引用），默认为None则使用reference_papers

    Returns:
        完整的综述文本
    """
    print(f"\n正在基于大纲撰写综述正文...")
    print(f"  参考文献总数: {len(reference_papers)}")
    print(f"  引用文献总数: {len(citation_papers) if citation_papers else len(reference_papers)}")

    # 如果citation_papers未提供，使用reference_papers
    if citation_papers is None:
        citation_papers = reference_papers

    try:
        # 解析大纲结构
        from outline_generator import parse_outline_structure
        sections = parse_outline_structure(outline)

        if not sections:
            return "解析大纲失败，无法生成综述。"

        # 初始化完成的综述内容
        completed_sections = []
        completed_titles = []  # 保存已完成的标题，用于上下文

        # 按章节分组：将二级标题和其三级子标题组合在一起
        chapter_groups = []
        current_chapter = None

        for section in sections:
            section_title = section['title']
            section_level = section.get('level', 2)

            # 跳过一级标题（总标题）
            if section_level == 1:
                total_title=section_title
                continue

            # 摘要单独处理
            if section_title.lower() in ['摘要', 'abstract', 'summary']:
                abstract_section = section
                continue

            # 关键词单独处理
            if section_title.lower() in ['关键词', 'keywords', 'keyword']:
                keywords_section = section
                continue

            # 二级标题：开始新章节
            if section_level == 2:
                if current_chapter:
                    chapter_groups.append(current_chapter)
                current_chapter = {
                    'title': section_title,
                    'papers': section.get('papers', []),
                    'word_count': section.get('word_count'),
                    'subsections': []
                }
            # 三级标题：添加到当前章节
            # elif section_level == 3 and current_chapter:
            #     current_chapter['subsections'].append({
            #         'title': section_title,
            #         'papers': section.get('papers', []),
            #         'word_count': section.get('word_count')
            #     })

        # 添加最后一个章节
        if current_chapter:
            chapter_groups.append(current_chapter)

        print(f"  共解析到 {len(sections)} 个原始章节，组织为 {len(chapter_groups)} 个章节组")

        # 逐章节撰写内容
        completed_chapters = []

        # 构建所有参考文献的完整信息（用于背景了解）
        all_reference_content = ""
        for ref_idx, paper in enumerate(reference_papers, 1):
            title = paper.get('title') or '未知标题'
            authors = paper.get('authors') or []
            published = paper.get('published') or '未知'
            venue = paper.get('venue') or ''
            citation_count = paper.get('citation_count')
            summary = paper.get('summary') or '无摘要'

            all_reference_content += f"\n=== 参考文献[{ref_idx}] ===\n"
            all_reference_content += f"标题: {title}\n"
            all_reference_content += f"作者: {', '.join(authors) if authors else '未知'}\n"
            all_reference_content += f"发表时间: {published}\n"
            if venue:
                all_reference_content += f"来源: {venue}\n"
            if citation_count is not None:
                all_reference_content += f"引用数: {citation_count}\n"
            all_reference_content += f"摘要: {summary}\n"
        for i, chapter in enumerate(chapter_groups):
            chapter_title = chapter['title']
            chapter_papers = chapter['papers']
            subsections = chapter.get('subsections', [])

            print(f"  正在撰写章节 [{i+1}/{len(chapter_groups)}]: {chapter_title}")

            # 合并本章节及其子章节的所有论文
            all_paper_indices = chapter_papers.copy()

            # 计算总字数要求
            chapter_word_count = chapter.get('word_count') or 0
            subsection_word_counts = sum((sub.get('word_count') or 0) for sub in subsections)
            total_word_count = chapter_word_count + subsection_word_counts
            word_requirement = f"字数要求：{total_word_count}字" if total_word_count > 0 else "字数适当控制"

            # 获取该章节分配的引用文献（用于引用）
            citation_papers_for_chapter = []
            for paper_idx in all_paper_indices:  # paper_idx是全局1-based序号
                if 1 <= paper_idx <= len(citation_papers):  # 1-based检查
                    paper = citation_papers[paper_idx - 1]  # 转换为0-based访问
                    citation_papers_for_chapter.append({
                        'global_idx': paper_idx,
                        'paper': paper
                    })

            # 构建被分配引用文献的详细信息
            cited_paper_content = ""
            for item in citation_papers_for_chapter:
                paper_idx = item['global_idx']
                paper = item['paper']

                title = paper.get('title') or '未知标题'
                authors = paper.get('authors') or []
                published = paper.get('published') or '未知'
                venue = paper.get('venue') or ''
                citation_count = paper.get('citation_count')
                summary = paper.get('summary') or '无摘要'

                cited_paper_content += f"\n=== 引用文献[{paper_idx}] ===\n"  # 使用新序号
                cited_paper_content += f"标题: {title}\n"
                cited_paper_content += f"作者: {', '.join(authors) if authors else '未知'}\n"
                cited_paper_content += f"发表时间: {published}\n"
                if venue:
                    cited_paper_content += f"来源: {venue}\n"
                if citation_count is not None:
                    cited_paper_content += f"引用数: {citation_count}\n"
                cited_paper_content += f"摘要: {summary}\n"

                # 添加全文内容（如果有）
                full_text = paper.get('full_text', {})
                if isinstance(full_text, dict) and full_text.get('content_type') != 'metadata_only' and full_text.get('content'):
                    content = full_text.get('content')
                    content_type = full_text.get('content_type', 'unknown')
                    if content_type == 'latex':
                        cited_paper_content += f"全文内容（LaTeX）: {content[:2000]}...\n"
                    elif content_type == 'xml':
                        cited_paper_content += f"全文内容（XML）: {content[:2000]}...\n"
                    elif content_type == 'pdf_text':
                        cited_paper_content += f"全文内容（PDF）: {content[:2000]}...\n"
                elif paper.get('latex_content'):
                    cited_paper_content += f"全文内容（LaTeX）: {paper['latex_content'][:2000]}...\n"
            # 构建提示词
            allowed_citations = all_paper_indices  # 使用章节的所有论文序号（新序号）

            # 章节级别的提示词
            # 准备章节结构信息
            system_prompt = f"""你是一位专业的中文学术综述撰写专家，擅长总结技术，分析趋势，专门负责根据确定的章节题目和分配的论文撰写该章节题目下的中文综述内容。

严格写作要求（必须严格遵守，否则将重新生成）：
1. 任务定位：
   - 你可以阅读所有{len(reference_papers)}篇参考文献了解该领域的研究背景
   - 重要！！除了引言，研究趋势和未来发展这三个章节外，在其他章节你必须着重分析介绍本章节分配的{len(all_paper_indices)}篇引用文献的技术内容
   - 技术路线有相似性的论文应该放在一起描述
   - 尤其要注意所写的内容要和引用的论文一致，不允许自己无根据写作

2. 引用规则（最重要，严格执行）：
   - 本章节只能使用以下新序号进行引用：{allowed_citations}
   - 必须使用[序号]格式，如[5]、[8]、[5,8]、[5,12,15]
   - 绝对禁止使用其他任何序号，只能使用大纲分配的序号
   - 绝对禁止引用未分配给本章节的论文
   - 序号对应关系（必须记住，新序号按发表时间最新在前排列）：
{chr(10).join([f"     [{paper_idx}] = 引用文献列表中序号{paper_idx}的论文" for paper_idx in allowed_citations])}

3. 内容要求：
   - 内容要完整、连贯
   - 使用学术化的语言，确保论述严谨
   - 段落之间不要有空行
   - 要着重分析分配给本章节的引用文献

4. 输出要求：
   - 直接输出章节的完整内容，不要重复章节标题
   - {word_requirement}

严重警告：如果生成的内容中出现任何不允许的引用序号，整个内容将被拒绝并重新生成。请确保100%遵守上述引用规则！"""
            user_prompt = f"""请根据以下信息撰写完整的章节内容，你所写的内容将放在总标题“{total_title}”的章节标题"{chapter_title}下"

=== 重要说明 ===
- 你可以阅读所有{len(reference_papers)}篇参考文献了解该领域的研究背景
- 但你必须着重分析介绍本章节分配的{len(all_paper_indices)}篇引用文献的技术内容

=== 严格引用规则（必须100%遵守，否则将被拒绝） ===
本章节只能使用以下新序号进行引用：{all_paper_indices}
禁止使用任何其他序号！

=== 序号映射关系（必须记住，新序号按发表时间最新在前排列） ===
{chr(10).join([f"[{paper_idx}] = 引用文献列表中序号{paper_idx}的论文" for paper_idx in allowed_citations])}

=== 所有参考文献（了解背景） ===
（共{len(reference_papers)}篇）
{all_reference_content}

=== 本章节分配的引用文献（着重分析介绍） ===
（共{len(all_paper_indices)}篇）
{cited_paper_content}

要求：
1. 可以参考其他参考文献了解背景，但只能引用本章节分配的论文
2. 只能使用大纲指定的新序号{all_paper_indices}
3. 绝对不能使用其他序号
4. 如果不需要引用，可以不使用引用
5. {word_requirement}
6. 只输出章节内容，不要重复包含标题
7. 如果需要分析技术，相似技术的论文应该写在一起进行对比分析，引言，研究趋势和未来展望章节不需要详细分析技术内容

请直接输出章节的中文完整正文内容："""
            if "引言" in chapter_title:
                system_prompt = f"""你是一位专业的中文学术综述撰写专家，擅长总结技术，分析趋势，专门负责根据确定的章节题目和分配的论文撰写该章节题目下的中文综述内容。

                严格写作要求（必须严格遵守，否则将重新生成）：
                1. 任务定位：
                   - 你可以阅读所有{len(reference_papers)}篇参考文献了解该领域的研究背景
                   - 重要！！目前你需要书写综述题目为‘{total_title}’的综述正文的引言部分，你应当使用分配的论文对符合该主题的研究背景和意义进行详细描述

                2. 引用规则（最重要，严格执行）：
                   - 本章节只能使用以下新序号进行引用：{allowed_citations}
                   - 必须使用[序号]格式，如[5]、[8]、[5,8]、[5,12,15]
                   - 绝对禁止使用其他任何序号，只能使用大纲分配的序号
                   - 绝对禁止引用未分配给本章节的论文
                   - 序号对应关系（必须记住，新序号按发表时间最新在前排列）：
                {chr(10).join([f"     [{paper_idx}] = 引用文献列表中序号{paper_idx}的论文" for paper_idx in allowed_citations])}

                3. 内容要求：
                   - 内容要完整、连贯
                   - 使用学术化的语言，确保论述严谨
                   - 段落之间不要有空行

                4. 输出要求：
                   - 直接输出章节的完整内容，不要重复章节标题
                   - {word_requirement}

                严重警告：如果生成的内容中出现任何不允许的引用序号，整个内容将被拒绝并重新生成。请确保100%遵守上述引用规则！"""
                user_prompt = f"""请根据以下信息撰写完整的章节内容，你所写的内容将放在标题"{chapter_title}下"

                === 重要说明 ===
                - 你可以阅读所有{len(reference_papers)}篇参考文献了解该领域的研究背景
                - 你必须注重分析该主题的研究背景，研究趋势，研究现状，研究意义，在引言部分写出适合主题的总览性介绍性文字

                === 严格引用规则（必须100%遵守，否则将被拒绝） ===
                本章节只能使用以下新序号进行引用：{all_paper_indices}
                禁止使用任何其他序号！

                === 序号映射关系（必须记住，新序号按发表时间最新在前排列） ===
                {chr(10).join([f"[{paper_idx}] = 引用文献列表中序号{paper_idx}的论文" for paper_idx in allowed_citations])}

                === 所有参考文献（了解背景） ===
                （共{len(reference_papers)}篇）
                {all_reference_content}

                === 本章节分配的引用文献（引用介绍） ===
                （共{len(all_paper_indices)}篇）
                {cited_paper_content}

                要求：
                1. 可以参考其他参考文献了解背景，但只能引用本章节分配的论文
                2. 只能使用大纲指定的新序号{all_paper_indices}
                3. 绝对不能使用其他序号
                4. 如果不需要引用，可以不使用引用
                5. {word_requirement}
                6. 只输出章节内容，不要重复包含标题

                请直接输出章节的中文完整正文内容："""
            # 检查是否是需要上下文的章节
            previous_content = ""
            if "当前研究趋势与热点" in chapter_title:
                # 为研究趋势和未来展望提供之前的所有内容作为上下文
                if completed_sections:
                    previous_content = "\n\n".join(completed_chapters)
                context_part = f"\n\n前面的综述内容（作为上下文参考）：{previous_content}" if previous_content else ""
                system_prompt = f"""你是一位专业的中文学术综述撰写专家，擅长总结技术，分析趋势，专门负责根据确定的章节题目和分配的论文撰写该章节题目下的中文综述内容。

                严格写作要求（必须严格遵守，否则将重新生成）：
                1. 任务定位：
                   - 你可以阅读所有{len(reference_papers)}篇参考文献了解该领域的研究背景
                   - 重要！！目前你需要书写综述题目为‘{total_title}’的综述正文的研究趋势总结分析部分，你应当使用分配的论文和前文中已经写好的综述正文对符合该主题的研究趋势进行详细分析

                2. 引用规则（最重要，严格执行）：
                   - 本章节只能使用以下新序号进行引用：{allowed_citations}
                   - 必须使用[序号]格式，如[5]、[8]、[5,8]、[5,12,15]
                   - 绝对禁止使用其他任何序号，只能使用大纲分配的序号
                   - 绝对禁止引用未分配给本章节的论文
                   - 序号对应关系（必须记住，新序号按发表时间最新在前排列）：
                {chr(10).join([f"     [{paper_idx}] = 引用文献列表中序号{paper_idx}的论文" for paper_idx in allowed_citations])}

                3. 内容要求：
                   - 内容要完整、连贯
                   - 使用学术化的语言，确保论述严谨
                   - 段落之间不要有空行

                4. 输出要求：
                   - 直接输出章节的完整内容，不要重复章节标题
                   - {word_requirement}

                严重警告：如果生成的内容中出现任何不允许的引用序号，整个内容将被拒绝并重新生成。请确保100%遵守上述引用规则！"""
                user_prompt = f"""请根据以下信息撰写完整的章节内容，你所写的内容将放在标题"{chapter_title}下"

                === 重要说明 ===
                - 你可以阅读所有{len(reference_papers)}篇参考文献了解该领域的研究背景
                - 你必须总结上文中已写好的内容，结合分配的到的论文进行当前研究趋势和热点的分析，不应当详细分析技术路线！

                === 严格引用规则（必须100%遵守，否则将被拒绝） ===
                本章节只能使用以下新序号进行引用：{all_paper_indices}
                禁止使用任何其他序号！

                === 序号映射关系（必须记住，新序号按发表时间最新在前排列） ===
                {chr(10).join([f"[{paper_idx}] = 引用文献列表中序号{paper_idx}的论文" for paper_idx in allowed_citations])}

                === 所有参考文献（了解背景） ===
                （共{len(reference_papers)}篇）
                {all_reference_content}{context_part}

                === 本章节分配的引用文献（引用，无需详细介绍技术内容） ===
                （共{len(all_paper_indices)}篇）
                {cited_paper_content}

                要求：
                1. 可以参考其他参考文献了解背景，但只能引用本章节分配的论文
                2. 只能使用大纲指定的新序号{all_paper_indices}
                3. 绝对不能使用其他序号
                4. 如果不需要引用，可以不使用引用
                5. {word_requirement}
                6. 只输出章节内容，不要重复包含标题

                请直接输出章节的中文完整正文内容："""
            if "未来发展方向与挑战" in chapter_title:
                # 为研究趋势和未来展望提供之前的所有内容作为上下文
                if completed_sections:
                    previous_content = "\n\n".join(completed_chapters)
                context_part = f"\n\n前面的综述内容（作为上下文参考）：{previous_content}" if previous_content else ""
                system_prompt = f"""你是一位专业的中文学术综述撰写专家，擅长总结技术，分析趋势，专门负责根据确定的章节题目和分配的论文撰写该章节题目下的中文综述内容。

                严格写作要求（必须严格遵守，否则将重新生成）：
                1. 任务定位：
                   - 你可以阅读所有{len(reference_papers)}篇参考文献了解该领域的研究背景
                   - 重要！！目前你需要书写综述题目为‘{total_title}’的综述正文的未来发展方向和挑战部分，你应当使用分配的论文和前文中已经写好的综述正文对该主题的未来发展进行详细分析

                2. 引用规则（最重要，严格执行）：
                   - 本章节只能使用以下新序号进行引用：{allowed_citations}
                   - 必须使用[序号]格式，如[5]、[8]、[5,8]、[5,12,15]
                   - 绝对禁止使用其他任何序号，只能使用大纲分配的序号
                   - 绝对禁止引用未分配给本章节的论文
                   - 序号对应关系（必须记住，新序号按发表时间最新在前排列）：
                {chr(10).join([f"     [{paper_idx}] = 引用文献列表中序号{paper_idx}的论文" for paper_idx in allowed_citations])}

                3. 内容要求：
                   - 内容要完整、连贯
                   - 使用学术化的语言，确保论述严谨
                   - 段落之间不要有空行

                4. 输出要求：
                   - 直接输出章节的完整内容，不要重复章节标题
                   - {word_requirement}

                严重警告：如果生成的内容中出现任何不允许的引用序号，整个内容将被拒绝并重新生成。请确保100%遵守上述引用规则！"""
                user_prompt = f"""请根据以下信息撰写完整的章节内容，你所写的内容将放在标题"{chapter_title}下"

                === 重要说明 ===
                - 你可以阅读所有{len(reference_papers)}篇参考文献了解该领域的研究背景
                - 你必须总结上文中已写好的内容，结合分配的到的论文进行未来研究方向和发展方向的分析，不应当详细分析技术路线！

                === 严格引用规则（必须100%遵守，否则将被拒绝） ===
                本章节只能使用以下新序号进行引用：{all_paper_indices}
                禁止使用任何其他序号！

                === 序号映射关系（必须记住，新序号按发表时间最新在前排列） ===
                {chr(10).join([f"[{paper_idx}] = 引用文献列表中序号{paper_idx}的论文" for paper_idx in allowed_citations])}

                === 所有参考文献（了解背景） ===
                （共{len(reference_papers)}篇）
                {all_reference_content}{context_part}

                === 本章节分配的引用文献（引用，无需详细介绍技术内容） ===
                （共{len(all_paper_indices)}篇）
                {cited_paper_content}

                要求：
                1. 可以参考其他参考文献了解背景，但只能引用本章节分配的论文
                2. 只能使用大纲指定的新序号{all_paper_indices}
                3. 绝对不能使用其他序号
                4. 如果不需要引用，可以不使用引用
                5. {word_requirement}
                6. 只输出章节内容，不要重复包含标题

                请直接输出章节的中文完整正文内容："""
            # 调用大模型撰写章节内容
            max_retries = 3  # 最多重试3次
            chapter_content = None
            for attempt in range(max_retries):
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
                    temperature=0.5,
                    timeout=default_timeout
                )

                # 计算并记录Token使用
                input_tokens = count_tokens(system_prompt) + count_tokens(user_prompt)
                if response and response.choices:
                    output_text = response.choices[0].message.content or ""
                    output_tokens = count_tokens(output_text)
                else:
                    output_tokens = 0
                record_api_call(input_tokens, output_tokens, "review", f"撰写章节: {chapter_title}")

                if response and response.choices and len(response.choices) > 0:
                    candidate_content = response.choices[0].message.content.strip()

                    # 验证引用序号是否符合要求
                    validation_passed, invalid_citations = validate_citation_compliance_detailed(candidate_content, all_paper_indices)

                    if candidate_content and validation_passed:
                        chapter_content = candidate_content
                        print(f"    [OK] 完成章节: {chapter_title} (尝试 {attempt + 1})")
                        print(f"\n=== 生成的章节内容 ===")
                        print(f"章节标题: {chapter_title}")
                        print(f"内容长度: {len(candidate_content)} 字符")
                        print(f"内容预览: {candidate_content[:200]}..." if len(candidate_content) > 200 else f"完整内容: {candidate_content}")
                        print(f"=== 章节内容结束 ===\n")
                        break
                else:
                    print(f"    [ERROR] API调用失败 (尝试 {attempt + 1})")
                    if attempt == max_retries - 1:
                        break
            # for
            # 如果所有尝试都失败，使用备用内容
            if not chapter_content:
                chapter_content = f"[{chapter_title}内容生成失败，请手动完善]"
                print(f"    [ERROR] 多次尝试后仍失败，使用备用内容")

            completed_chapters.append({
                'title': chapter_title,
                'content': chapter_content
            })
        # 生成摘要（基于已完成的其他所有内容）
        if abstract_section:
            print("\n正在生成摘要（基于其他所有章节内容）...")
            # 提取所有已完成章节的内容用于生成摘要
            chapter_titles = [chap['title'] for chap in completed_chapters]
            chapter_contents = [chap['content'] for chap in completed_chapters]
            abstract_content = generate_abstract(chapter_titles, chapter_contents, abstract_section, reference_papers)

            # 将摘要插入到引言之前的位置
            abstract_title = abstract_section['title']

            # 找到引言的位置
            intro_index = -1
            for i, chap in enumerate(completed_chapters):
                if chap['title'].lower() in ['引言', 'introduction', 'intro']:
                    intro_index = i
                    break

            if intro_index >= 0:
                # 插入到引言之前
                completed_chapters.insert(intro_index, {
                    'title': abstract_title,
                    'content': abstract_content
                })
            else:
                # 如果没找到引言，插入到开头
                completed_chapters.insert(0, {
                    'title': abstract_title,
                    'content': abstract_content
                })
        # 生成关键词（基于已完成的其他所有内容）
        if keywords_section:
            print("\n正在生成关键词（基于其他所有章节内容）...")
            # 提取所有已完成章节的内容用于生成摘要
            chapter_titles = [chap['title'] for chap in completed_chapters]
            chapter_contents = [chap['content'] for chap in completed_chapters]
            keywords_content = generate_keywords(chapter_titles, chapter_contents, keywords_section, reference_papers)

            # 将关键词插入到引言之前的位置
            keywords_title = keywords_section['title']

            # 找到引言的位置
            intro_index = -1
            for i, chap in enumerate(completed_chapters):
                if chap['title'].lower() in ['引言', 'introduction', 'intro']:
                    intro_index = i
                    break

            if intro_index >= 0:
                # 插入到引言之前
                completed_chapters.insert(intro_index, {
                    'title': keywords_title,
                    'content': keywords_content
                })
            else:
                # 如果没找到引言，插入到开头
                completed_chapters.insert(0, {
                    'title': keywords_title,
                    'content': keywords_content
                })
        # 组合最终的综述：标题 + 内容
        final_review_parts = []
        for chap in completed_chapters:
            final_review_parts.append(f"## {chap['title']}\n{chap['content']}")

        final_review = "\n\n".join(final_review_parts)

        print("  [OK] 综述正文撰写完成")
        print(f"  共完成 {len(completed_chapters)} 个章节")

        # 打印完整的综述内容
        print(f"\n{'='*80}")
        print("生成的完整综述正文内容：")
        print(f"{'='*80}")
        print(final_review)
        print(f"{'='*80}")
        print(f"综述总长度: {len(final_review)} 字符")
        print(f"包含章节数: {len(completed_chapters)}")

        return final_review

    except Exception as e:
        error_msg = f"基于大纲撰写综述时出错: {e}"
        print(error_msg)
        return error_msg
def write_review_from_outline_deep(outline, reference_papers, keyword, citation_papers=None):
    """
    基于大纲逐标题撰写综述正文

    Args:
        outline: 综述大纲文本（包含标题和对应论文分配）
        reference_papers: 所有参考文献列表（用于了解全文背景）
        keyword: 关键词
        citation_papers: 引用文献列表（用于文中引用），默认为None则使用reference_papers

    Returns:
        完整的综述文本
    """
    print(f"\n正在基于大纲撰写综述正文...")
    print(f"  参考文献总数: {len(reference_papers)}")
    print(f"  引用文献总数: {len(citation_papers) if citation_papers else len(reference_papers)}")

    # 如果citation_papers未提供，使用reference_papers
    if citation_papers is None:
        citation_papers = reference_papers

    try:
        # 解析大纲结构
        from outline_generator import parse_outline_structure
        sections = parse_outline_structure(outline)

        if not sections:
            return "解析大纲失败，无法生成综述。"

        # 初始化完成的综述内容
        completed_sections = []

        # 按章节分组：将二级标题和其三级子标题组合在一起
        chapter_groups = []
        current_chapter = None

        for section in sections:
            section_title = section['title']
            section_level = section.get('level', 2)

            # 跳过一级标题（总标题）
            if section_level == 1:
                total_title=section_title
                continue

            # 摘要单独处理
            if section_title.lower() in ['摘要', 'abstract', 'summary']:
                abstract_section = section
                continue

            # 关键词单独处理
            if section_title.lower() in ['关键词', 'keywords', 'keyword']:
                keywords_section = section
                continue

            # 二级标题：开始新章节
            if section_level == 2:
                if current_chapter:
                    chapter_groups.append(current_chapter)
                current_chapter = {
                    'title': section_title,
                    'papers': section.get('papers', []),
                    'word_count': section.get('word_count'),
                    'subsections': []
                }
            # 三级标题：添加到当前章节
            elif section_level == 3 and current_chapter:
                current_chapter['subsections'].append({
                    'title': section_title,
                    'papers': section.get('papers', []),
                    'word_count': section.get('word_count')
                })

        # 添加最后一个章节
        if current_chapter:
            chapter_groups.append(current_chapter)
        print(f"  共解析到 {len(sections)} 个原始章节，组织为 {len(chapter_groups)} 个章节组")

        # 逐章节撰写内容
        completed_chapters = []
        # 构建所有参考文献的完整信息（用于背景了解）
        all_reference_content = ""
        for ref_idx, paper in enumerate(reference_papers, 1):
            title = paper.get('title') or '未知标题'
            authors = paper.get('authors') or []
            published = paper.get('published') or '未知'
            venue = paper.get('venue') or ''
            citation_count = paper.get('citation_count')
            summary = paper.get('summary') or '无摘要'

            all_reference_content += f"\n=== 参考文献[{ref_idx}] ===\n"
            all_reference_content += f"标题: {title}\n"
            all_reference_content += f"作者: {', '.join(authors) if authors else '未知'}\n"
            all_reference_content += f"发表时间: {published}\n"
            if venue:
                all_reference_content += f"来源: {venue}\n"
            if citation_count is not None:
                all_reference_content += f"引用数: {citation_count}\n"
            all_reference_content += f"摘要: {summary}\n"
        for i, chapter in enumerate(chapter_groups):
            chapter_title = chapter['title']
            chapter_papers = chapter['papers']
            subsections = chapter.get('subsections', [])
            print(f"  正在撰写章节 [{i+1}/{len(chapter_groups)}]: {chapter_title}")

            # 合并本章节及其子章节的所有论文
            all_paper_indices = chapter_papers.copy()

            # 计算总字数要求
            chapter_word_count = chapter.get('word_count') or 0
            word_requirement = f"字数要求：{chapter_word_count}字" if chapter_word_count > 0 else "字数适当控制"

            # 获取该章节分配的引用文献（用于引用）
            citation_papers_for_chapter = []
            for paper_idx in all_paper_indices:  # paper_idx是全局1-based序号
                if 1 <= paper_idx <= len(citation_papers):  # 1-based检查
                    paper = citation_papers[paper_idx - 1]  # 转换为0-based访问
                    citation_papers_for_chapter.append({
                        'global_idx': paper_idx,
                        'paper': paper
                    })
            # 构建被分配引用文献的详细信息
            cited_paper_content = ""
            for item in citation_papers_for_chapter:
                paper_idx = item['global_idx']
                paper = item['paper']

                title = paper.get('title') or '未知标题'
                authors = paper.get('authors') or []
                published = paper.get('published') or '未知'
                venue = paper.get('venue') or ''
                citation_count = paper.get('citation_count')
                summary = paper.get('summary') or '无摘要'

                cited_paper_content += f"\n=== 引用文献[{paper_idx}] ===\n"  # 使用新序号
                cited_paper_content += f"标题: {title}\n"
                cited_paper_content += f"作者: {', '.join(authors) if authors else '未知'}\n"
                cited_paper_content += f"发表时间: {published}\n"
                if venue:
                    cited_paper_content += f"来源: {venue}\n"
                if citation_count is not None:
                    cited_paper_content += f"引用数: {citation_count}\n"
                cited_paper_content += f"摘要: {summary}\n"
                # 添加全文内容（如果有）
                full_text = paper.get('full_text', {})
                if isinstance(full_text, dict) and full_text.get('content_type') != 'metadata_only' and full_text.get('content'):
                    content = full_text.get('content')
                    content_type = full_text.get('content_type', 'unknown')
                    if content_type == 'latex':
                        cited_paper_content += f"全文内容（LaTeX）: {content[:2000]}...\n"
                    elif content_type == 'xml':
                        cited_paper_content += f"全文内容（XML）: {content[:2000]}...\n"
                    elif content_type == 'pdf_text':
                        cited_paper_content += f"全文内容（PDF）: {content[:2000]}...\n"
                elif paper.get('latex_content'):
                    cited_paper_content += f"全文内容（LaTeX）: {paper['latex_content'][:2000]}...\n"
            # 构建提示词
            allowed_citations = all_paper_indices  # 使用章节的所有论文序号（新序号）
            # 二级章节级别的提示词
            system_prompt = f"""你是一位专业的中文学术综述撰写专家，擅长总结技术，分析趋势，专门负责根据确定的章节题目和分配的论文撰写该章节题目下总述引出的中文综述内容。

严格写作要求（必须严格遵守，否则将重新生成）：
1. 任务定位：
   - 你可以阅读所有{len(reference_papers)}篇参考文献了解该领域的研究背景
   - 你需要根据分配的论文和题目在该标题下，写出总览性全局性的综述内容，目的是为了引出后面三个子标题的内容
   - 尤其要注意所写的内容要和引用的论文一致，不允许自己无根据写作

2. 引用规则（最重要，严格执行）：
   - 本章节只能使用以下新序号进行引用：{allowed_citations}
   - 必须使用[序号]格式，如[5]、[8]、[5,8]、[5,12,15]
   - 绝对禁止使用其他任何序号，只能使用大纲分配的序号
   - 绝对禁止引用未分配给本章节的论文
   - 序号对应关系（必须记住，新序号按发表时间最新在前排列）：
{chr(10).join([f"     [{paper_idx}] = 引用文献列表中序号{paper_idx}的论文" for paper_idx in allowed_citations])}

3. 内容要求：
   - 内容要完整、连贯
   - 使用学术化的语言，确保论述严谨
   - 段落之间不要有空行

4. 输出要求：
   - 直接输出章节的完整内容，不要重复章节标题
   - {word_requirement}

严重警告：如果生成的内容中出现任何不允许的引用序号，整个内容将被拒绝并重新生成。请确保100%遵守上述引用规则！"""
            user_prompt = f"""请根据以下信息撰写完整的章节内容，你所写的内容将放在总标题“{total_title}”的章节标题"{chapter_title}下，你的目的是为了写出一段文字引出后续子小节“{subsections}”的综述内容"

=== 重要说明 ===
- 你可以阅读所有{len(reference_papers)}篇参考文献了解该领域的研究背景
- 但你必须着重分析介绍本章节分配的{len(all_paper_indices)}篇引用文献的内容，并进行总览性全局性的描述，从而引出后文的内容

=== 严格引用规则（必须100%遵守，否则将被拒绝） ===
本章节只能使用以下新序号进行引用：{all_paper_indices}
禁止使用任何其他序号！

=== 序号映射关系（必须记住，新序号按发表时间最新在前排列） ===
{chr(10).join([f"[{paper_idx}] = 引用文献列表中序号{paper_idx}的论文" for paper_idx in allowed_citations])}

=== 所有参考文献（了解背景） ===
（共{len(reference_papers)}篇）
{all_reference_content}

=== 本章节分配的引用文献（着重分析介绍） ===
（共{len(all_paper_indices)}篇）
{cited_paper_content}

要求：
1. 可以参考其他参考文献了解背景，但只能引用本章节分配的论文
2. 只能使用大纲指定的新序号{all_paper_indices}
3. 绝对不能使用其他序号
4. 如果不需要引用，可以不使用引用
5. {word_requirement}
6. 只输出章节内容，不要重复包含标题

请直接输出章节的中文完整正文内容："""
            if "引言" in chapter_title:
                system_prompt = f"""你是一位专业的中文学术综述撰写专家，擅长总结技术，分析趋势，专门负责根据确定的章节题目和分配的论文撰写该章节题目下的中文综述内容。

                严格写作要求（必须严格遵守，否则将重新生成）：
                1. 任务定位：
                   - 你可以阅读所有{len(reference_papers)}篇参考文献了解该领域的研究背景
                   - 重要！！目前你需要书写综述题目为‘{total_title}’的综述正文的引言部分，你应当使用分配的论文对符合该主题的研究背景和意义进行详细描述

                2. 引用规则（最重要，严格执行）：
                   - 本章节只能使用以下新序号进行引用：{allowed_citations}
                   - 必须使用[序号]格式，如[5]、[8]、[5,8]、[5,12,15]
                   - 绝对禁止使用其他任何序号，只能使用大纲分配的序号
                   - 绝对禁止引用未分配给本章节的论文
                   - 序号对应关系（必须记住，新序号按发表时间最新在前排列）：
                {chr(10).join([f"     [{paper_idx}] = 引用文献列表中序号{paper_idx}的论文" for paper_idx in allowed_citations])}

                3. 内容要求：
                   - 内容要完整、连贯
                   - 使用学术化的语言，确保论述严谨
                   - 段落之间不要有空行

                4. 输出要求：
                   - 直接输出章节的完整内容，不要重复章节标题
                   - {word_requirement}

                严重警告：如果生成的内容中出现任何不允许的引用序号，整个内容将被拒绝并重新生成。请确保100%遵守上述引用规则！"""
                user_prompt = f"""请根据以下信息撰写完整的章节内容，你所写的内容将放在标题"{chapter_title}下"

                === 重要说明 ===
                - 你可以阅读所有{len(reference_papers)}篇参考文献了解该领域的研究背景
                - 你必须注重分析该主题的研究背景，研究趋势，研究现状，研究意义，在引言部分写出适合主题的总览性介绍性文字

                === 严格引用规则（必须100%遵守，否则将被拒绝） ===
                本章节只能使用以下新序号进行引用：{all_paper_indices}
                禁止使用任何其他序号！

                === 序号映射关系（必须记住，新序号按发表时间最新在前排列） ===
                {chr(10).join([f"[{paper_idx}] = 引用文献列表中序号{paper_idx}的论文" for paper_idx in allowed_citations])}

                === 所有参考文献（了解背景） ===
                （共{len(reference_papers)}篇）
                {all_reference_content}

                === 本章节分配的引用文献（引用介绍） ===
                （共{len(all_paper_indices)}篇）
                {cited_paper_content}

                要求：
                1. 可以参考其他参考文献了解背景，但只能引用本章节分配的论文
                2. 只能使用大纲指定的新序号{all_paper_indices}
                3. 绝对不能使用其他序号
                4. 如果不需要引用，可以不使用引用
                5. {word_requirement}
                6. 只输出章节内容，不要重复包含标题

                请直接输出章节的中文完整正文内容："""
            # 检查是否是需要上下文的章节
            previous_content = ""
            if "当前研究趋势与热点" in chapter_title:
                # 为研究趋势和未来展望提供之前的所有内容作为上下文
                if completed_sections:
                    previous_content = "\n\n".join(completed_chapters)
                context_part = f"\n\n前面的综述内容（作为上下文参考）：{previous_content}" if previous_content else ""
                system_prompt = f"""你是一位专业的中文学术综述撰写专家，擅长总结技术，分析趋势，专门负责根据确定的章节题目和分配的论文撰写当前研究趋势和热点的中文综述内容，无需分析技术细节。

                严格写作要求（必须严格遵守，否则将重新生成）：
                1. 任务定位：
                   - 你可以阅读所有{len(reference_papers)}篇参考文献了解该领域的研究背景
                   - 重要！！目前你需要书写综述题目为‘{total_title}’的综述正文的研究趋势总结分析部分，你应当使用分配的论文和前文中已经写好的综述正文对符合该主题的研究趋势进行详细分析,无需介绍技术细节

                2. 引用规则（最重要，严格执行）：
                   - 本章节只能使用以下新序号进行引用：{allowed_citations}
                   - 必须使用[序号]格式，如[5]、[8]、[5,8]、[5,12,15]
                   - 绝对禁止使用其他任何序号，只能使用大纲分配的序号
                   - 绝对禁止引用未分配给本章节的论文
                   - 序号对应关系（必须记住，新序号按发表时间最新在前排列）：
                {chr(10).join([f"     [{paper_idx}] = 引用文献列表中序号{paper_idx}的论文" for paper_idx in allowed_citations])}

                3. 内容要求：
                   - 内容要完整、连贯
                   - 使用学术化的语言，确保论述严谨
                   - 段落之间不要有空行

                4. 输出要求：
                   - 直接输出章节的完整内容，不要重复章节标题
                   - {word_requirement}

                严重警告：如果生成的内容中出现任何不允许的引用序号，整个内容将被拒绝并重新生成。请确保100%遵守上述引用规则！"""
                user_prompt = f"""请根据以下信息撰写完整的章节内容，你所写的内容将放在标题"{chapter_title}下"

                === 重要说明 ===
                - 你可以阅读所有{len(reference_papers)}篇参考文献了解该领域的研究背景
                - 你必须总结上文中已写好的内容，结合分配的到的论文进行当前研究趋势和热点的分析，不应当详细分析技术路线！

                === 严格引用规则（必须100%遵守，否则将被拒绝） ===
                本章节只能使用以下新序号进行引用：{all_paper_indices}
                禁止使用任何其他序号！

                === 序号映射关系（必须记住，新序号按发表时间最新在前排列） ===
                {chr(10).join([f"[{paper_idx}] = 引用文献列表中序号{paper_idx}的论文" for paper_idx in allowed_citations])}

                === 所有参考文献（了解背景） ===
                （共{len(reference_papers)}篇）
                {all_reference_content}{context_part}

                === 本章节分配的引用文献（引用，无需详细介绍技术内容） ===
                （共{len(all_paper_indices)}篇）
                {cited_paper_content}

                要求：
                1. 可以参考其他参考文献了解背景，但只能引用本章节分配的论文，但无需分析技术细节
                2. 只能使用大纲指定的新序号{all_paper_indices}
                3. 绝对不能使用其他序号
                4. 如果不需要引用，可以不使用引用
                5. {word_requirement}
                6. 只输出章节内容，不要重复包含标题

                请直接输出章节的中文完整正文内容："""
            if "未来发展方向与挑战" in chapter_title:
                # 为研究趋势和未来展望提供之前的所有内容作为上下文
                if completed_sections:
                    previous_content = "\n\n".join(completed_chapters)
                context_part = f"\n\n前面的综述内容（作为上下文参考）：{previous_content}" if previous_content else ""
                system_prompt = f"""你是一位专业的中文学术综述撰写专家，擅长总结技术，分析趋势，专门负责根据确定的章节题目和分配的论文撰写未来发展方向与挑战的中文综述内容。

                严格写作要求（必须严格遵守，否则将重新生成）：
                1. 任务定位：
                   - 你可以阅读所有{len(reference_papers)}篇参考文献了解该领域的研究背景
                   - 重要！！目前你需要书写综述题目为‘{total_title}’的综述正文的未来发展方向和挑战部分，你应当使用分配的论文和前文中已经写好的综述正文对该主题的未来发展进行详细分析，但无需分析技术细节

                2. 引用规则（最重要，严格执行）：
                   - 本章节只能使用以下新序号进行引用：{allowed_citations}
                   - 必须使用[序号]格式，如[5]、[8]、[5,8]、[5,12,15]
                   - 绝对禁止使用其他任何序号，只能使用大纲分配的序号
                   - 绝对禁止引用未分配给本章节的论文
                   - 序号对应关系（必须记住，新序号按发表时间最新在前排列）：
                {chr(10).join([f"     [{paper_idx}] = 引用文献列表中序号{paper_idx}的论文" for paper_idx in allowed_citations])}

                3. 内容要求：
                   - 内容要完整、连贯
                   - 使用学术化的语言，确保论述严谨
                   - 段落之间不要有空行

                4. 输出要求：
                   - 直接输出章节的完整内容，不要重复章节标题
                   - {word_requirement}

                严重警告：如果生成的内容中出现任何不允许的引用序号，整个内容将被拒绝并重新生成。请确保100%遵守上述引用规则！"""
                user_prompt = f"""请根据以下信息撰写完整的章节内容，你所写的内容将放在标题"{chapter_title}下"

                === 重要说明 ===
                - 你可以阅读所有{len(reference_papers)}篇参考文献了解该领域的研究背景
                - 你必须总结上文中已写好的内容，结合分配的到的论文进行未来研究方向和发展方向的分析，不应当详细分析技术路线！

                === 严格引用规则（必须100%遵守，否则将被拒绝） ===
                本章节只能使用以下新序号进行引用：{all_paper_indices}
                禁止使用任何其他序号！

                === 序号映射关系（必须记住，新序号按发表时间最新在前排列） ===
                {chr(10).join([f"[{paper_idx}] = 引用文献列表中序号{paper_idx}的论文" for paper_idx in allowed_citations])}

                === 所有参考文献（了解背景） ===
                （共{len(reference_papers)}篇）
                {all_reference_content}{context_part}

                === 本章节分配的引用文献（引用，无需详细介绍技术内容） ===
                （共{len(all_paper_indices)}篇）
                {cited_paper_content}

                要求：
                1. 可以参考其他参考文献了解背景，但只能引用本章节分配的论文，无需分析技术细节
                2. 只能使用大纲指定的新序号{all_paper_indices}
                3. 绝对不能使用其他序号
                4. 如果不需要引用，可以不使用引用
                5. {word_requirement}
                6. 只输出章节内容，不要重复包含标题

                请直接输出章节的中文完整正文内容："""
            # 调用大模型撰写章节内容
            max_retries = 3  # 最多重试3次
            chapter_content = None
            for attempt in range(max_retries):
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
                    temperature=0.5,
                    timeout=default_timeout
                )

                # 计算并记录Token使用
                input_tokens = count_tokens(system_prompt) + count_tokens(user_prompt)
                if response and response.choices:
                    output_text = response.choices[0].message.content or ""
                    output_tokens = count_tokens(output_text)
                else:
                    output_tokens = 0
                record_api_call(input_tokens, output_tokens, "review", f"撰写章节: {chapter_title}")

                if response and response.choices and len(response.choices) > 0:
                    candidate_content = response.choices[0].message.content.strip()

                    # 验证引用序号是否符合要求
                    validation_passed, invalid_citations = validate_citation_compliance_detailed(candidate_content, all_paper_indices)

                    if candidate_content and validation_passed:
                        chapter_content = candidate_content
                        print(f"    [OK] 完成章节: {chapter_title} (尝试 {attempt + 1})")
                        print(f"\n=== 生成的章节内容 ===")
                        print(f"章节标题: {chapter_title}")
                        print(f"内容长度: {len(candidate_content)} 字符")
                        print(f"内容预览: {candidate_content[:200]}..." if len(candidate_content) > 200 else f"完整内容: {candidate_content}")
                        print(f"=== 章节内容结束 ===\n")
                        break
                else:
                    print(f"    [ERROR] API调用失败 (尝试 {attempt + 1})")
                    if attempt == max_retries - 1:
                        break

            # 如果所有尝试都失败，使用备用内容
            if not chapter_content:
                chapter_content = f"[{chapter_title}内容生成失败，请手动完善]"
                print(f"    [ERROR] 多次尝试后仍失败，使用备用内容")

            completed_chapters.append({
                'title': chapter_title,
                'content': chapter_content
            })
            #开始二级标题下三级标题内容生成 subsections
            for i, subsection in enumerate(subsections):
                sub_title = subsection['title']
                sub_papers = subsection['papers']
                print(f"  正在撰写子章节 [{i + 1}/{len(subsections)}]: {sub_title}")

                # 计算总字数要求
                sub_word_count = subsection.get('word_count') or 0
                word_requirement = f"字数要求：{sub_word_count}字" if sub_word_count > 0 else "字数适当控制"
                # 获取该章节分配的引用文献（用于引用）
                citation_papers_for_sub = []
                for paper_idx in sub_papers:  # paper_idx是全局1-based序号
                    if 1 <= paper_idx <= len(citation_papers):  # 1-based检查
                        paper = citation_papers[paper_idx - 1]  # 转换为0-based访问
                        citation_papers_for_sub.append({
                            'global_idx': paper_idx,
                            'paper': paper
                        })
                # 构建被分配引用文献的详细信息
                cited_sub_content = ""
                for item in citation_papers_for_sub:
                    paper_idx = item['global_idx']
                    paper = item['paper']
                    title = paper.get('title') or '未知标题'
                    authors = paper.get('authors') or []
                    published = paper.get('published') or '未知'
                    venue = paper.get('venue') or ''
                    citation_count = paper.get('citation_count')
                    summary = paper.get('summary') or '无摘要'

                    cited_sub_content += f"\n=== 引用文献[{paper_idx}] ===\n"  # 使用新序号
                    cited_sub_content += f"标题: {title}\n"
                    cited_sub_content += f"作者: {', '.join(authors) if authors else '未知'}\n"
                    cited_sub_content += f"发表时间: {published}\n"
                    if venue:
                        cited_sub_content += f"来源: {venue}\n"
                    if citation_count is not None:
                        cited_sub_content += f"引用数: {citation_count}\n"
                    cited_sub_content += f"摘要: {summary}\n"
                    # 添加全文内容（如果有）
                    full_text = paper.get('full_text', {})
                    if isinstance(full_text, dict) and full_text.get(
                            'content_type') != 'metadata_only' and full_text.get('content'):
                        content = full_text.get('content')
                        content_type = full_text.get('content_type', 'unknown')
                        if content_type == 'latex':
                            cited_sub_content += f"全文内容（LaTeX）: {content[:2000]}...\n"
                        elif content_type == 'xml':
                            cited_sub_content += f"全文内容（XML）: {content[:2000]}...\n"
                        elif content_type == 'pdf_text':
                            cited_sub_content += f"全文内容（PDF）: {content[:2000]}...\n"
                    elif paper.get('latex_content'):
                        cited_sub_content += f"全文内容（LaTeX）: {paper['latex_content'][:2000]}...\n"
                allowed_citations_sub = sub_papers # 使用章节的所有论文序号（新序号）
                # 二级章节级别的提示词
                system_prompt = f"""你是一位专业的中文学术综述撰写专家，擅长总结技术，分析趋势，专门负责根据确定的章节题目和分配的论文撰写该章节题目下的中文综述内容。

                严格写作要求（必须严格遵守，否则将重新生成）：
                1. 任务定位：
                   - 你可以阅读所有{len(reference_papers)}篇参考文献了解该领域的研究背景
                   - 重要！！除了引言，研究趋势和未来发展这三个章节外，在其他章节你必须着重分析介绍本章节分配的{len(allowed_citations_sub)}篇引用文献的技术内容
                   - 技术路线有相似性的论文应该放在一起描述
                   - 尤其要注意所写的内容要和引用的论文一致，不允许自己无根据写作

                2. 引用规则（最重要，严格执行）：
                   - 本章节只能使用以下新序号进行引用：{allowed_citations_sub}
                   - 必须使用[序号]格式，如[5]、[8]、[5,8]、[5,12,15]
                   - 绝对禁止使用其他任何序号，只能使用大纲分配的序号
                   - 绝对禁止引用未分配给本章节的论文
                   - 序号对应关系（必须记住，新序号按发表时间最新在前排列）：
                {chr(10).join([f"     [{paper_idx}] = 引用文献列表中序号{paper_idx}的论文" for paper_idx in allowed_citations_sub])}

                3. 内容要求：
                   - 内容要完整、连贯
                   - 使用学术化的语言，确保论述严谨
                   - 段落之间不要有空行
                   - 要着重分析分配给本章节的引用文献

                4. 输出要求：
                   - 直接输出章节的完整内容，不要重复章节标题
                   - {word_requirement}

                严重警告：如果生成的内容中出现任何不允许的引用序号，整个内容将被拒绝并重新生成。请确保100%遵守上述引用规则！"""
                user_prompt = f"""请根据以下信息撰写完整的章节内容，你所写的内容将放在总标题“{total_title}”的章节标题"{chapter_title}的次级标题“{sub_title}”下"

                === 重要说明 ===
                - 你可以阅读所有{len(reference_papers)}篇参考文献了解该领域的研究背景
                - 但你必须着重分析介绍本章节分配的{len(allowed_citations_sub)}篇引用文献的技术内容

                === 严格引用规则（必须100%遵守，否则将被拒绝） ===
                本章节只能使用以下新序号进行引用：{allowed_citations_sub}
                禁止使用任何其他序号！

                === 序号映射关系（必须记住，新序号按发表时间最新在前排列） ===
                {chr(10).join([f"[{paper_idx}] = 引用文献列表中序号{paper_idx}的论文" for paper_idx in allowed_citations_sub])}

                === 所有参考文献（了解背景） ===
                （共{len(reference_papers)}篇）
                {all_reference_content}

                === 本章节分配的引用文献（着重分析介绍） ===
                （共{len(allowed_citations_sub)}篇）
                {cited_sub_content}

                要求：
                1. 可以参考其他参考文献了解背景，但只能引用本章节分配的论文
                2. 只能使用大纲指定的新序号{allowed_citations_sub}
                3. 绝对不能使用其他序号
                4. 如果不需要引用，可以不使用引用
                5. {word_requirement}
                6. 只输出章节内容，不要重复包含标题
                7. 如果需要分析技术，相似技术的论文应该写在一起进行对比分析，引言，研究趋势和未来展望章节不需要详细分析技术内容

                请直接输出章节的中文完整正文内容："""
                # 调用大模型撰写章节内容
                max_retries = 3  # 最多重试3次
                sub_content = None
                for attempt in range(max_retries):
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
                        temperature=0.5,
                        timeout=default_timeout
                    )

                    # 计算并记录Token使用
                    input_tokens = count_tokens(system_prompt) + count_tokens(user_prompt)
                    if response and response.choices:
                        output_text = response.choices[0].message.content or ""
                        output_tokens = count_tokens(output_text)
                    else:
                        output_tokens = 0
                    record_api_call(input_tokens, output_tokens, "review", f"撰写章节: {chapter_title}")

                    if response and response.choices and len(response.choices) > 0:
                        candidate_content = response.choices[0].message.content.strip()

                        # 验证引用序号是否符合要求
                        validation_passed, invalid_citations = validate_citation_compliance_detailed(candidate_content,
                                                                                                     all_paper_indices)

                        if candidate_content and validation_passed:
                            sub_content = candidate_content
                            print(f"    [OK] 完成章节: {chapter_title} (尝试 {attempt + 1})")
                            print(f"\n=== 生成的章节内容 ===")
                            print(f"章节标题: {chapter_title}")
                            print(f"内容长度: {len(candidate_content)} 字符")
                            print(f"内容预览: {candidate_content[:200]}..." if len(
                                candidate_content) > 200 else f"完整内容: {candidate_content}")
                            print(f"=== 章节内容结束 ===\n")
                            break
                    else:
                        print(f"    [ERROR] API调用失败 (尝试 {attempt + 1})")
                        if attempt == max_retries - 1:
                            break
                completed_chapters.append({
                    'sub_title': sub_title,
                    'content': sub_content
                })

        # 生成摘要（基于已完成的其他所有内容）
        if abstract_section:
            print("\n正在生成摘要（基于其他所有章节内容）...")
            # 提取所有已完成章节的内容用于生成摘要
            # chapter_titles = [chap['title'] for chap in completed_chapters]
            chapter_titles = [
                chap['title'] if 'title' in chap else chap['sub_title']
                for chap in completed_chapters
            ]
            chapter_contents = [chap['content'] for chap in completed_chapters]
            abstract_content = generate_abstract(chapter_titles, chapter_contents, abstract_section, reference_papers)
            # 将摘要插入到引言之前的位置
            abstract_title = abstract_section['title']
            # 找到引言的位置
            intro_index = -1
            for i, chap in enumerate(completed_chapters):
                title = chap.get('title') or chap.get('sub_title') or ''
                if title.lower() in ['引言', 'introduction', 'intro']:
                    intro_index = i
                    break

            if intro_index >= 0:
                # 插入到引言之前
                completed_chapters.insert(intro_index, {
                    'title': abstract_title,
                    'content': abstract_content
                })
            else:
                # 如果没找到引言，插入到开头
                completed_chapters.insert(0, {
                    'title': abstract_title,
                    'content': abstract_content
                })
        # 生成关键词（基于已完成的其他所有内容）
        if keywords_section:
            print("\n正在生成关键词（基于其他所有章节内容）...")
            # 提取所有已完成章节的内容用于生成摘要
            chapter_titles = [
                chap['title'] if 'title' in chap else chap['sub_title']
                for chap in completed_chapters
            ]
            chapter_contents = [chap['content'] for chap in completed_chapters]
            keywords_content = generate_keywords(chapter_titles, chapter_contents, keywords_section, reference_papers)

            # 将关键词插入到引言之前的位置
            keywords_title = keywords_section['title']

            # 找到引言的位置
            intro_index = -1
            for i, chap in enumerate(completed_chapters):
                title = chap.get('title') or chap.get('sub_title') or ''
                if title.lower() in ['引言', 'introduction', 'intro']:
                    intro_index = i
                    break

            if intro_index >= 0:
                # 插入到引言之前
                completed_chapters.insert(intro_index, {
                    'title': keywords_title,
                    'content': keywords_content
                })
            else:
                # 如果没找到引言，插入到开头
                completed_chapters.insert(0, {
                    'title': keywords_title,
                    'content': keywords_content
                })
        # 组合最终的综述：标题 + 内容
        final_review_parts = []
        for chap in completed_chapters:
            if 'title' in chap:
                final_review_parts.append(f"## {chap['title']}\n{chap.get('content', '')}")
            elif 'sub_title' in chap:
                final_review_parts.append(f"### {chap['sub_title']}\n{chap.get('content', '')}")

        final_review = "\n\n".join(final_review_parts)

        print("  [OK] 综述正文撰写完成")
        print(f"  共完成 {len(completed_chapters)} 个章节")

        # 打印完整的综述内容
        print(f"\n{'='*80}")
        print("生成的完整综述正文内容：")
        print(f"{'='*80}")
        print(final_review)
        print(f"{'='*80}")
        print(f"综述总长度: {len(final_review)} 字符")
        print(f"包含章节数: {len(completed_chapters)}")

        return final_review

    except Exception as e:
        error_msg = f"基于大纲撰写综述时出错: {e}"
        print(error_msg)
        return error_msg
