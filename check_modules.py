#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
模块导入检查脚本
"""
import sys
import os

# 添加项目路径
project_path = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_path)

print("=" * 60)
print("系统模块检查")
print("=" * 60)

modules = [
    ('config', '配置模块'),
    ('paper_search_filter', '论文搜索模块'),
    ('outline_generator', '大纲生成模块'),
    ('review_writer', '综述撰写模块'),
    ('format_check', '格式检查模块'),
    ('hallucination_check', '幻觉检查模块'),
    ('system_check', '系统检查模块'),
    ('main', '主程序模块')
]

results = []
errors = []

for module_name, desc in modules:
    try:
        exec(f'import {module_name}')
        status = 'OK'
        print(f'  [OK] {module_name}.py')
        results.append((module_name, True, ''))
    except Exception as e:
        status = 'FAIL'
        error_msg = str(e)
        print(f'  [FAIL] {module_name}.py - Error: {error_msg}')
        results.append((module_name, False, error_msg))
        errors.append((module_name, error_msg))

print("=" * 60)
print(f"检查结果: {sum(1 for _, ok, _ in results if ok)}/{len(results)} 模块正常")
print("=" * 60)

if errors:
    print("\n需要修复的错误:")
    for module, error in errors:
        print(f"  - {module}.py: {error}")
    sys.exit(1)
else:
    print("\n所有模块检查通过!")
    sys.exit(0)





