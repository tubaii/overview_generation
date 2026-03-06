#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调试引用问题的脚本
"""

def test_citation_mapping():
    """测试引用序号映射"""
    print("调试引用序号映射")
    print("=" * 50)

    # 模拟大纲解析结果
    sections = [
        {
            'title': '引言',
            'papers': [0, 1],  # 0-based indices in outline
        },
        {
            'title': '卷积神经网络方法',
            'papers': [2, 3, 4],  # 0-based indices in outline
        },
        {
            'title': '注意力机制方法',
            'papers': [5, 6, 7],  # 0-based indices in outline
        }
    ]

    # 模拟论文列表（实际的papers数组）
    papers = [
        {'title': 'Paper A', 'authors': ['Author A']},  # index 0
        {'title': 'Paper B', 'authors': ['Author B']},  # index 1
        {'title': 'Paper C', 'authors': ['Author C']},  # index 2
        {'title': 'Paper D', 'authors': ['Author D']},  # index 3
        {'title': 'Paper E', 'authors': ['Author E']},  # index 4
        {'title': 'Paper F', 'authors': ['Author F']},  # index 5
        {'title': 'Paper G', 'authors': ['Author G']},  # index 6
        {'title': 'Paper H', 'authors': ['Author H']},  # index 7
    ]

    # 模拟正文生成时的逻辑
    for section in sections:
        section_title = section['title']
        paper_indices = section['papers']  # 0-based indices from outline

        print(f"\n章节: {section_title}")
        print(f"大纲分配的论文索引: {paper_indices}")

        # 在正文生成时，为每个章节重新编号（1-based for citations）
        citation_mapping = ""
        for local_idx, paper_idx in enumerate(paper_indices, 1):
            if 0 <= paper_idx < len(papers):
                paper = papers[paper_idx]
                title = paper.get('title', 'Unknown')[:30]
                citation_mapping += f"  [论文{local_idx}] -> papers[{paper_idx}] ({title})\n"

        print("引用序号映射关系:")
        print(citation_mapping.strip())

        # 计算允许的引用序号
        allowed_citations = list(range(1, len(paper_indices) + 1))
        print(f"允许在文本中使用的引用序号: {allowed_citations}")

        # 模拟验证逻辑
        import re
        def validate_citation_compliance(text, allowed_paper_indices):
            citation_pattern = r'\[(\d+(?:,\s*\d+)*)\]'
            citations = re.findall(citation_pattern, text)
            used_citations = []
            for citation in citations:
                numbers = re.findall(r'\d+', citation)
                used_citations.extend([int(n) for n in numbers])
            used_citations = list(set(used_citations))
            allowed_citations = [i + 1 for i in range(len(allowed_paper_indices))]
            for citation in used_citations:
                if citation not in allowed_citations:
                    return False
            return True

        # 测试不同情况
        test_cases = [
            ("正确引用", f"在{section_title}中，[1]和[2]提出了重要方法。", True),
            ("错误引用", f"在{section_title}中，[1]和[5]提出了重要方法。", False),  # [5]超出范围
            ("组合引用", f"在{section_title}中，[1,2,3]都涉及了这个方法。", len(paper_indices) >= 3),
            ("无引用", f"在{section_title}中讨论了一些方法。", True),
        ]

        print("验证测试:")
        for test_name, test_text, should_pass in test_cases:
            result = validate_citation_compliance(test_text, paper_indices)
            status = "PASS" if result == should_pass else "FAIL"
            print(f"  {status} {test_name}: {result} (期望: {should_pass})")
            if result != should_pass:
                print(f"     文本: {test_text}")
                print(f"     允许序号: {allowed_citations}")

    print("\n" + "=" * 50)
    print("调试完成")

if __name__ == "__main__":
    test_citation_mapping()
