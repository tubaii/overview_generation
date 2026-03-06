from paper_search_filter import (
    search_arxiv_papers,
    search_semantic_scholar_papers,
    search_openalex_papers,
    merge_and_deduplicate_papers,
    enrich_papers_with_citations,
    get_paper_latex_content,
    FullTextDownloader,
    filter_papers_two_stage,
    extract_text_from_pdf_url
)
from outline_generator import parse_outline_structure
from outline_generator import (
    generate_review_outline
)

from review_writer import (
    write_review_from_outline,
    write_review_from_outline_deep
)

from format_check import (
    save_review_to_docx
)

from hallucination_check import (
    check_and_fix_hallucinations,
    lightweight_hallucination_check,
    check_citation_consistency
)

from token_counter import (
    reset_token_counter,
    print_token_summary
)

from config import (
    get_search_config,
    get_search_config2,
    get_runtime_config,
    get_path_config,
    get_user_input_config,
    get_fulltext_config,
    get_openai_config,
    print_current_config,
    print_command_line_help
)
from outline_generator import parse_outline_structure

def main():
    """
    主函数：实现多数据源论文搜索、筛选和综述生成
    新流程：
    1. 搜索论文（arxiv最新日期，openalex和semantic scholar分别搜索最新日期和最高引用）
    2. 所有搜索到的论文用于生成综述
    3. 由大模型选择要引用的文献（固定数量）
    4. 生成综述
    """
    # 初始化Token计数器
    openai_config = get_openai_config()
    reset_token_counter(openai_config['model'])
    print("=" * 60)
    print("学术综述生成系统 - Token计数器已启动")
    print("=" * 60)

    # 加载配置
    runtime_config = get_runtime_config()

    path_config = get_path_config()
    user_input_config = get_user_input_config()
    fulltext_config = get_fulltext_config()

    # 显示欢迎信息
    print("=" * 80)
    print("欢迎使用学术综述生成系统")
    print("=" * 80)

    # 显示当前配置（如果启用调试）
    if runtime_config['enable_debug']:
        print_current_config()

    # 获取搜索关键词
    if user_input_config['enable_keyword_input']:
        # 询问用户输入关键词
        keyword = input("\n请输入要搜索的关键词（例如：transformer, deep learning, etc.）: ").strip()
        if not keyword:
            print("关键词不能为空！")
            return
        # 根据配置文件决定是否询问全文获取设置
        fulltext_choice = input(
            f"\n请选择快速模式或深度模式？（y/n）\n"
            "  - 选择'y'：对所有搜索到的论文进行智能全文获取（包括Arxiv的LaTeX源码），生成更深入的综述\n"
            "  - 选择'n'：仅使用论文摘要生成综述，速度更快\n"
            f"请选择 (y/n): ").strip().lower()
        smart_fulltext = fulltext_choice == 'y'
        if fulltext_choice == 'y':
            generation_mode = 'deep'
            search_config = get_search_config2()
        else:
            generation_mode = 'fast'
            search_config = get_search_config()
    # 获取Arxiv搜索数量
    arxiv_count = search_config['arxiv_count']
    openalex_latest = search_config['openalex_latest']
    openalex_cited = search_config['openalex_cited']

    semantic_latest = search_config['semantic_latest']

    semantic_cited = search_config['semantic_cited']

    # 获取最终引用文献数量
    citation_count = search_config['citation_paper_count']

    # 获取参考文献数量
    reference_count = search_config['reference_paper_count']


    # smart_fulltext=False

    print(f"\n搜索配置：")
    print(f"  - Arxiv: {arxiv_count}篇（最新日期）")
    print(f"  - OpenAlex: {openalex_latest}篇最新日期 + {openalex_cited}篇最高引用")
    print(f"  - Semantic Scholar: {semantic_latest}篇最新日期 + {semantic_cited}篇最高引用")
    print(f"  - 参考文献数量: {reference_count}篇（用于综述撰写）")
    print(f"  - 引用文献数量: {citation_count}篇（用于文中详细引用）")
    print(f"  - 全文获取模式: {'智能获取所有论文全文' if smart_fulltext else '仅使用论文摘要'}")

    # ========== 第一步：搜索论文 ==========
    print("\n" + "=" * 80)
    print("第一步：搜索论文...")
    print("=" * 80)

    arxiv_papers = []
    semantic_papers = []
    openalex_papers = []

    # 搜索Arxiv（最新日期）
    if arxiv_count > 0:
        print(f"\n从Arxiv搜索 {arxiv_count} 篇最新日期的论文...")
        arxiv_papers = search_arxiv_papers(keyword, arxiv_count, include_latex=False)
        print(f"Arxiv找到 {len(arxiv_papers)} 篇论文")
        # Arxiv论文无需再进行引用查询

    # 搜索OpenAlex（最新日期 + 最高引用）
    if openalex_latest > 0 or openalex_cited > 0:
        print(f"\n从OpenAlex搜索论文...")
        try:
            openalex_papers = search_openalex_papers(
                keyword,
                max_results=0,  # 不使用max_results，使用latest_count和cited_count
                include_details=True,
                latest_count=openalex_latest,
                cited_count=openalex_cited
            )
            print(f"OpenAlex找到 {len(openalex_papers)} 篇论文")
            if len(openalex_papers) == 0:
                print("  注意: OpenAlex未找到论文，可能是网络连接问题或API限制")
                print("  建议: 如果多次失败，可以考虑减少OpenAlex的搜索数量")
        except Exception as e:
            print(f"  OpenAlex搜索出错: {e}")
            print("  建议: 检查网络连接，或暂时减少OpenAlex数据源的使用")
            openalex_papers = []

    # 搜索Semantic Scholar（最新日期 + 最高引用）
    if semantic_latest > 0 or semantic_cited > 0:
        print(f"\n从Semantic Scholar搜索论文...")
        try:
            semantic_papers = search_semantic_scholar_papers(
                keyword,
                max_results=0,  # 不使用max_results，使用latest_count和cited_count
                include_details=True,
                latest_count=semantic_latest,
                cited_count=semantic_cited
            )
            print(f"Semantic Scholar找到 {len(semantic_papers)} 篇论文")
            if len(semantic_papers) == 0:
                print("  警告: Semantic Scholar未找到论文，可能是网络问题或API限制。")
                print("  建议: 可以稍后重试，或仅使用Arxiv数据源。")
        except Exception as e:
            print(f"  Semantic Scholar搜索出错: {e}")
            print("  将继续使用已找到的论文...")
            semantic_papers = []

    # 合并和去重
    print("\n" + "=" * 80)
    print("合并搜索结果并去重...")
    print("=" * 80)
    all_papers = merge_and_deduplicate_papers(arxiv_papers, semantic_papers, openalex_papers)

    if not all_papers:
        print("未找到相关论文，请尝试其他关键词。")
        return

    print(f"\n去重后共找到 {len(all_papers)} 篇不重复的相关论文")

    # ========== 第一步：两步筛选文献 ==========
    print("\n" + "=" * 80)
    print("开始两步筛选文献...")
    print("=" * 80)
    # 使用新的两步筛选方法
    reference_papers, citation_papers, citation_index_mapping = filter_papers_two_stage(
        all_papers,
        reference_count,
        citation_count,
        keyword
    )
    print('reference_papers')
    print(reference_papers)
    print('citation_papers')
    print(citation_papers)
    if not reference_papers:
        print("参考文献筛选失败，使用所有论文作为参考文献")
        reference_papers = all_papers

    # 如果筛选失败导致citation_papers为空，使用reference_papers
    if not citation_papers:
        print("引用文献筛选失败，使用参考文献作为引用文献")
        citation_papers = reference_papers.copy()
        # 生成默认的序号映射：1->1, 2->2, ...
        citation_index_mapping = {i: i for i in range(1, len(citation_papers) + 1)}

    if not citation_papers:
        print("引用文献筛选失败，使用所有参考文献作为引用文献")
        citation_papers = reference_papers

    print(f"\n最终筛选结果：")
    print(f"  - 参考文献: {len(reference_papers)} 篇（用于综述撰写）")
    print(f"  - 引用文献: {len(citation_papers)} 篇（用于文中详细引用，为参考文献的子集）")

    # ========== 第二步：获取引用次数信息（仅对非Arxiv论文） ==========
    print("\n" + "=" * 80)
    print("第二步：获取论文引用次数信息（Arxiv论文无需查询）...")
    print("=" * 80)
    papers_for_review = enrich_papers_with_citations(reference_papers)

    fulltext_stats = {'latex': 0, 'xml': 0, 'pdf_text': 0, 'metadata_only': len(papers_for_review)}

    # 显示统计信息
    print("\n" + "=" * 80)
    print("全文内容获取统计:")
    print("=" * 80)
    for content_type, count in fulltext_stats.items():
        if count > 0:
            type_name = {
                'latex': 'LaTeX源码',
                'xml': 'XML全文',
                'pdf_text': 'PDF文本',
                'metadata_only': '仅元数据'
            }.get(content_type, content_type)
            print(f"  {type_name}: {count} 篇")

    # ========== 第四步：生成综述大纲 ==========
    print("\n" + "=" * 80)
    print("第四步：生成综述大纲...")
    print("=" * 80)

    if smart_fulltext:
        print("综述生成模式：深度模式（基于智能获取的全文内容）")
        print("系统将充分利用论文的全文内容生成更深入、更有洞察力的综述。")
    else:
        print("综述生成模式：快速模式（基于论文摘要）")
        print("系统将使用论文摘要信息生成结构化的综述，撰写速度更快。")

    # 生成综述大纲
    # 使用参考文献生成大纲，但只分配引用文献给各章节
    outline_text, citation_index_mapping = generate_review_outline(
        papers_for_review, keyword, generation_mode, citation_papers, citation_index_mapping
    )
    # 打印大纲内容
    print("\n" + "=" * 80)
    print("生成的综述大纲：")
    print("=" * 80)
    print(outline_text)
    print("=" * 80)
    sections = parse_outline_structure(outline_text)
    # 找到需要提取全文内容的目标章节的索引
    intro_index = None
    trend_index = None
    for i, section in enumerate(sections):
        if section['title'] == '引言':
            intro_index = i
        elif section['title'] == '当前研究趋势与热点':
            trend_index = i

    if intro_index is None or trend_index is None:
        print("未找到指定章节")
    else:
        # 提取中间章节的所有论文序号
        middle_sections = sections[intro_index + 1:trend_index]
        all_papers = []
        for section in middle_sections:
            all_papers.extend(section.get('papers', []))

        # 去重并排序
        unique_papers = sorted(set(all_papers))
        print("提取到的论文序号（去重后）:", unique_papers)
    #---------------------------------------------------------------------------
    # ========== 第三步：智能获取全文内容 ==========
    if smart_fulltext:
        print("\n" + "=" * 80)
        print("第三步：智能获取所需论文的全文内容...")
        print("=" * 80)

        downloader = FullTextDownloader()
        fulltext_stats = {'latex': 0, 'xml': 0, 'pdf_text': 0, 'metadata_only': 0}

        for i, paper in enumerate(citation_papers, 1):
            if i in unique_papers:
                print(f"\n处理论文 [{i}/{len(unique_papers)}]: {paper.get('title', '未知标题')[:60]}...")
                fulltext_info = downloader.smart_get_fulltext(paper)
                # print('system-check')
                # print(extract_text_from_pdf_url(paper.get('pdf_url')))
                paper['full_text'] = fulltext_info
                citation_papers[i-1]['full_text'] = fulltext_info
                content_type = fulltext_info.get('content_type', 'metadata_only')
                fulltext_stats[content_type] = fulltext_stats.get(content_type, 0) + 1
                if content_type != 'metadata_only':
                    print(f"  ✓ {fulltext_info.get('reason', '成功获取全文')}")
                    # 如果获取到LaTeX内容，也设置latex_content字段以兼容旧代码
                    if content_type == 'latex' and fulltext_info.get('content'):
                        paper['latex_content'] = fulltext_info['content']
                else:
                    print(f"  - {fulltext_info.get('reason', '无法获取全文，将使用摘要')}")

                    print(f"  - {fulltext_info.get('reason', 'no full text available')}")
                fulltext_stats[content_type] = fulltext_stats.get(content_type, 0) + 1

                if content_type != 'metadata_only':
                    print(f"  - {fulltext_info.get('reason', 'no full text available')}")
                    # 如果获取到LaTeX内容，也设置latex_content字段以兼容旧代码
                    print(f"  - {fulltext_info.get('reason', 'no full text available')}")
                    print(f"  - {fulltext_info.get('reason', 'no full text available')}")
                else:
                    print(f"  - {fulltext_info.get('reason', 'no full text available')}")
    else:
        print("\n" + "=" * 80)
        print("第三步：跳过全文获取，将使用论文摘要进行综述撰写...")
        print("=" * 80)
        print("所有论文将仅使用摘要信息生成综述，撰写速度更快。")
    if not outline_text or "出错" in outline_text or "失败" in outline_text:
        print("\n错误：大纲生成失败，无法继续生成综述")
        return

    for content_type, count in fulltext_stats.items():
        if count > 0:
            type_name = {
                'latex': 'LaTeX源码',
                'xml': 'XML全文',
                'pdf_text': 'PDF文本',
                'metadata_only': '仅元数据'
            }.get(content_type, content_type)
            print(f"  {type_name}: {count} 篇")
    # # 使用参考文献撰写综述，引用文献用于文中引用
    if generation_mode=='fast':
        review = write_review_from_outline(outline_text, papers_for_review, keyword, citation_papers)
    else:
        review = write_review_from_outline_deep(outline_text, papers_for_review, keyword, citation_papers)

    if not review or "解析大纲失败" in review or "出错" in review:
        print("\n错误：综述正文撰写失败")
        return

    # 使用引用文献作为最终引用文献
    final_cited_papers = citation_papers
    print(f"\n最终使用引用文献 {len(final_cited_papers)} 篇用于文中详细引用")
    # 输出结果
    print("\n" + "=" * 80)
    print("最终生成的综述：")
    print("=" * 80)
    print(review)
    print("=" * 80)

    # 可选：保存到文件
    if user_input_config['enable_save_config']:
        save_option = input("\n是否保存综述到文件？(y/n): ").strip().lower()
        should_save = save_option == 'y'
    else:
        # 使用配置文件中的默认设置（自动保存）
        should_save = True

    if should_save:
        import os
        filename = f"综述_{keyword.replace(' ', '_')}.docx"
        save_review_to_docx(keyword, papers_for_review, citation_papers, review, filename)

    # ========== 打印Token使用统计 ==========
    print_token_summary()


if __name__ == "__main__":
    main()
