"""
学术综述幻觉检查模块

此模块负责：
1. 检测综述正文中的幻觉内容（与参考文献数据不符）
2. 修正或删除幻觉语句
3. 确保引用与文献数据一致
"""

from openai import OpenAI
import re
from typing import Dict, List, Tuple, Optional
from datetime import datetime

# Token计数
from token_counter import record_api_call, count_tokens


# 初始化OpenAI客户端（从配置中读取）
from config import get_openai_config, get_quality_config
openai_config = get_openai_config()
quality_config = get_quality_config()
# 幻觉检测涉及大量文本，增加超时时间
default_timeout = max(openai_config['timeout'], 300)
client = OpenAI(
    base_url=openai_config['base_url'],
    api_key=openai_config['api_key'],
    timeout=default_timeout
)


def extract_citations_from_text(text: str) -> List[Tuple[str, List[int]]]:
    """
    从正文中提取所有引用及其上下文
    
    Args:
        text: 正文本
    
    Returns:
        [(引用上下文, [文献序号列表]), ...]
    """
    # 匹配 [1], [1,2,3], [1-3] 等格式
    citation_pattern = r'([^\]]*?)(\[(\d+(?:,\s*\d+)*(?:\s*-\s*\d+)*)\])'
    
    matches = []
    for match in re.finditer(citation_pattern, text):
        context = match.group(1).strip()
        citation = match.group(2)
        
        # 解析文献序号
        numbers = []
        for part in re.split(r'[,-\s]+', citation.strip('[]')):
            part = part.strip()
            if part.isdigit():
                numbers.append(int(part))
        
        if numbers:
            matches.append((context, numbers))
    
    return matches


def extract_paper_info_for_citation(paper: Dict, paper_idx: int) -> str:
    """
    提取论文的关键信息用于幻觉检测
    
    Args:
        paper: 论文信息字典
        paper_idx: 文献序号
    
    Returns:
        格式化的论文信息字符串
    """
    info = f"[文献{paper_idx}] "
    info += f"标题: {paper.get('title', '未知')}\n"
    info += f"年份: {paper.get('published', '未知')[:4]}\n"
    info += f"作者: {', '.join(paper.get('authors', [])[:3])}"
    if len(paper.get('authors', [])) > 3:
        info += " 等"
    info += "\n"
    info += f"引用数: {paper.get('citation_count', '未知')}\n"
    
    # 摘要摘要用于对比
    summary = paper.get('summary', '')
    if summary:
        summary_short = summary[:500] + "..." if len(summary) > 500 else summary
        info += f"摘要: {summary_short}\n"
    
    return info


def check_hallucinations_in_chapter(chapter_title: str, chapter_content: str, 
                                     cited_papers: List[Dict], 
                                     paper_indices: List[int]) -> Dict:
    """
    检测单个章节中的幻觉内容
    
    Args:
        chapter_title: 章节标题
        chapter_content: 章节正文
        cited_papers: 所有参考文献列表
        paper_indices: 本章节引用的文献序号列表（1-based）
    
    Returns:
        检测结果字典
    """
    if not chapter_content or not cited_papers:
        return {
            'has_hallucination': False,
            'original_content': chapter_content,
            'corrected_content': chapter_content,
            'hallucinations': [],
            'suggestions': []
        }
    
    # 构建论文信息摘要
    papers_info = ""
    for idx in paper_indices:
        if 1 <= idx <= len(cited_papers):
            papers_info += extract_paper_info_for_citation(cited_papers[idx - 1], idx)
            papers_info += "-" * 60 + "\n"
    
    # 提取引用上下文
    citations = extract_citations_from_text(chapter_content)
    citations_info = ""
    for i, (context, numbers) in enumerate(citations, 1):
        citations_info += f"[引用{i}] 上下文: \"{context}\" 引用文献: {numbers}\n"
    
    system_prompt = """你是一位严谨的学术审稿专家，专门检测学术综述中的幻觉内容。

幻觉定义：
- 文中描述与文献实际内容严重不符
- 编造文献中不存在的信息（如错误年份、错误作者、错误方法等）
- 夸大学院或扭曲论文的实际贡献
- 将某论文的发现错误归因于另一篇论文

检测任务：
1. 仔细对比文中每个引用句子的上下文与对应文献的实际信息
2. 识别任何与文献数据不符的陈述
3. 对于每处可能的幻觉，提供：
   - 具体问题描述
   - 原始语句
   - 问题严重程度（高/中/低）

重要：
- 只标记真正与文献不符的内容
- 不要误判合理的研究综述和推断
- 区分"文献未提及"和"文献明确否定"的情况"""

    user_prompt = f"""请检测以下学术综述章节中的幻觉内容。

【章节标题】
{chapter_title}

【章节正文】
{chapter_content}

【引用上下文分析】
{citations_info if citations_info else "正文中有引用标记，但未能提取具体上下文"}

【参考文献信息】
{papers_info}

请分析正文中的每个引用陈述是否与参考文献信息一致。

检测重点：
1. 年份是否与文献发表时间一致（如文献2020年发表，文中说"近年来"可能合理，但说"在2018年"则可能是幻觉）
2. 作者姓名是否与文献一致
3. 方法描述是否在文献摘要/内容中有提及
4. 研究结论是否有文献支持

请输出以下格式的检测结果：

## 幻觉检测报告

### 检测结果
- 总引用数: {len(citations)}
- 疑似幻觉数: X

### 详细分析
[逐条分析每处引用]

### 结论
是否需要修正: 是/否

如果需要修正，请提供修正后的完整正文。"""

    try:
        response = client.chat.completions.create(
            model=openai_config['model'],
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt}
            ],
            stream=False,
            temperature=0.3,
            timeout=default_timeout
        )

        # 计算并记录Token使用
        input_tokens = count_tokens(system_prompt) + count_tokens(user_prompt)
        if response and response.choices:
            output_text = response.choices[0].message.content or ""
            output_tokens = count_tokens(output_text)
        else:
            output_tokens = 0
        record_api_call(input_tokens, output_tokens, "hallucination", "检测幻觉")
        
        if response and response.choices and len(response.choices) > 0:
            analysis = response.choices[0].message.content.strip()
            return {
                'has_hallucination': True,
                'original_content': chapter_content,
                'analysis': analysis,
                'hallucinations': [],  # 详细幻觉列表由AI生成
                'suggestions': []
            }
        
    except Exception as e:
        print(f"  幻觉检测出错: {e}")
    
    return {
        'has_hallucination': False,
        'original_content': chapter_content,
        'corrected_content': chapter_content,
        'hallucinations': [],
        'suggestions': []
    }


def correct_hallucinations(chapter_title: str, chapter_content: str, 
                           cited_papers: List[Dict], 
                           paper_indices: List[int]) -> str:
    """
    修正章节中的幻觉内容
    
    Args:
        chapter_title: 章节标题
        chapter_content: 章节正文
        cited_papers: 所有参考文献列表
        paper_indices: 本章节引用的文献序号列表
    
    Returns:
        修正后的正文内容
    """
    if not chapter_content or not cited_papers:
        return chapter_content
    
    # 构建论文信息摘要
    papers_info = ""
    for idx in paper_indices:
        if 1 <= idx <= len(cited_papers):
            papers_info += extract_paper_info_for_citation(cited_papers[idx - 1], idx)
            papers_info += "-" * 60 + "\n"
    
    system_prompt = """你是一位专业的学术编辑，负责修正学术综述中的幻觉内容。

修正原则：
1. 删除与文献不符的幻觉语句
2. 删除对应的引用标记
3. 添加适当的衔接语句使上下文流畅
4. 保留有文献支持的有效信息
5. 保持学术语言的规范性

修正策略：
- 如果某句话是幻觉：删除整句话，添加衔接词
- 如果某句话部分有效：修正错误部分，保留有效部分
- 如果引用标记是幻觉：删除引用标记，保留上下文"""

    user_prompt = f"""请修正以下学术综述章节中的幻觉内容。

【章节标题】
{chapter_title}

【章节正文】
{chapter_content}

【参考文献信息】
{papers_info}

请执行以下任务：
1. 逐句检查每个引用陈述是否与参考文献信息一致
2. 删除与文献不符的幻觉语句及其引用标记
3. 删除无法验证的幻觉引用标记
4. 添加适当的衔接语句使上下文流畅
5. 保留有文献支持的有效信息

修正格式要求：
- 输出修正后的完整正文
- 不要添加任何解释或说明
- 不要使用markdown格式
- 直接输出正文内容

修正后的正文："""

    try:
        response = client.chat.completions.create(
            model=openai_config['model'],
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt}
            ],
            stream=False,
            temperature=0.3,
            timeout=default_timeout
        )

        # 计算并记录Token使用
        input_tokens = count_tokens(system_prompt) + count_tokens(user_prompt)
        if response and response.choices:
            output_text = response.choices[0].message.content or ""
            output_tokens = count_tokens(output_text)
        else:
            output_tokens = 0
        record_api_call(input_tokens, output_tokens, "hallucination", "修正幻觉")
        
        if response and response.choices and len(response.choices) > 0:
            corrected = response.choices[0].message.content.strip()
            if corrected:
                print(f"    ✓ 已完成章节幻觉修正")
                return corrected
        
    except Exception as e:
        print(f"    幻觉修正出错: {e}")
    
    return chapter_content  # 出错时返回原文


def check_and_fix_hallucinations(review: str, papers: List[Dict], 
                                  cited_paper_indices: List[int]) -> Tuple[str, Dict]:
    """
    对整篇综述进行幻觉检测和修正
    
    Args:
        review: 综述正文
        papers: 所有参考文献
        cited_paper_indices: 被引用的文献序号列表（1-based）
    
    Returns:
        (修正后的综述, 检测报告)
    """
    print(f"\n正在进行幻觉检测...")
    
    # 获取被引用的论文
    cited_papers = []
    for idx in cited_paper_indices:
        if 1 <= idx <= len(papers):
            cited_papers.append(papers[idx - 1])
    
    if not cited_papers:
        print("  未找到被引用的论文，跳过幻觉检测")
        return review, {'status': 'skipped', 'reason': 'no_cited_papers'}
    
    print(f"  正在检测 {len(cited_papers)} 篇被引用文献的一致性...")
    
    # 解析综述结构
    from outline_generator import parse_outline_structure
    sections = parse_outline_structure(review)
    
    if not sections:
        print("  解析综述结构失败，跳过幻觉检测")
        return review, {'status': 'skipped', 'reason': 'parse_failed'}
    
    # 筛选正文章节（排除摘要、关键词等）
    content_sections = []
    for section in sections:
        title = section.get('title', '').lower()
        if title not in ['摘要', '关键词', 'abstract', 'keywords']:
            content_sections.append(section)
    
    if not content_sections:
        print("  未找到正文章节，跳过幻觉检测")
        return review, {'status': 'skipped', 'reason': 'no_content_sections'}
    
    # 按章节进行幻觉检测和修正
    corrected_sections = []
    report = {
        'status': 'completed',
        'total_sections': len(content_sections),
        'sections_with_hallucinations': 0,
        'corrections': []
    }
    
    for i, section in enumerate(content_sections, 1):
        title = section.get('title', '未知标题')
        content = section.get('content', '') or ''
        paper_indices = section.get('papers', [])
        
        # 如果没有分配论文，尝试从正文中提取
        if not paper_indices and content:
            cited_in_content = extract_citations_from_text(content)
            for _, nums in cited_in_content:
                paper_indices.extend(nums)
            paper_indices = list(set(paper_indices))
        
        if not paper_indices or not content:
            # 无引用或无内容，直接保留
            corrected_sections.append(f"## {title}\n{content}")
            continue
        
        print(f"  检测章节 [{i}/{len(content_sections)}]: {title}")
        
        # 检测幻觉
        check_result = check_hallucinations_in_chapter(
            title, content, cited_papers, paper_indices
        )
        
        if check_result.get('has_hallucination'):
            # 需要修正
            print(f"    发现疑似幻觉，进行修正...")
            corrected = correct_hallucinations(
                title, content, cited_papers, paper_indices
            )
            corrected_sections.append(f"## {title}\n{corrected}")
            
            report['sections_with_hallucinations'] += 1
            report['corrections'].append({
                'section': title,
                'analysis': check_result.get('analysis', '')
            })
        else:
            # 无幻觉，保留原文
            corrected_sections.append(f"## {title}\n{content}")
    
    # 重组综述
    corrected_review = "\n\n".join(corrected_sections)
    
    # 统计修正效果
    original_length = len(review)
    corrected_length = len(corrected_review)
    
    report['original_length'] = original_length
    report['corrected_length'] = corrected_length
    report['length_change'] = corrected_length - original_length
    report['hallucination_rate'] = report['sections_with_hallucinations'] / report['total_sections'] if report['total_sections'] > 0 else 0
    
    print(f"\n幻觉检测完成:")
    print(f"  - 检测章节数: {report['total_sections']}")
    print(f"  - 发现幻觉章节: {report['sections_with_hallucinations']}")
    print(f"  - 内容变化: {report['length_change']:+d} 字符")
    
    return corrected_review, report


def lightweight_hallucination_check(review: str, papers: List[Dict]) -> Tuple[str, int]:
    """
    轻量级幻觉检测 - 只检测明显的幻觉
    
    Args:
        review: 综述正文
        papers: 参考文献列表
    
    Returns:
        (修正后的综述, 检测到的幻觉数量)
    """
    print(f"\n进行轻量级幻觉检测...")
    
    # 构建文献信息摘要（简化版）
    papers_summary = ""
    for i, paper in enumerate(papers, 1):
        title = paper.get('title', '未知')[:100]
        year = paper.get('published', '未知')[:4]
        authors = paper.get('authors', [])
        first_author = authors[0] if authors else '未知'
        
        papers_summary += f"[{i}] {title} ({year}), {first_author}\n"
    
    system_prompt = """你是一位严谨的学术编辑，负责快速检测综述中的明显幻觉。

检测重点：
1. 与所引用论文摘要完全矛盾的内容
2. 明显的数值错误（引用数、样本数等）
3. 年份错误（文中提到的年份与实际发表年份不符）
4. 作者错误（引用作者与文献不符）


输出要求：
- 直接输出修正后的综述正文
- 删除或修正明显的幻觉内容
- 保持其他内容不变
- 不要添加解释"""

    user_prompt = f"""请快速检测并修正以下综述中的明显幻觉。

【参考文献信息】
{papers_summary}

【综述正文】
{review}

请快速检查并修正明显的幻觉：
1. 检查综述正文与参考文献完全不符的幻觉内容
1. 删除无法验证的幻觉引用
2. 检查文中引用的年份是否与参考文献年份一致
3. 检查作者姓名是否正确


直接输出修正后的正文，不要添加任何说明。"""

    try:
        response = client.chat.completions.create(
            model=openai_config['model'],
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt}
            ],
            stream=False,
            temperature=0.2,
            timeout=60
        )

        # 计算并记录Token使用
        input_tokens = count_tokens(system_prompt) + count_tokens(user_prompt)
        if response and response.choices:
            output_text = response.choices[0].message.content or ""
            output_tokens = count_tokens(output_text)
        else:
            output_tokens = 0
        record_api_call(input_tokens, output_tokens, "hallucination", "轻量级幻觉检测")
        
        if response and response.choices and len(response.choices) > 0:
            corrected = response.choices[0].message.content.strip()
            if corrected and corrected != review:
                # 统计修正比例
                changes = sum(1 for a, b in zip(review, corrected) if a != b)
                hallucination_count = min(changes // 10, len(papers))  # 估算幻觉数量
                print(f"  ✓ 检测到并修正了 {hallucination_count} 处潜在幻觉")
                return corrected, hallucination_count
        
    except Exception as e:
        print(f"  轻量级幻觉检测出错: {e}")
    
    return review, 0


def check_citation_consistency(review: str, papers: List[Dict], 
                                cited_indices: List[int]) -> Dict:
    """
    检查引用的一致性 - 确保引用的文献都在参考文献列表中
    
    Args:
        review: 综述正文
        papers: 参考文献列表
        cited_indices: 被引用的文献序号
    
    Returns:
        检查报告
    """
    report = {
        'total_citations': 0,
        'valid_citations': 0,
        'invalid_citations': [],
        'unlisted_citations': []
    }
    
    # 提取所有引用序号
    all_cited = set()
    for match in re.finditer(r'\[(\d+(?:,\s*\d+)*)\]', review):
        nums = re.findall(r'\d+', match.group(1))
        all_cited.update([int(n) for n in nums])
    
    report['total_citations'] = len(all_cited)
    
    # 检查是否在引用列表中
    for num in sorted(all_cited):
        if num in cited_indices:
            report['valid_citations'] += 1
        else:
            if 1 <= num <= len(papers):
                report['unlisted_citations'].append(num)
            else:
                report['invalid_citations'].append(num)
    
    return report


if __name__ == "__main__":
    # 测试幻觉检测功能
    print("幻觉检测模块测试")
    print("=" * 60)
    
    # 示例论文数据
    test_papers = [
        {
            'title': 'Attention Is All You Need',
            'authors': ['Ashish Vaswani', 'Noam Shazeer', 'Niki Parmar'],
            'published': '2017-06-12',
            'citation_count': 100000,
            'summary': 'We propose a new network architecture, the Transformer, based solely on attention mechanisms.'
        },
        {
            'title': 'BERT: Pre-training of Deep Bidirectional Transformers',
            'authors': ['Jacob Devlin', 'Ming-Wei Chang', 'Kenton Lee'],
            'published': '2018-10-11',
            'citation_count': 80000,
            'summary': 'We introduce a new language representation model called BERT.'
        }
    ]
    
    test_review = """
## 引言
近年来，Transformer架构在自然语言处理领域取得了突破性进展[1]。Vaswani等人于2017年在Nature杂志上首次提出了Transformer架构[1]，该架构完全基于自注意力机制。BERT模型则是在2019年由Google提出[2]，进一步推动了预训练语言模型的发展。
    """
    
    print("测试综述:")
    print(test_review)
    print("\n测试论文:")
    for i, p in enumerate(test_papers, 1):
        print(f"[{i}] {p['title']} ({p['published'][:4]})")
    
    # 执行轻量级检测
    corrected, count = lightweight_hallucination_check(test_review, test_papers)
    
    print(f"\n检测到幻觉: {count}处")
    print("\n修正后综述:")
    print(corrected)

