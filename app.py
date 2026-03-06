"""
学术综述生成系统 - Flask Web界面

功能：
1. 提供Web界面输入搜索参数
2. 支持快速模式和深度模式选择
3. 生成综述并提供docx文件下载
4. 实时显示生成进度和日志
"""

from flask import Flask, render_template, request, send_file, jsonify, Response
import os
import sys
import time
import threading
from datetime import datetime
from pathlib import Path

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

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

app = Flask(__name__)
app.secret_key = 'overview_generation_secret_key'

# 任务状态存储
tasks = {}


class TaskManager:
    """任务管理器"""
    
    def __init__(self):
        self.tasks = {}
        self.logs = {}  # 存储每个任务的日志
    
    def create_task(self, task_id, **kwargs):
        """创建新任务"""
        self.tasks[task_id] = {
            'status': 'pending',
            'progress': 0,
            'message': '等待开始...',
            'result': None,
            'error': None,
            'keyword': kwargs.get('keyword', ''),
            'mode': kwargs.get('mode', 'fast'),
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            **kwargs
        }
        self.logs[task_id] = []
        return task_id
    
    def get_task(self, task_id):
        """获取任务状态"""
        return self.tasks.get(task_id)
    
    def update_task(self, task_id, **kwargs):
        """更新任务状态"""
        if task_id in self.tasks:
            self.tasks[task_id].update(kwargs)
    
    def add_log(self, task_id, message, level='info'):
        """添加日志"""
        if task_id not in self.logs:
            self.logs[task_id] = []
        
        log_entry = {
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'message': message,
            'level': level
        }
        self.logs[task_id].append(log_entry)
        
        # 保留最近100条日志
        if len(self.logs[task_id]) > 100:
            self.logs[task_id] = self.logs[task_id][-100:]
    
    def get_logs(self, task_id, since=0):
        """获取日志（用于流式传输）"""
        if task_id not in self.logs:
            return []
        logs = self.logs[task_id]
        return [log for log in logs if len(logs) - logs.index(log) > since]
    
    def clear_logs(self, task_id):
        """清空日志"""
        if task_id in self.logs:
            self.logs[task_id] = []
    
    def list_tasks(self):
        """列出所有任务"""
        return sorted(self.tasks.values(), 
                     key=lambda x: x.get('created_at', ''), 
                     reverse=True)


task_manager = TaskManager()


@app.route('/')
def index():
    """主页"""
    config = get_user_input_config()
    return render_template('index.html',
                          default_keyword=config.get('search_keyword', 'transformer'),
                          default_mode='fast')


@app.route('/api/start', methods=['POST'])
def start_generation():
    """开始生成综述"""
    data = request.json

    keyword = data.get('keyword', '').strip()
    mode = data.get('mode', 'fast')

    if not keyword:
        return jsonify({'error': '请输入搜索关键词'}), 400

    # 生成任务ID
    task_id = f"task_{int(time.time())}"

    # 在后台线程中运行生成任务
    def run_task():
        try:
            task_manager.update_task(task_id, status='running', progress=0, 
                                    message='正在初始化...')
            task_manager.add_log(task_id, f'开始生成综述，关键词: {keyword}，模式: {"深度模式" if mode == "deep" else "快速模式"}', 'info')

            # 更新运行时配置
            runtime_config = get_runtime_config()
            runtime_config['generation_mode'] = mode

            # 重置token计数器
            openai_config = get_openai_config()
            from token_counter import reset_token_counter, get_token_summary
            reset_token_counter(openai_config['model'])

            task_manager.update_task(task_id, message='多学术源论文搜索中...', progress=10)
            task_manager.add_log(task_id, '多学术源论文搜索中...', 'info')

            # 搜索论文
            from paper_search_filter import (
                search_arxiv_papers,
                search_openalex_papers,
                search_semantic_scholar_papers,
                merge_and_deduplicate_papers,
                filter_papers_two_stage,
                enrich_papers_with_citations
            )

            # 搜索论文
            from paper_search_filter import (
                search_arxiv_papers,
                search_openalex_papers,
                search_semantic_scholar_papers,
                merge_and_deduplicate_papers,
                filter_papers_two_stage,
                enrich_papers_with_citations
            )
            if mode == 'deep':
                search_config = get_search_config2()
            else:
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
            semantic_papers = []

            # 搜索Arxiv
            arxiv_papers = search_arxiv_papers(keyword, arxiv_count, include_latex=False)

            # 搜索OpenAlex
            openalex_papers = search_openalex_papers(
                keyword,
                latest_count=openalex_latest,
                cited_count=openalex_cited
            )

            # 搜索Semantic Scholar（如果配置数量大于0）
            if semantic_latest > 0 or semantic_cited > 0:
                semantic_papers = search_semantic_scholar_papers(
                    keyword,
                    latest_count=semantic_latest,
                    cited_count=semantic_cited,
                    include_details=True
                )

            # 合并去重（包含 Arxiv / Semantic Scholar / OpenAlex）
            all_papers = merge_and_deduplicate_papers(arxiv_papers, semantic_papers, openalex_papers)

            if not all_papers:
                task_manager.update_task(task_id, status='failed', 
                                        error='未找到相关论文，请尝试其他关键词')
                task_manager.add_log(task_id, '未找到相关论文', 'error')
                return

            task_manager.update_task(task_id, message='论文筛选中...', progress=40)
            task_manager.add_log(task_id, '论文筛选中...', 'info')

            # 使用两步筛选方法
            reference_papers, citation_papers, citation_index_mapping = filter_papers_two_stage(
                all_papers, reference_count, citation_count, keyword
            )

            if not reference_papers:
                reference_papers = all_papers

            if not citation_papers:
                citation_papers = reference_papers

            # 为参考文献补充/规范引用次数信息
            reference_papers = enrich_papers_with_citations(reference_papers)

            task_manager.update_task(task_id, message='大纲生成中...', progress=50)
            task_manager.add_log(task_id, '大纲生成中...', 'info')

            # 生成大纲
            from outline_generator import generate_review_outline
            outline, citation_index_mapping = generate_review_outline(
                reference_papers, keyword, mode, citation_papers, citation_index_mapping
            )

            if not outline or "出错" in outline:
                task_manager.update_task(task_id, status='failed',
                                        error='大纲生成失败')
                task_manager.add_log(task_id, '大纲生成失败', 'error')
                return

            task_manager.update_task(task_id, message='显示大纲...', progress=60)
            task_manager.add_log(task_id, '显示大纲...', 'info')
            task_manager.add_log(task_id, f'===== 大纲内容 =====\n{outline}\n===== 大纲结束 =====', 'info')

            task_manager.update_task(task_id, message='逐章节撰写综述中...', progress=70)
            task_manager.add_log(task_id, '逐章节撰写综述中...', 'info')

            # 撰写综述
            from review_writer import write_review_from_outline, write_review_from_outline_deep

            # 根据模式选择撰写方式：快速 / 深度
            if mode == 'deep':
                review = write_review_from_outline_deep(
                    outline, reference_papers, keyword, citation_papers
                )
            else:
                review = write_review_from_outline(
                    outline, reference_papers, keyword, citation_papers
                )

            # 撰写过程中更新进度，避免进度条长时间停留
            task_manager.update_task(task_id, progress=80)

            if not review or "解析大纲失败" in review:
                task_manager.update_task(task_id, status='failed',
                                        error='综述撰写失败')
                task_manager.add_log(task_id, '综述撰写失败', 'error')
                return

            task_manager.update_task(task_id, message='显示逐章节综述内容...', progress=85)
            task_manager.add_log(task_id, '显示逐章节综述内容...', 'info')
            task_manager.add_log(task_id, f'===== 综述内容 =====\n{review[:2000]}...\n===== 综述结束 =====', 'info')

            task_manager.update_task(task_id, message='格式检查输出中...', progress=90)
            task_manager.add_log(task_id, '格式检查输出中...', 'info')

            # 保存文件
            filename = f"综述_{keyword.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"

            from format_check import save_review_to_docx
            save_review_to_docx(keyword, reference_papers, citation_papers, review, filename)

            # 获取文件路径
            output_dir = './output'
            filepath = os.path.join(output_dir, filename)

            if not os.path.exists(filepath):
                filepath = filename

            # 获取本次任务的 Token 统计信息
            token_summary = get_token_summary()

            task_manager.update_task(task_id, status='completed',
                                    progress=100,
                                    message='综述生成完成！',
                                    result={
                                        'filename': filename,
                                        'filepath': filepath,
                                        'paper_count': len(all_papers),
                                        'reference_count': len(reference_papers),
                                        'citation_count': len(citation_papers),
                                        'token_summary': token_summary
                                    })
            task_manager.add_log(task_id, '综述生成完成！', 'success')
            print(f"[DEBUG] Task {task_id} completed successfully!")

        except Exception as e:
            error_msg = str(e)
            task_manager.update_task(task_id, status='failed',
                                    error=error_msg)
            task_manager.add_log(task_id, f'错误: {error_msg}', 'error')

    # 创建任务并启动线程
    task_manager.create_task(task_id, keyword=keyword, mode=mode)
    thread = threading.Thread(target=run_task)
    thread.start()

    return jsonify({
        'task_id': task_id,
        'message': '任务已启动'
    })


@app.route('/api/status/<task_id>')
def get_task_status(task_id):
    """获取任务状态"""
    task = task_manager.get_task(task_id)
    if not task:
        return jsonify({'error': '任务不存在'}), 404

    response = {
        'status': task['status'],
        'progress': task.get('progress', 0),
        'message': task.get('message', ''),
    }

    if task['status'] == 'completed' and task.get('result'):
        response['result'] = task['result']
    elif task['status'] == 'failed':
        response['error'] = task.get('error', '未知错误')

    # 调试：打印当前任务状态
    print(f"[DEBUG] task_id={task_id}, status={task['status']}, progress={task.get('progress')}")

    return jsonify(response)


@app.route('/api/logs/<task_id>')
def get_logs(task_id):
    """获取任务日志"""
    try:
        since = int(request.args.get('since', 0))
    except:
        since = 0
    
    logs = task_manager.get_logs(task_id, since)
    return jsonify(logs)


@app.route('/api/logs/<task_id>/stream')
def stream_logs(task_id):
    """流式传输日志 (Server-Sent Events)"""
    def generate():
        last_index = 0
        while True:
            logs = task_manager.get_logs(task_id, last_index)
            for log in logs:
                last_index += 1
                data = f"data: {log['timestamp']} | {log['message']}\n\n"
                yield data
            
            # 检查任务状态
            task = task_manager.get_task(task_id)
            if task and task['status'] in ['completed', 'failed']:
                break
            
            time.sleep(0.5)
    
    return Response(generate(), mimetype='text/event-stream')


@app.route('/api/download/<filename>')
def download_file(filename):
    """下载生成的docx文件"""
    filename = os.path.basename(filename)
    
    paths = [
        filename,
        os.path.join('./output', filename),
        os.path.join('.', filename),
    ]
    
    for filepath in paths:
        if os.path.exists(filepath):
            return send_file(filepath, as_attachment=True, download_name=filename)
    
    return jsonify({'error': '文件不存在'}), 404


@app.route('/api/history')
def get_history():
    """获取历史任务"""
    tasks = task_manager.list_tasks()[:10]
    return jsonify([{
        'id': t.get('task_id', ''),
        'keyword': t.get('keyword', ''),
        'mode': t.get('mode', ''),
        'status': t.get('status', ''),
        'created_at': t.get('created_at', ''),
        'result': t.get('result') if t.get('status') == 'completed' else None
    } for t in tasks])



# 创建输出目录
output_dir = './output'
if not os.path.exists(output_dir):
    os.makedirs(output_dir)


if __name__ == '__main__':
    print("=" * 60)
    print("学术综述生成系统 - Web界面")
    print("=" * 60)
    print("启动服务器...")
    print("访问地址: http://localhost:5000")
    print("=" * 60)
    app.run(debug=True, host='0.0.0.0', port=5000)
