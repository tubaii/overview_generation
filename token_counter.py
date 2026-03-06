"""
Token计数器模块

功能：
1. 计算文本的token数量
2. 记录每次API调用的token使用
3. 统计并打印总消耗
"""

import tiktoken
from typing import Dict, List, Optional
from datetime import datetime


class TokenCounter:
    """
    Token计数器类
    
    用于：
    - 计算文本的token数量
    - 记录每次API调用
    - 统计总消耗
    """
    
    def __init__(self, model_name: str = "qwen-max"):
        """
        初始化Token计数器
        
        Args:
            model_name: 使用的模型名称（用于确定编码器）
        """
        self.model_name = model_name
        self.encoding = None
        self.calls = []  # 记录所有API调用
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost = 0.0
        
        # 初始化编码器
        self._init_encoder()
    
    def _init_encoder(self):
        """初始化编码器"""
        try:
            # 尝试使用cl100k_base编码器（GPT-4/Qwen兼容）
            self.encoding = tiktoken.get_encoding("cl100k_base")
        except Exception:
            try:
                # 备用：尝试其他编码器
                self.encoding = tiktoken.encoding_for_model(self.model_name)
            except Exception:
                # 最后备用：使用UTF-8字符估算
                pass
    
    def num_tokens_from_string(self, text: str) -> int:
        """
        计算文本的token数量
        
        Args:
            text: 输入文本
        
        Returns:
            token数量估算
        """
        if not text:
            return 0
        
        if self.encoding:
            try:
                return len(self.encoding.encode(text))
            except Exception:
                pass
        
        # 备用估算：英文约4字符/token，中文约1.5字符/token
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        other_chars = len(text) - chinese_chars
        return int(chinese_chars * 0.7 + other_chars * 0.25)
    
    def count_messages(self, messages: List[Dict]) -> int:
        """
        计算消息列表的token数量
        
        Args:
            messages: OpenAI格式的消息列表
        
        Returns:
            token数量
        """
        if not messages:
            return 0
        
        # 估算每个消息的token（大约）
        tokens_per_message = 4  # 消息格式开销
        tokens_per_name = 1     # name字段开销
        
        total = 0
        for msg in messages:
            total += tokens_per_message
            total += self.num_tokens_from_string(msg.get('role', ''))
            total += self.num_tokens_from_string(msg.get('content', ''))
            if msg.get('name'):
                total += tokens_per_name
        
        return total
    
    def record_call(self, input_tokens: int, output_tokens: int, 
                    call_type: str = "general", details: str = ""):
        """
        记录一次API调用
        
        Args:
            input_tokens: 输入token数
            output_tokens: 输出token数
            call_type: 调用类型（如 "outline", "review", "hallucination"）
            details: 详细说明
        """
        call_info = {
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'type': call_type,
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
            'total_tokens': input_tokens + output_tokens,
            'details': details
        }
        
        self.calls.append(call_info)
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        
        # 估算成本（Qwen-turbo近似价格）
        input_cost = input_tokens * 0.000002  # $2/1M tokens
        output_cost = output_tokens * 0.000006  # $6/1M tokens
        self.total_cost += input_cost + output_cost
    
    def get_call_count(self) -> int:
        """获取API调用次数"""
        return len(self.calls)
    
    def get_total_tokens(self) -> int:
        """获取总token数"""
        return self.total_input_tokens + self.total_output_tokens
    
    def get_summary(self) -> Dict:
        """
        获取使用统计摘要
        
        Returns:
            统计信息字典
        """
        return {
            'total_calls': self.get_call_count(),
            'total_input_tokens': self.total_input_tokens,
            'total_output_tokens': self.total_output_tokens,
            'total_tokens': self.get_total_tokens(),
            'estimated_cost_usd': round(self.total_cost, 4)
        }
    
    def print_summary(self):
        """打印使用统计"""
        summary = self.get_summary()
        
        print("\n" + "=" * 60)
        print("Token 使用统计")
        print("=" * 60)
        print(f"  API调用次数:     {summary['total_calls']}")
        print(f"  输入Token:       {summary['total_input_tokens']:,}")
        print(f"  输出Token:       {summary['total_output_tokens']:,}")
        print(f"  总Token:         {summary['total_tokens']:,}")
        # print(f"  预估成本 (USD):  ${summary['estimated_cost_usd']:.4f}")
        print("=" * 60)
        
        # 按类型统计
        if self.calls:
            type_stats = {}
            for call in self.calls:
                t = call['type']
                if t not in type_stats:
                    type_stats[t] = {'count': 0, 'tokens': 0}
                type_stats[t]['count'] += 1
                type_stats[t]['tokens'] += call['total_tokens']
            
            if type_stats:
                print("\n按调用类型统计:")
                print("-" * 40)
                for call_type, stats in sorted(type_stats.items(), key=lambda x: x[1]['tokens'], reverse=True):
                    print(f"  {call_type:15} | {stats['count']:3}次 | {stats['tokens']:>8,} tokens")
                print("-" * 40)
        
        print()
    
    def get_calls(self) -> List[Dict]:
        """获取所有调用记录"""
        return self.calls


# 全局Token计数器实例
_global_token_counter: Optional[TokenCounter] = None


def get_token_counter() -> TokenCounter:
    """获取全局Token计数器实例"""
    global _global_token_counter
    if _global_token_counter is None:
        _global_token_counter = TokenCounter()
    return _global_token_counter


def reset_token_counter(model_name: str = "qwen-max"):
    """重置Token计数器"""
    global _global_token_counter
    _global_token_counter = TokenCounter(model_name)


def count_tokens(text: str) -> int:
    """快速计算文本token数"""
    counter = get_token_counter()
    return counter.num_tokens_from_string(text)


def record_api_call(input_tokens: int, output_tokens: int, 
                    call_type: str = "general", details: str = ""):
    """记录一次API调用"""
    counter = get_token_counter()
    counter.record_call(input_tokens, output_tokens, call_type, details)


def print_token_summary():
    """打印Token统计"""
    counter = get_token_counter()
    counter.print_summary()


def get_token_summary() -> Dict:
    """获取Token统计"""
    counter = get_token_counter()
    return counter.get_summary()


if __name__ == "__main__":
    # 测试Token计数器
    print("Token计数器测试")
    print("=" * 50)
    
    counter = TokenCounter()
    
    # 测试文本
    test_texts = [
        "Hello, world!",  # 英文短文本
        "你好，世界！",   # 中文短文本
        "Artificial intelligence (AI) is intelligence demonstrated by machines, as opposed to the natural intelligence displayed by animals including humans." * 10,  # 长英文
        "人工智能（Artificial Intelligence，简称AI）是计算机科学的一个分支，它企图了解智能的实质，并生产出一种新的能以人类智能相似的方式做出反应的智能机器。" * 5  # 长中文
    ]
    
    for i, text in enumerate(test_texts, 1):
        tokens = counter.num_tokens_from_string(text)
        chars = len(text)
        print(f"文本 {i}: {chars} 字符 -> 约 {tokens} tokens")
    
    print("\n" + "=" * 50)
    print("模拟API调用记录:")
    
    # 模拟调用
    counter.record_call(1500, 500, "outline", "生成大纲")
    counter.record_call(2000, 300, "outline", "生成大纲2")
    counter.record_call(3000, 1500, "review", "撰写综述")
    counter.record_call(4000, 2000, "revise", "修订综述")
    
    counter.print_summary()

