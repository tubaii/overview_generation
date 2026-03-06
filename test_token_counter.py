#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Token计数器测试脚本"""
import sys
sys.path.insert(0, 'd:/all_project/python_project/Overview_generation_r')

from token_counter import TokenCounter, reset_token_counter, get_token_summary, record_api_call, print_token_summary

# 初始化
reset_token_counter('qwen-max')
print('=' * 60)
print('Token计数器测试')
print('=' * 60)

# 模拟一些API调用
record_api_call(1500, 500, 'outline', '生成大纲')
record_api_call(2000, 800, 'outline', '生成大纲2')
record_api_call(5000, 2000, 'review', '撰写综述')
record_api_call(6000, 2500, 'review', '撰写综述2')
record_api_call(4000, 1500, 'revise', '修订综述')
record_api_call(1000, 300, 'filter', '筛选论文')

print()
summary = get_token_summary()
print(f'API调用次数: {summary["total_calls"]}')
print(f'输入Token: {summary["total_input_tokens"]:,}')
print(f'输出Token: {summary["total_output_tokens"]:,}')
print(f'总Token: {summary["total_tokens"]:,}')
print(f'预估成本: ${summary["estimated_cost_usd"]:.4f}')
print()
print_token_summary()
