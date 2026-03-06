from openai import OpenAI
import arxiv
import requests
import tarfile
import io
import re
import hashlib
import time
from typing import List, Dict, Set, Optional
from datetime import datetime
from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn

# Token计数
from token_counter import record_api_call, count_tokens

# 初始化客户端（从配置中读取）
from config import get_openai_config, get_fulltext_config
openai_config = get_openai_config()
fulltext_config = get_fulltext_config()
# 论文筛选涉及大量文本，增加超时时间
default_timeout = max(openai_config['timeout'], 120)
client = OpenAI(
    base_url=openai_config['base_url'],
    api_key=openai_config['api_key'],
    timeout=default_timeout
)

def make_semantic_scholar_request(url, params=None, max_retries=None, retry_delay=None):
    """
    统一的Semantic Scholar API请求函数，包含重试和速率限制处理

    Args:
        url: API请求URL
        params: 请求参数
        max_retries: 最大重试次数（默认从配置文件读取）
        retry_delay: 基础重试延迟（秒），会指数增长（默认从配置文件读取）

    Returns:
        response对象或None（如果失败）
    """
    # 使用配置文件中的默认值
    if max_retries is None:
        max_retries = fulltext_config['max_retries']
    if retry_delay is None:
        retry_delay = fulltext_config['retry_delay']
    import requests.exceptions
    
    for attempt in range(max_retries):
        try:
            response = requests.get(url, params=params, timeout=fulltext_config['timeout'])
            
            # 成功响应
            if response.status_code == 200:
                return response
            
            # 429错误：速率限制，固定等待15秒
            elif response.status_code == 429:
                # 固定等待15秒
                wait_time = 15
                
                if attempt < max_retries - 1:
                    print(f"  遇到速率限制（429），等待 {wait_time} 秒后重试... (尝试 {attempt + 1}/{max_retries})")
                    print(f"  提示：Semantic Scholar API有速率限制，请耐心等待...")
                    time.sleep(wait_time)
                    continue
                else:
                    print(f"  达到最大重试次数，仍遇到速率限制。")
                    print(f"  建议：请稍后再试，或减少搜索数量，或仅使用Arxiv数据源。")
                    return None
            
            # 其他HTTP错误
            else:
                print(f"  API请求失败，状态码: {response.status_code}")
                if attempt < max_retries - 1:
                    wait_time = min(30, retry_delay * (2 ** attempt))  # 其他错误最多等待30秒
                    print(f"  等待 {wait_time} 秒后重试... (尝试 {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                    continue
                return None
                
        except (requests.exceptions.ConnectionError, 
                requests.exceptions.Timeout,
                ConnectionResetError,
                OSError) as e:
            # 连接相关错误，使用更长的等待时间
            wait_time = max(3, retry_delay * (2 ** attempt))
            if attempt < max_retries - 1:
                error_type = type(e).__name__
                print(f"  连接错误 ({error_type})，等待 {wait_time} 秒后重试... (尝试 {attempt + 1}/{max_retries})")
                time.sleep(wait_time)
                continue
            else:
                print(f"  连接失败，已达到最大重试次数。请检查网络连接后重试。")
                return None
                
        except Exception as e:
            # 其他未知错误
            wait_time = min(30, retry_delay * (2 ** attempt))
            if attempt < max_retries - 1:
                print(f"  请求出错: {e}，等待 {wait_time} 秒后重试... (尝试 {attempt + 1}/{max_retries})")
                time.sleep(wait_time)
                continue
            else:
                print(f"  请求失败，已达到最大重试次数: {e}")
                return None
    
    return None

def get_paper_unique_id(paper_info):
    """
    生成论文的唯一标识符，用于去重
    优先级：paperId > title+author > title
    """
    # 如果有paperId，直接使用
    if paper_info.get('paper_id'):
        return f"id:{paper_info['paper_id']}"
    
    # 否则使用title+author的组合
    title = paper_info.get('title', '').lower().strip()
    authors = paper_info.get('authors', [])
    if authors:
        # 取前两个作者的首字母和标题
        author_str = ','.join(sorted([a.lower().strip() for a in authors[:2]]))
        return f"title_author:{hashlib.md5((title + author_str).encode()).hexdigest()}"
    
    # 最后只使用标题
    return f"title:{hashlib.md5(title.encode()).hexdigest()}"

def get_semantic_scholar_paper_details(paper_id):
    """
    通过paperId获取Semantic Scholar论文的详细信息
    包括PDF链接、引用数等
    """
    try:
        url = f"https://api.semanticscholar.org/graph/v1/paper/{paper_id}"
        params = {
            'fields': 'title,authors,year,abstract,url,venue,isOpenAccess,openAccessPdf,externalIds,citationCount,referenceCount'
        }
        response = make_semantic_scholar_request(url, params=params)
        if response:
            return response.json()
    except Exception as e:
        print(f"  获取论文详情时出错: {e}")
    return None

def search_semantic_scholar_papers(keyword, max_results=5, include_details=False, latest_count=6, cited_count=14):
    """
    使用Semantic Scholar API搜索相关论文
    支持分别搜索最新日期和最高引用的论文
    
    处理流程：
    1. 通过关键词搜索论文列表，获取基本信息（标题、作者、摘要、年份、venue等）
    2. 如果include_details=True，通过paperId获取详细信息（PDF链接、引用数等）
    3. 提取并统一格式化论文信息
    4. 注意：Semantic Scholar不提供LaTeX源码，只有摘要和元数据
    
    Args:
        keyword: 搜索关键词
        max_results: 最大结果数量（如果latest_count和cited_count都指定，则忽略此参数）
        include_details: 是否获取详细信息（包括PDF链接、引用数等）
        latest_count: 搜索最新日期的论文数量（默认6篇）
        cited_count: 搜索最高引用的论文数量（默认14篇）
    
    Returns:
        论文信息列表，每个论文包含：标题、作者、发表时间、摘要、venue、paperId、URL等
    """
    print(f"正在从Semantic Scholar搜索关键词: {keyword}...")
    
    papers = []
    all_papers_data = []
    
    try:
        # 如果指定了latest_count和cited_count，分别搜索
        if latest_count > 0:
            print(f"  搜索最新日期的论文（{latest_count}篇）...")
            url = "https://api.semanticscholar.org/graph/v1/paper/search"
            params = {
                'query': keyword,
                'limit': latest_count,
                'fields': 'title,authors,year,abstract,paperId,url,venue,isOpenAccess,citationCount',
                'sort': 'year:desc'  # 按年份降序（最新）
            }
            response = make_semantic_scholar_request(url, params=params)
            if response:
                data = response.json()
                latest_papers_data = data.get('data', [])
                all_papers_data.extend(latest_papers_data)
                print(f"  找到 {len(latest_papers_data)} 篇最新日期的论文")
        
        if cited_count > 0:
            print(f"  搜索最高引用的论文（{cited_count}篇）...")
            url = "https://api.semanticscholar.org/graph/v1/paper/search"
            params = {
                'query': keyword,
                'limit': cited_count,
                'fields': 'title,authors,year,abstract,paperId,url,venue,isOpenAccess,citationCount',
                'sort': 'citationCount:desc'  # 按引用数降序
            }
            response = make_semantic_scholar_request(url, params=params)
            if response:
                data = response.json()
                cited_papers_data = data.get('data', [])
                all_papers_data.extend(cited_papers_data)
                print(f"  找到 {len(cited_papers_data)} 篇最高引用的论文")
        
        # 如果都没有指定，使用原来的逻辑
        if latest_count == 0 and cited_count == 0:
            url = "https://api.semanticscholar.org/graph/v1/paper/search"
            params = {
                'query': keyword,
                'limit': max_results,
                'fields': 'title,authors,year,abstract,paperId,url,venue,isOpenAccess'
            }
            response = make_semantic_scholar_request(url, params=params)
            if response:
                data = response.json()
                all_papers_data = data.get('data', [])
        
        # 处理所有找到的论文
        for paper_data in all_papers_data:
            # 提取作者信息
            authors = []
            if paper_data.get('authors'):
                authors = [author.get('name', '') for author in paper_data['authors']]
            
            # 基础论文信息
            paper_id = paper_data.get('paperId', '')
            paper_info = {
                'title': paper_data.get('title', ''),
                'authors': authors,
                'published': str(paper_data.get('year', '')) if paper_data.get('year') else '',
                'summary': paper_data.get('abstract', ''),
                'entry_id': paper_data.get('url', ''),
                'paper_id': paper_id,
                'venue': paper_data.get('venue', ''),
                'source': 'semantic_scholar',
                'pdf_url': None,
                'latex_content': None,  # Semantic Scholar不提供LaTeX源码
                'citation_count': paper_data.get('citationCount'),  # 如果API返回了引用数，直接使用
                'reference_count': None
            }
            
            # 如果需要详细信息，通过paperId获取
            if include_details and paper_id:
                print(f"  正在获取论文详细信息: {paper_info['title'][:50]}...")
                details = get_semantic_scholar_paper_details(paper_id)
                if details:
                    # 获取PDF链接（如果开放获取）
                    if details.get('isOpenAccess') and details.get('openAccessPdf'):
                        paper_info['pdf_url'] = details.get('openAccessPdf', {}).get('url', '')
                    
                    # 获取引用数（如果之前没有）
                    if paper_info['citation_count'] is None:
                        paper_info['citation_count'] = details.get('citationCount', 0)
                    paper_info['reference_count'] = details.get('referenceCount', 0)
                    
                    # 如果有Arxiv ID，记录以便后续可能获取LaTeX
                    external_ids = details.get('externalIds', {})
                    if external_ids.get('ArXiv'):
                        paper_info['arxiv_id'] = external_ids['ArXiv']
            
            papers.append(paper_info)
            print(f"  找到论文: {paper_info['title']}")
            if paper_info.get('citation_count') is not None:
                print(f"    引用数: {paper_info['citation_count']}, 参考文献数: {paper_info.get('reference_count', 'N/A')}")
            
            # 每找到一篇论文后空闲2秒，以控制访问速度
            time.sleep(2.0)
    except Exception as e:
        print(f"  搜索Semantic Scholar时出错: {e}")
    
    return papers

def search_arxiv_papers(keyword, max_results=5, include_latex=False):
    """
    使用Arxiv API搜索相关论文，按最新日期排序
    """
    print(f"正在搜索关键词: {keyword}...")
    
    papers = []
    try:
        # 使用arxiv库直接搜索，按最新提交日期排序
        search = arxiv.Search(
            query=keyword,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.SubmittedDate,
            sort_order=arxiv.SortOrder.Descending
        )
        
        for paper in search.results():
            try:
                # 处理日期可能为None的情况
                published_date = ''
                if paper.published:
                    published_date = paper.published.strftime('%Y-%m-%d')
                
                paper_info = {
                    'title': paper.title or '',
                    'authors': [author.name for author in paper.authors] if paper.authors else [],
                    'published': published_date,
                    'summary': paper.summary or '',
                    'entry_id': paper.entry_id or '',
                    'paper_id': None,  # Arxiv没有paperId
                    'venue': 'arXiv',
                    'source': 'arxiv',
                    'pdf_url': paper.pdf_url if hasattr(paper, 'pdf_url') else None,
                    'latex_content': None,
                    'citation_count': None
                }
                
                # 如果需要获取LaTeX源码
                if include_latex:
                    latex_content = get_paper_latex_content(paper.entry_id)
                    if latex_content:
                        paper_info['latex_content'] = latex_content
                        print(f"  ✓ 已获取LaTeX源码")
                    else:
                        print(f"  ✗ 无法获取LaTeX源码，将使用摘要")
                
                papers.append(paper_info)
                print(f"  找到论文: {paper_info['title']}")
            except Exception as e:
                print(f"  处理论文时出错: {e}")
                continue
    except Exception as e:
        print(f"搜索Arxiv论文时出错: {e}")
    
    return papers

# class OpenAlexClient:
#     """
#     OpenAlex API客户端，用于搜索论文并获取元数据
#     增加了超时控制、重试机制和错误处理
#     """
#     def __init__(self):
#         self.base_url = "https://api.openalex.org"
#         self.max_retries = 3  # 最大重试次数
#         self.base_timeout = 60  # 基础超时时间（秒）
#         self.retry_delay = 5  # 重试间隔（秒）
#
#     def _make_request_with_retry(self, url: str, params: dict = None) -> Optional[requests.Response]:
#         """
#         带重试机制的HTTP请求
#
#         Args:
#             url: 请求URL
#             params: 请求参数
#
#         Returns:
#             Response对象或None
#         """
#         import socket
#
#         for attempt in range(self.max_retries):
#             try:
#                 # 设置较长的超时时间
#                 timeout = self.base_timeout * (1 + attempt * 0.5)  # 递增超时
#                 response = requests.get(url, params=params, timeout=timeout)
#
#                 if response.status_code == 200:
#                     return response
#                 elif response.status_code == 429:  # 速率限制
#                     wait_time = 60 * (attempt + 1)  # 等待更长时间
#                     print(f"  OpenAlex速率限制，等待{wait_time}秒后重试... (尝试 {attempt + 1}/{self.max_retries})")
#                     time.sleep(wait_time)
#                     continue
#                 else:
#                     print(f"  OpenAlex API错误: 状态码 {response.status_code}")
#                     if attempt < self.max_retries - 1:
#                         print(f"  等待{self.retry_delay}秒后重试... (尝试 {attempt + 1}/{self.max_retries})")
#                         time.sleep(self.retry_delay)
#                         continue
#                     return None
#
#             except requests.exceptions.Timeout:
#                 print(f"  请求超时 (尝试 {attempt + 1}/{self.max_retries})")
#                 if attempt < self.max_retries - 1:
#                     wait_time = self.retry_delay * (attempt + 1)
#                     print(f"  等待{wait_time}秒后重试...")
#                     time.sleep(wait_time)
#                     continue
#                 return None
#
#             except requests.exceptions.ConnectionError as e:
#                 print(f"  连接错误 (尝试 {attempt + 1}/{self.max_retries}): {e}")
#                 if attempt < self.max_retries - 1:
#                     wait_time = self.retry_delay * (attempt + 1)
#                     print(f"  等待{wait_time}秒后重试...")
#                     time.sleep(wait_time)
#                     continue
#                 return None
#
#             except socket.timeout:
#                 print(f"  Socket超时 (尝试 {attempt + 1}/{self.max_retries})")
#                 if attempt < self.max_retries - 1:
#                     wait_time = self.retry_delay * (attempt + 1)
#                     print(f"  等待{wait_time}秒后重试...")
#                     time.sleep(wait_time)
#                     continue
#                 return None
#
#             except Exception as e:
#                 print(f"  请求出错: {e}")
#                 if attempt < self.max_retries - 1:
#                     time.sleep(self.retry_delay)
#                     continue
#                 return None
#
#         print(f"  已达到最大重试次数({self.max_retries})")
#         return None
#
#     def search_papers(self, query: str, max_results: int = 50, sort: str = "cited_by_count:desc") -> List[Dict]:
#         """
#         通过OpenAlex搜索论文并获取丰富元数据
#
#         Args:
#             query: 搜索关键词
#             max_results: 最大返回数量
#             sort: 排序方式，默认按引用数降序
#
#         Returns:
#             论文列表
#         """
#         papers = []
#         try:
#             url = f"{self.base_url}/works"
#             params = {
#                 'search': query,
#                 'per-page': min(max_results, 200),  # OpenAlex单次最大200
#                 'sort': sort
#             }
#
#             print(f"  正在通过OpenAlex搜索: {query}...")
#
#             # 使用带重试的请求
#             response = self._make_request_with_retry(url, params)
#
#             if response is None:
#                 print(f"  OpenAlex搜索失败: 多次重试后仍无法连接")
#                 return papers
#
#             data = response.json()
#             results = data.get('results', [])
#
#             if not results:
#                 print(f"  OpenAlex未找到相关论文")
#                 return papers
#
#             print(f"  OpenAlex返回 {len(results)} 篇论文")
#             for i, work in enumerate(results, 1):
#                 try:
#                     paper_info = self._parse_openalex_paper(work)
#                     if paper_info:
#                         papers.append(paper_info)
#                         print(f"  找到论文 [{i}]: {paper_info['title'][:60]}...")
#                         if paper_info.get('citation_count') is not None:
#                             print(f"    引用数: {paper_info['citation_count']}")
#
#                     # 控制请求频率
#                     if i < len(results):
#                         time.sleep(1.0)  # 减少等待时间，避免太慢
#
#                 except Exception as e:
#                     print(f"  解析论文时出错: {e}")
#                     continue
#
#             if papers:
#                 print(f"  成功获取 {len(papers)} 篇论文")
#             else:
#                 print(f"  未能解析任何论文")
#
#         except Exception as e:
#             print(f"  OpenAlex搜索失败: {e}")
#             print(f"  建议: 检查网络连接，或稍后重试")
#
#         return papers
#
#     def _parse_openalex_paper(self, work: Dict) -> Optional[Dict]:
#         """
#         解析OpenAlex返回的论文数据，转换为统一格式
#         """
#         try:
#             # 提取开放获取信息
#             oa_info = work.get('open_access', {})
#             is_oa = oa_info.get('oa_status', 'closed') != 'closed'
#             oa_url = oa_info.get('oa_url')
#
#             # 提取全文位置信息
#             locations = work.get('locations', [])
#             pdf_url = None
#             landing_url = None
#
#             for location in locations:
#                 if location.get('pdf_url'):
#                     pdf_url = location['pdf_url']
#                 if location.get('landing_page_url'):
#                     landing_url = location['landing_page_url']
#
#             # 提取主题信息
#             topics = [topic.get('display_name', '') for topic in work.get('topics', [])[:5]]
#
#             # 提取作者信息
#             authors_list = []
#             for authorship in work.get('authorships', []):
#                 author = authorship.get('author', {})
#                 if author:
#                     authors_list.append(author.get('display_name', ''))
#
#             # 提取DOI
#             doi = work.get('doi')
#             if doi and doi.startswith('https://doi.org/'):
#                 doi = doi.replace('https://doi.org/', '')
#
#             # 提取Arxiv ID（如果有）
#             arxiv_id = None
#             primary_location = work.get('primary_location', {})
#             if primary_location:
#                 source = primary_location.get('source', {})
#                 if source and 'arxiv' in source.get('display_name', '').lower():
#                     # 尝试从URL提取Arxiv ID
#                     landing = primary_location.get('landing_page_url', '')
#                     arxiv_match = re.search(r'arxiv\.org/abs/(\d+\.\d+)', landing)
#                     if arxiv_match:
#                         arxiv_id = arxiv_match.group(1)
#
#             # 提取发表信息
#             venue = None
#             if work.get('primary_location', {}).get('source'):
#                 venue = work.get('primary_location', {}).get('source', {}).get('display_name', '')
#
#             publication_date = work.get('publication_date', '')
#             publication_year = work.get('publication_year')
#
#             return {
#                 'title': work.get('title', ''),
#                 'authors': authors_list[:10],  # 最多10个作者
#                 'published': publication_date,
#                 'publication_year': publication_year,
#                 'summary': work.get('abstract', ''),
#                 'doi': doi,
#                 'venue': venue or 'Unknown',
#                 'source': 'openalex',
#                 'paper_id': work.get('id', '').replace('https://openalex.org/', '') if work.get('id') else None,
#                 'entry_id': work.get('id', '') if work.get('id') else None,
#                 'pdf_url': pdf_url,
#                 'citation_count': work.get('cited_by_count', 0),
#                 'reference_count': None,  # OpenAlex不直接提供
#                 'latex_content': None,
#                 # OpenAlex特有字段
#                 'open_access': {
#                     'is_oa': is_oa,
#                     'oa_status': oa_info.get('oa_status', 'closed'),
#                     'oa_url': oa_url
#                 },
#                 'full_text_locations': {
#                     'pdf_url': pdf_url,
#                     'landing_page_url': landing_url
#                 },
#                 'topics': topics,
#                 'arxiv_id': arxiv_id,
#                 'keywords': [kw.get('display_name', '') for kw in work.get('keywords', [])]
#             }
#         except Exception as e:
#             print(f"  解析OpenAlex论文数据时出错: {e}")
#             return None
class OpenAlexClient:
    """
    OpenAlex API客户端，用于搜索论文并获取元数据
    增加了超时控制、重试机制和错误处理
    """

    def __init__(self, email: str = None):
        """
        Args:
            email: 用于OpenAPI礼貌请求的邮箱地址（推荐提供，否则可能无法获取摘要）
        """
        self.base_url = "https://api.openalex.org"
        self.max_retries = 3
        self.base_timeout = 60
        self.retry_delay = 5
        self.email = "....com" # 新增：存储邮箱地址

    def _make_request_with_retry(self, url: str, params: dict = None) -> Optional[requests.Response]:
        """（保持不变，同原有实现）"""
        import socket

        for attempt in range(self.max_retries):
            try:
                timeout = self.base_timeout * (1 + attempt * 0.5)
                response = requests.get(url, params=params, timeout=timeout)

                if response.status_code == 200:
                    return response
                elif response.status_code == 429:
                    wait_time = 60 * (attempt + 1)
                    print(f"  OpenAlex速率限制，等待{wait_time}秒后重试... (尝试 {attempt + 1}/{self.max_retries})")
                    time.sleep(wait_time)
                    continue
                else:
                    print(f"  OpenAlex API错误: 状态码 {response.status_code}")
                    if attempt < self.max_retries - 1:
                        print(f"  等待{self.retry_delay}秒后重试... (尝试 {attempt + 1}/{self.max_retries})")
                        time.sleep(self.retry_delay)
                        continue
                    return None

            except requests.exceptions.Timeout:
                print(f"  请求超时 (尝试 {attempt + 1}/{self.max_retries})")
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (attempt + 1)
                    print(f"  等待{wait_time}秒后重试...")
                    time.sleep(wait_time)
                    continue
                return None

            except requests.exceptions.ConnectionError as e:
                print(f"  连接错误 (尝试 {attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (attempt + 1)
                    print(f"  等待{wait_time}秒后重试...")
                    time.sleep(wait_time)
                    continue
                return None

            except socket.timeout:
                print(f"  Socket超时 (尝试 {attempt + 1}/{self.max_retries})")
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (attempt + 1)
                    print(f"  等待{wait_time}秒后重试...")
                    time.sleep(wait_time)
                    continue
                return None

            except Exception as e:
                print(f"  请求出错: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                    continue
                return None

        print(f"  已达到最大重试次数({self.max_retries})")
        return None

    def search_papers(self, query: str, max_results: int = 50, sort: str = "cited_by_count:desc") -> List[Dict]:
        """
        通过OpenAlex搜索论文并获取丰富元数据
        如果初始化时提供了email，请求中会自动添加mailto参数以获取摘要
        """
        papers = []
        try:
            url = f"{self.base_url}/works"
            params = {
                'search': query,
                'per-page': min(max_results, 200),
                'sort': sort
            }

            # 新增：如果提供了邮箱，则添加到请求参数中（OpenAlex要求以获取慢速字段如摘要）
            if self.email:
                params['mailto'] = self.email
            else:
                print("  [警告] 未提供邮箱地址，可能无法获取摘要。建议在初始化时传入email参数。")

            print(f"  正在通过OpenAlex搜索: {query}...")

            response = self._make_request_with_retry(url, params)
            if response is None:
                print(f"  OpenAlex搜索失败: 多次重试后仍无法连接")
                return papers

            data = response.json()
            results = data.get('results', [])

            if not results:
                print(f"  OpenAlex未找到相关论文")
                return papers

            print(f"  OpenAlex返回 {len(results)} 篇论文")
            for i, work in enumerate(results, 1):
                try:
                    paper_info = self._parse_openalex_paper(work)
                    if paper_info:
                        papers.append(paper_info)
                        print(f"  找到论文 [{i}]: {paper_info['title'][:60]}...")
                        if paper_info.get('citation_count') is not None:
                            print(f"    引用数: {paper_info['citation_count']}")
                        # 新增：显示摘要长度以便调试
                        if paper_info.get('summary'):
                            print(f"    摘要长度: {len(paper_info['summary'])} 字符")

                    if i < len(results):
                        time.sleep(1.0)

                except Exception as e:
                    print(f"  解析论文时出错: {e}")
                    continue

            if papers:
                print(f"  成功获取 {len(papers)} 篇论文")
            else:
                print(f"  未能解析任何论文")

        except Exception as e:
            print(f"  OpenAlex搜索失败: {e}")
            print(f"  建议: 检查网络连接，或稍后重试")

        return papers

    def _parse_abstract_inverted_index(self, inverted_index: Dict) -> str:
        """
        将OpenAlex返回的倒排索引摘要解析为纯文本
        示例输入: {"This": [0], "is": [1], "an": [2], "example": [3], "abstract": [4]}
        输出: "This is an example abstract"
        """
        if not inverted_index:
            return ""
        # 确定最大位置，初始化单词列表
        max_pos = 0
        for positions in inverted_index.values():
            if positions:
                max_pos = max(max_pos, max(positions))
        words = [""] * (max_pos + 1)
        for word, positions in inverted_index.items():
            for pos in positions:
                # 防止索引越界（理论上不会，但稳健起见）
                if 0 <= pos < len(words):
                    words[pos] = word
        return " ".join(words)

    def _parse_openalex_paper(self, work: Dict) -> Optional[Dict]:
        """
        解析OpenAlex返回的论文数据，转换为统一格式
        现在会从abstract_inverted_index解析摘要并存入summary字段
        """
        try:
            # 提取开放获取信息
            oa_info = work.get('open_access', {})
            is_oa = oa_info.get('oa_status', 'closed') != 'closed'
            oa_url = oa_info.get('oa_url')

            # 提取全文位置信息
            locations = work.get('locations', [])
            pdf_url = None
            landing_url = None

            for location in locations:
                if location.get('pdf_url'):
                    pdf_url = location['pdf_url']
                if location.get('landing_page_url'):
                    landing_url = location['landing_page_url']

            # 提取主题信息
            topics = [topic.get('display_name', '') for topic in work.get('topics', [])[:5]]

            # 提取作者信息
            authors_list = []
            for authorship in work.get('authorships', []):
                author = authorship.get('author', {})
                if author:
                    authors_list.append(author.get('display_name', ''))

            # 提取DOI
            doi = work.get('doi')
            if doi and doi.startswith('https://doi.org/'):
                doi = doi.replace('https://doi.org/', '')

            # 提取Arxiv ID（如果有）
            arxiv_id = None
            primary_location = work.get('primary_location', {})
            if primary_location:
                source = primary_location.get('source', {})
                if source and 'arxiv' in source.get('display_name', '').lower():
                    landing = primary_location.get('landing_page_url', '')
                    arxiv_match = re.search(r'arxiv\.org/abs/(\d+\.\d+)', landing)
                    if arxiv_match:
                        arxiv_id = arxiv_match.group(1)

            # 提取发表信息
            venue = None
            if work.get('primary_location', {}).get('source'):
                venue = work.get('primary_location', {}).get('source', {}).get('display_name', '')

            publication_date = work.get('publication_date', '')
            publication_year = work.get('publication_year')

            # 新增：解析摘要（如果存在）
            inverted_index = work.get('abstract_inverted_index')
            summary = self._parse_abstract_inverted_index(inverted_index) if inverted_index else ""

            return {
                'title': work.get('title', ''),
                'authors': authors_list[:10],
                'published': publication_date,
                'publication_year': publication_year,
                'summary': summary,  # 现在包含真实摘要文本
                'doi': doi,
                'venue': venue or 'Unknown',
                'source': 'openalex',
                'paper_id': work.get('id', '').replace('https://openalex.org/', '') if work.get('id') else None,
                'entry_id': work.get('id', '') if work.get('id') else None,
                'pdf_url': pdf_url,
                'citation_count': work.get('cited_by_count', 0),
                'reference_count': None,
                'latex_content': None,
                # OpenAlex特有字段
                'open_access': {
                    'is_oa': is_oa,
                    'oa_status': oa_info.get('oa_status', 'closed'),
                    'oa_url': oa_url
                },
                'full_text_locations': {
                    'pdf_url': pdf_url,
                    'landing_page_url': landing_url
                },
                'topics': topics,
                'arxiv_id': arxiv_id,
                'keywords': [kw.get('display_name', '') for kw in work.get('keywords', [])]
            }
        except Exception as e:
            print(f"  解析OpenAlex论文数据时出错: {e}")
            return None
class FullTextDownloader:
    """
    智能全文下载器，根据论文元数据尝试获取LaTeX/XML全文内容
    """
    def __init__(self):
        self.priority_sources = ['arxiv', 'pubmed', 'acl', 'openreview']
    
    def smart_get_fulltext(self, paper_metadata: Dict) -> Dict:
        """
        根据论文元数据智能获取全文内容
        
        Args:
            paper_metadata: 论文元数据字典
        
        Returns:
            包含content_type, content, source, reason的字典
        """
        content_type = None
        fulltext_content = None
        source = None
        reason = None
        
        # 只有开放获取论文才尝试下载全文
        open_access = paper_metadata.get('open_access', {})
        if isinstance(open_access, dict):
            is_oa = open_access.get('is_oa', False)
        else:
            # 兼容旧格式
            is_oa = paper_metadata.get('source') == 'arxiv'  # Arxiv默认开放获取
        
        if not is_oa and paper_metadata.get('source') != 'arxiv':
            return {
                'content_type': 'metadata_only',
                'content': None,
                'source': None,
                'reason': '非开放获取论文'
            }
        
        # 策略1: 尝试从arXiv获取LaTeX源码
        arxiv_content = self._try_get_arxiv_content(paper_metadata)
        if arxiv_content:
            return {
                'content_type': 'latex',
                'content': arxiv_content,
                'source': 'arxiv',
                'reason': '成功获取LaTeX源码'
            }
        
        # 策略2: 尝试从PubMed Central获取XML
        pmc_content = self._try_get_pmc_content(paper_metadata)
        if pmc_content:
            return {
                'content_type': 'xml',
                'content': pmc_content,
                'source': 'pmc',
                'reason': '成功获取XML全文'
            }
        
        # 策略3: 尝试从ACL Anthology获取LaTeX
        acl_content = self._try_get_acl_content(paper_metadata)
        if acl_content:
            return {
                'content_type': 'latex',
                'content': acl_content,
                'source': 'acl',
                'reason': '成功获取ACL LaTeX源码'
            }
        
        # 策略4: 如果有PDF链接，可以尝试PDF解析（可选，需要pymupdf）
        pdf_url = paper_metadata.get('pdf_url') or \
                  (paper_metadata.get('full_text_locations', {}).get('pdf_url') if isinstance(paper_metadata.get('full_text_locations'), dict) else None)
        if pdf_url :
            pdf_text = extract_text_from_ieee_pdf_url(pdf_url)
            if pdf_text:
                return {
                    'content_type': 'pdf_text',
                    'content': pdf_text,
                    'source': 'pdf_parser',
                    'reason': '从PDF解析文本'
                }
        
        # 所有方法都失败，回退到仅使用元数据
        return {
            'content_type': 'metadata_only',
            'content': None,
            'source': None,
            'reason': '无法获取全文内容'
        }
    
    def _try_get_arxiv_content(self, paper_metadata: Dict) -> Optional[str]:
        """尝试从arXiv获取LaTeX源码"""
        try:
            # 检查是否有arxiv_id
            arxiv_id = paper_metadata.get('arxiv_id')
            if not arxiv_id:
                # 尝试从entry_id或DOI提取
                entry_id = paper_metadata.get('entry_id', '')
                if 'arxiv' in entry_id.lower():
                    arxiv_match = re.search(r'arxiv\.org/abs/(\d+\.\d+)', entry_id)
                    if arxiv_match:
                        arxiv_id = arxiv_match.group(1)
                
                if not arxiv_id:
                    doi = paper_metadata.get('doi', '')
                    if 'arxiv' in doi.lower():
                        arxiv_match = re.search(r'arxiv\.(\d+\.\d+)', doi)
                        if arxiv_match:
                            arxiv_id = arxiv_match.group(1)
            
            if arxiv_id:
                # 使用现有的get_paper_latex_content函数
                latex_content = get_paper_latex_content(f"http://arxiv.org/abs/{arxiv_id}")
                if latex_content:
                    return latex_content
        except Exception as e:
            print(f"    获取arXiv内容失败: {e}")
        return None
    
    def _try_get_pmc_content(self, paper_metadata: Dict) -> Optional[str]:
        """尝试从PubMed Central获取XML全文"""
        try:
            doi = paper_metadata.get('doi')
            if not doi:
                return None
            
            # 通过PMC API获取XML内容
            # 首先需要通过DOI获取PMC ID
            pmc_id = self._get_pmc_id_by_doi(doi)
            if pmc_id:
                # 下载PMC全文XML
                pmc_url = f"https://www.ncbi.nlm.nih.gov/pmc/oai/oai.cgi?verb=GetRecord&identifier=oai:pubmedcentral.nih.gov:{pmc_id}&metadataPrefix=pmc"
                response = requests.get(pmc_url, timeout=30)
                if response.status_code == 200:
                    # 这里需要解析XML，简化处理
                    return response.text[:50000]  # 限制长度
        except Exception as e:
            print(f"    获取PMC内容失败: {e}")
        return None
    
    def _get_pmc_id_by_doi(self, doi: str) -> Optional[str]:
        """通过DOI获取PMC ID"""
        try:
            url = f"https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/?ids={doi}&format=json"
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                data = response.json()
                records = data.get('records', [])
                if records and records[0].get('pmcid'):
                    return records[0]['pmcid'].replace('PMC', '')
        except Exception as e:
            pass
        return None
    
    def _try_get_acl_content(self, paper_metadata: Dict) -> Optional[str]:
        """尝试从ACL Anthology获取LaTeX源码"""
        try:
            # 检查是否是ACL相关会议
            title = paper_metadata.get('title', '').lower()
            venue = paper_metadata.get('venue', '').lower()
            topics = paper_metadata.get('topics', [])
            
            acl_keywords = ['acl', 'emnlp', 'naacl', 'eacl', 'computational linguistics', 'natural language processing']
            if any(keyword in title for keyword in acl_keywords) or \
               any(keyword in venue for keyword in acl_keywords) or \
               any(topic.lower() in acl_keywords for topic in topics if isinstance(topic, str)):
                # ACL Anthology通常可以通过DOI或标题搜索
                # 这里简化处理，实际需要访问ACL Anthology API
                pass
        except Exception as e:
            print(f"    获取ACL内容失败: {e}")
        return None
    
    def _is_trusted_pdf_source(self, pdf_url: str) -> bool:
        """判断是否是可信的PDF源"""
        trusted_domains = ['arxiv.org', 'pubmedcentral.nih.gov', 'aclweb.org', 'openreview.net']
        return any(domain in pdf_url.lower() for domain in trusted_domains)
    
    def _try_parse_pdf(self, pdf_url: str) -> Optional[str]:
        """尝试从PDF URL解析文本内容（需要pymupdf库）"""
        try:
            try:
                import pymupdf  # PyMuPDF
            except ImportError:
                # 如果没有安装pymupdf，跳过PDF解析
                return None
            
            import io
            response = requests.get(pdf_url, timeout=30)
            if response.status_code == 200:
                pdf_data = io.BytesIO(response.content)
                doc = pymupdf.open(stream=pdf_data, filetype="pdf")
                text = ""
                for page in doc:
                    text += page.get_text()
                return text if len(text) > 100 else None  # 确保有足够内容
        except Exception as e:
            print(f"    PDF解析失败: {e}")
        return None
import pdfplumber
import io
from typing import Optional

def extract_text_from_pdf_url(url: str,
                              remove_header_footer: bool = True,
                              header_ratio: float = 0.1,
                              footer_ratio: float = 0.1) -> Optional[str]:
    """
    从给定的 URL 下载 PDF 文件，并使用 pdfplumber 提取其中的文本内容。

    参数:
        url (str): PDF 文件的网络地址。
        remove_header_footer (bool): 是否尝试去除页眉页脚（基于页面高度比例）。
        header_ratio (float): 页面顶部被视为页眉的比例（例如 0.1 表示顶部 10%）。
        footer_ratio (float): 页面底部被视为页脚的比例（例如 0.1 表示底部 10%）。

    返回:
        Optional[str]: 提取到的文本内容，如果失败则返回 None。
    """
    try:
        # 1. 从 URL 下载 PDF 内容
        response = requests.get(url, timeout=30)
        response.raise_for_status()  # 检查请求是否成功

        # 2. 将内容包装成字节流，供 pdfplumber 直接读取
        pdf_file = io.BytesIO(response.content)

        # 3. 使用 pdfplumber 打开 PDF
        full_text = []
        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                # 获取页面尺寸，用于裁剪页眉页脚
                if remove_header_footer and page.height:
                    # 计算裁剪区域：去除顶部和底部指定比例的区域
                    crop_box = (
                        0,                          # x0
                        page.height * footer_ratio, # y0 (底部切除后剩下的 y 起点)
                        page.width,                 # x1
                        page.height * (1 - header_ratio)  # y1 (顶部切除后的 y 终点)
                    )
                    # 注意：pdfplumber 的坐标原点在页面左上角，y 轴向下
                    # 上面定义的 crop_box 为 (left, top, right, bottom)，
                    # 但 pdfplumber 的 crop() 方法期望的边界是 (x0, top, x1, bottom)，
                    # 其中 top 和 bottom 是相对于页面顶部的距离。
                    # 为了切除顶部 header_ratio 区域，我们需要设置 top = header_ratio * height，
                    # 为了切除底部 footer_ratio 区域，我们需要设置 bottom = (1 - footer_ratio) * height。
                    # 重新计算更直观：
                    top = page.height * header_ratio
                    bottom = page.height * (1 - footer_ratio)
                    cropped_page = page.within_bbox((0, top, page.width, bottom))
                else:
                    cropped_page = page

                # 提取当前页文本
                page_text = cropped_page.extract_text()
                if page_text:
                    full_text.append(page_text)

        # 4. 合并所有页文本（可在此添加更多后处理，如合并断词、段落重组等）
        result = "\n".join(full_text)
        return result

    except requests.exceptions.RequestException as e:
        print(f"下载 PDF 失败: {e}")
        return None
    except Exception as e:
        print(f"解析 PDF 时出错: {e}")
        return None

def extract_text_from_ieee_pdf_url(pdf_url: str,
                                   cookies: Optional[dict] = None,
                                   headers: Optional[dict] = None,
                                   remove_header_footer: bool = True,
                                   header_ratio: float = 0.1,
                                   footer_ratio: float = 0.1) -> Optional[str]:
    """
    从 IEEE Xplore PDF 链接下载 PDF 并提取文本内容，使用模拟浏览器请求头。

    参数:
        pdf_url (str): IEEE 论文的 PDF 链接，例如
                       "https://ieeexplore.ieee.org/document/xxxxxx"
                       或直接 PDF 文件链接。
        cookies (dict, optional): 包含登录信息的 Cookies 字典，用于访问需要订阅的论文。
        headers (dict, optional): 自定义请求头，若不提供则使用默认模拟浏览器的请求头。
        remove_header_footer (bool): 是否尝试去除页眉页脚（基于页面高度比例）。
        header_ratio (float): 页面顶部被视为页眉的比例（例如 0.1 表示顶部 10% 被切除）。
        footer_ratio (float): 页面底部被视为页脚的比例（例如 0.1 表示底部 10% 被切除）。

    返回:
        Optional[str]: 提取到的文本内容，如果失败则返回 None。
    """
    # 默认请求头，模拟主流浏览器
    default_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Cache-Control': 'max-age=0',
    }
    if headers:
        default_headers.update(headers)

    # 创建会话并设置 cookies（如果提供）
    session = requests.Session()
    if cookies:
        session.cookies.update(cookies)

    try:
        # 发起 GET 请求，获取 PDF 内容
        response = session.get(pdf_url, headers=default_headers, timeout=30)
        response.raise_for_status()

        # 可选：检查内容类型是否为 PDF
        content_type = response.headers.get('Content-Type', '')
        if 'application/pdf' not in content_type and not response.content[:4] == b'%PDF':
            print("警告: 下载的内容可能不是 PDF 文件，但仍尝试解析。")

        # 将内容包装为字节流供 pdfplumber 读取
        pdf_file = io.BytesIO(response.content)

        # 使用 pdfplumber 提取文本
        full_text = []
        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                if remove_header_footer and page.height:
                    # 计算裁剪区域：切除顶部 header_ratio 和底部 footer_ratio
                    top = page.height * header_ratio
                    bottom = page.height * (1 - footer_ratio)
                    cropped_page = page.within_bbox((0, top, page.width, bottom))
                else:
                    cropped_page = page

                page_text = cropped_page.extract_text()
                if page_text:
                    full_text.append(page_text)

        return "\n".join(full_text) if full_text else None

    except requests.exceptions.RequestException as e:
        print(f"下载 PDF 失败: {e}")
        return None
    except Exception as e:
        print(f"解析 PDF 时出错: {e}")
        return None
def search_openalex_papers(keyword, max_results=50, include_details=False, latest_count=6, cited_count=14):
    """
    使用OpenAlex API搜索相关论文
    支持分别搜索最新日期和最高引用的论文
    
    Args:
        keyword: 搜索关键词
        max_results: 最大返回数量（如果latest_count和cited_count都指定，则忽略此参数）
        include_details: 是否获取详细信息（OpenAlex默认包含详细信息）
        latest_count: 搜索最新日期的论文数量（默认6篇）
        cited_count: 搜索最高引用的论文数量（默认14篇）
    
    Returns:
        论文列表
    """
    client = OpenAlexClient()
    papers = []
    
    # 如果指定了latest_count和cited_count，分别搜索
    if latest_count > 0:
        print(f"  搜索最新日期的论文（{latest_count}篇）...")
        latest_papers = client.search_papers(keyword, max_results=latest_count, sort="publication_date:desc")
        papers.extend(latest_papers)
        print(f"  找到 {len(latest_papers)} 篇最新日期的论文")
    
    if cited_count > 0:
        print(f"  搜索最高引用的论文（{cited_count}篇）...")
        cited_papers = client.search_papers(keyword, max_results=cited_count, sort="cited_by_count:desc")
        papers.extend(cited_papers)
        print(f"  找到 {len(cited_papers)} 篇最高引用的论文")
    
    # 如果都没有指定，使用原来的逻辑
    if latest_count == 0 and cited_count == 0:
        papers = client.search_papers(keyword, max_results=max_results)
    
    return papers

def merge_and_deduplicate_papers(arxiv_papers, semantic_papers, openalex_papers=None):
    """
    合并Arxiv、Semantic Scholar和OpenAlex的搜索结果，并去除重复论文
    
    Args:
        arxiv_papers: Arxiv论文列表
        semantic_papers: Semantic Scholar论文列表
        openalex_papers: OpenAlex论文列表（可选）
    
    Returns:
        合并去重后的论文列表
    """
    all_papers = []
    seen_papers: Set[str] = set()
    duplicate_count = 0
    
    # 先添加Arxiv的论文
    for paper in arxiv_papers:
        unique_id = get_paper_unique_id(paper)
        if unique_id not in seen_papers:
            seen_papers.add(unique_id)
            all_papers.append(paper)
        else:
            duplicate_count += 1
            print(f"  去重: 跳过重复论文 - {paper['title']}")
    
    # 再添加Semantic Scholar的论文（去重）
    for paper in semantic_papers:
        unique_id = get_paper_unique_id(paper)
        if unique_id not in seen_papers:
            seen_papers.add(unique_id)
            all_papers.append(paper)
        else:
            duplicate_count += 1
            print(f"  去重: 跳过重复论文 - {paper['title']}")
    
    # 最后添加OpenAlex的论文（去重）
    if openalex_papers:
        for paper in openalex_papers:
            unique_id = get_paper_unique_id(paper)
            if unique_id not in seen_papers:
                seen_papers.add(unique_id)
                all_papers.append(paper)
            else:
                duplicate_count += 1
                print(f"  去重: 跳过重复论文 - {paper['title']}")
    
    if duplicate_count > 0:
        print(f"\n  去重统计: 共发现 {duplicate_count} 篇重复论文，已自动去除")
    
    return all_papers

def parse_latex_to_text(latex_content):
    """
    将LaTeX源码解析为可读的文本内容
    提取章节标题、正文、公式说明等，去除LaTeX命令
    """
    if not latex_content:
        return None
    
    # 提取主要.tex文件的内容（通常是主文件）
    main_content = latex_content
    
    # 1. 提取标题
    title_match = re.search(r'\\title\{(.*?)\}', main_content, re.DOTALL)
    title = title_match.group(1).strip() if title_match else ""
    # 清理标题中的LaTeX命令
    title = re.sub(r'\\[a-zA-Z]+\{([^}]*)\}', r'\1', title)
    title = re.sub(r'\\[a-zA-Z]+', '', title)
    
    # 2. 提取摘要
    abstract_match = re.search(r'\\begin\{abstract\}(.*?)\\end\{abstract\}', main_content, re.DOTALL)
    abstract = abstract_match.group(1).strip() if abstract_match else ""
    
    # 3. 提取章节结构
    sections = []
    # 查找所有section、subsection等
    section_pattern = r'\\(sub)?section\*?\{([^}]+)\}'
    for match in re.finditer(section_pattern, main_content):
        section_type = "小节" if match.group(1) else "章节"
        section_title = match.group(2).strip()
        sections.append(f"{section_type}: {section_title}")
    
    # 4. 提取正文内容（去除LaTeX命令）
    # 移除注释
    text = re.sub(r'%.*?\n', '\n', main_content)
    # 移除LaTeX命令（保留参数内容）
    text = re.sub(r'\\[a-zA-Z]+\{([^}]*)\}', r'\1', text)
    text = re.sub(r'\\[a-zA-Z]+', '', text)
    # 移除环境标签但保留内容
    text = re.sub(r'\\begin\{[^}]+\}', '', text)
    text = re.sub(r'\\end\{[^}]+\}', '', text)
    # 移除标签和引用
    text = re.sub(r'\\label\{[^}]+\}', '', text)
    text = re.sub(r'\\cite\{[^}]+\}', '[引用]', text)
    text = re.sub(r'\\ref\{[^}]+\}', '[引用]', text)
    # 移除公式环境（保留公式说明）
    text = re.sub(r'\$.*?\$', '[公式]', text)
    text = re.sub(r'\\begin\{equation\}.*?\\end\{equation\}', '[公式]', text, flags=re.DOTALL)
    # 清理多余空白
    text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
    text = re.sub(r' {2,}', ' ', text)
    
    # 提取前10000字符作为主要文本内容
    main_text = text[:10000].strip()
    
    # 5. 构建结构化输出
    parsed_content = ""
    if title:
        parsed_content += f"标题: {title}\n\n"
    if abstract:
        parsed_content += f"摘要: {abstract}\n\n"
    if sections:
        parsed_content += f"论文结构:\n" + "\n".join(sections[:10]) + "\n\n"
    if main_text:
        parsed_content += f"主要文本内容:\n{main_text}\n"
    
    return parsed_content if parsed_content.strip() else None

def extract_arxiv_id(entry_id):
    """
    从entry_id中提取Arxiv ID，处理可能包含版本号的情况
    例如：http://arxiv.org/abs/1234.5678v1 -> 1234.5678
    """
    if not entry_id:
        return None
    # 提取最后一个路径段
    arxiv_id = entry_id.split('/')[-1]
    # 移除版本号（如v1, v2等）
    if 'v' in arxiv_id and arxiv_id[-1].isdigit():
        # 找到最后一个v的位置
        last_v = arxiv_id.rfind('v')
        if last_v > 0:
            arxiv_id = arxiv_id[:last_v]
    return arxiv_id

def get_citation_count_for_arxiv_paper(paper_info):
    """
    为Arxiv论文查找引用次数（通过Semantic Scholar API）
    使用Arxiv ID或标题+作者进行搜索
    """
    try:
        # 首先尝试使用Arxiv ID查找
        arxiv_id = None
        if paper_info.get('entry_id'):
            # 从entry_id提取Arxiv ID（格式：http://arxiv.org/abs/1234.5678）
            arxiv_id = extract_arxiv_id(paper_info['entry_id'])
        
        # 方法1: 如果有Arxiv ID，直接通过Arxiv ID查找
        if arxiv_id:
            try:
                # Semantic Scholar支持通过Arxiv ID查找
                url = f"https://api.semanticscholar.org/graph/v1/paper/arXiv:{arxiv_id}"
                params = {
                    'fields': 'citationCount,referenceCount'
                }
                response = make_semantic_scholar_request(url, params=params)
                if response:
                    data = response.json()
                    citation_count = data.get('citationCount', 0)
                    if citation_count is not None:
                        return citation_count
            except Exception as e:
                # 静默失败，继续尝试其他方法
                pass
        
        # 方法2: 通过标题搜索（如果Arxiv ID方法失败）
        title = paper_info.get('title', '')
        if title:
            try:
                url = "https://api.semanticscholar.org/graph/v1/paper/search"
                params = {
                    'query': title,
                    'limit': 5,
                    'fields': 'title,authors,citationCount'
                }
                response = make_semantic_scholar_request(url, params=params)
                if response:
                    data = response.json()
                    papers_data = data.get('data', [])
                    # 尝试匹配标题
                    for match in papers_data:
                        if match.get('title', '').lower() == title.lower():
                            citation_count = match.get('citationCount', 0)
                            if citation_count is not None:
                                return citation_count
            except Exception as e:
                # 静默失败，继续返回None
                pass
    except Exception as e:
        print(f"  获取引用次数时出错: {e}")
    
    return None

def enrich_papers_with_citations(papers):
    """
    为论文补充引用次数信息
    仅对 OpenAlex 与 Semantic Scholar 来源的论文进行处理；跳过 Arxiv。
    """
    print("\n正在获取论文引用次数信息（仅OpenAlex与Semantic Scholar，跳过Arxiv）...")
    processed = 0
    for i, paper in enumerate(papers):
        source = (paper.get('source') or '').lower()
        # 跳过 Arxiv 来源
        if source == 'arxiv':
            # 若无引用次数字段，统一初始化为0，避免后续使用时报错
            if paper.get('citation_count') is None:
                paper['citation_count'] = 0
            continue
        # 仅处理 OpenAlex 与 Semantic Scholar
        if source in ('openalex', 'semantic_scholar', 'semanticscholar'):
            # 避免不必要的外部请求：若已携带引用次数则标准化类型后跳过
            if paper.get('citation_count') is not None:
                try:
                    paper['citation_count'] = int(paper['citation_count']) or 0
                except Exception:
                    paper['citation_count'] = 0
                continue
            # Semantic Scholar 可能需要补充细节
            if source in ('semantic_scholar', 'semanticscholar') and paper.get('paper_id'):
                details = get_semantic_scholar_paper_details(paper['paper_id'])
                if details:
                    citation_count = details.get('citationCount', 0)
                    paper['citation_count'] = citation_count if citation_count is not None else 0
                    reference_count = details.get('referenceCount', 0)
                    paper['reference_count'] = reference_count if reference_count is not None else 0
                    print(f"  ✓ {paper['title'][:50]}... 引用数: {paper['citation_count']}")
                else:
                    paper['citation_count'] = 0
            else:
                # OpenAlex 通常已包含引用数；若无则设为0
                paper['citation_count'] = int(paper.get('citation_count') or 0)
            processed += 1
        else:
            # 其他来源统一不查询，规范化字段
            if paper.get('citation_count') is None:
                paper['citation_count'] = 0
    if processed == 0:
        print("  - 未发现需要获取引用次数的论文（OpenAlex/Semantic Scholar）。")
    return papers

def filter_papers_by_criteria(papers, top_by_date=5, top_by_citations=5, min_citations=10):
    """
    根据最新日期和引用次数筛选论文
    
    Args:
        papers: 论文列表
        top_by_date: 按最新日期选择前N篇
        top_by_citations: 按引用次数选择前N篇（即使日期不新）
        min_citations: 高引用论文的最低引用数阈值
    
    Returns:
        (latest_papers, high_citation_papers, all_selected)
        latest_papers: 按日期筛选的论文
        high_citation_papers: 按引用次数筛选的论文
        all_selected: 合并去重后的所有选中论文
    """
    # 解析日期
    def parse_date(date_str):
        if not date_str:
            return datetime(1900, 1, 1)
        try:
            # 尝试多种日期格式
            if isinstance(date_str, str):
                # YYYY-MM-DD格式
                if '-' in date_str and len(date_str) >= 10:
                    return datetime.strptime(date_str[:10], '%Y-%m-%d')
                # YYYY格式
                elif date_str.isdigit() and len(date_str) == 4:
                    return datetime(int(date_str), 1, 1)
            return datetime(1900, 1, 1)
        except (ValueError, TypeError) as e:
            # 日期解析失败，返回默认日期
            return datetime(1900, 1, 1)
    
    # 为每篇论文计算解析后的日期和引用次数（不修改原数据）
    papers_with_metadata = []
    for paper in papers:
        paper_copy = paper.copy()  # 创建副本以避免污染原数据
        paper_copy['_parsed_date'] = parse_date(paper.get('published', ''))
        paper_copy['_citation_count'] = int(paper.get('citation_count', 0) or 0)
        papers_with_metadata.append(paper_copy)
    
    # 1. 按最新日期筛选
    sorted_by_date = sorted(papers_with_metadata, key=lambda x: x['_parsed_date'], reverse=True)
    latest_papers = [p.copy() for p in sorted_by_date[:top_by_date]]
    # 移除临时字段
    for p in latest_papers:
        p.pop('_parsed_date', None)
        p.pop('_citation_count', None)
    
    # 2. 按引用次数筛选（排除已在最新日期列表中的）
    latest_ids = {get_paper_unique_id(p) for p in latest_papers}
    remaining_papers = [p for p in papers_with_metadata if get_paper_unique_id(p) not in latest_ids]
    
    # 筛选高引用论文（引用数 >= min_citations）
    high_citation_papers = [p for p in remaining_papers if p['_citation_count'] >= min_citations]
    high_citation_papers = sorted(high_citation_papers, key=lambda x: x['_citation_count'], reverse=True)[:top_by_citations]
    # 移除临时字段
    for p in high_citation_papers:
        p.pop('_parsed_date', None)
        p.pop('_citation_count', None)
    
    # 3. 合并去重
    all_selected = []
    seen_ids = set()
    for paper in latest_papers + high_citation_papers:
        unique_id = get_paper_unique_id(paper)
        if unique_id not in seen_ids:
            seen_ids.add(unique_id)
            all_selected.append(paper)
    
    return latest_papers, high_citation_papers, all_selected

def display_papers_for_selection(papers, category_name=""):
    """
    显示论文列表供用户选择
    """
    if not papers:
        return []
    
    print(f"\n{'='*80}")
    if category_name:
        print(f"{category_name} ({len(papers)}篇)")
    print(f"{'='*80}")
    
    for i, paper in enumerate(papers, 1):
        print(f"\n[{i}] {paper.get('title', '未知标题')}")
        authors = paper.get('authors') or []
        print(f"    作者: {', '.join(authors[:3]) if authors else '未知'}")
        print(f"    发表时间: {paper.get('published', '未知')}")
        if paper.get('citation_count') is not None:
            print(f"    引用数: {paper['citation_count']}")
        if paper.get('venue'):
            print(f"    来源: {paper['venue']} ({paper.get('source', 'unknown')})")
        summary = paper.get('summary')
        if summary and isinstance(summary, str):
            summary_display = summary[:150] + "..." if len(summary) > 150 else summary
            print(f"    摘要: {summary_display}")
    
    print(f"\n{'='*80}")
    print(f"请选择要包含在综述中的论文（输入编号，多个用逗号分隔，如：1,3,5，或输入 'all' 选择全部）:")
    choice = input().strip()
    
    if not choice:
        print("未输入任何内容，未选择任何论文")
        return []
    
    if choice.lower() == 'all':
        return papers
    else:
        try:
            indices = [int(x.strip()) - 1 for x in choice.split(',') if x.strip().isdigit()]
            if not indices:
                print("输入格式错误，未选择任何论文")
                return []
            selected = [papers[i] for i in indices if 0 <= i < len(papers)]
            if len(selected) < len(indices):
                print(f"警告：部分编号无效（有效范围：1-{len(papers)}）")
            return selected
        except (ValueError, IndexError) as e:
            print(f"输入格式错误，未选择任何论文: {e}")
            return []

def get_paper_latex_content(paper_id):
    """
    获取论文的LaTeX源码内容并解析为可读文本
    """
    try:
        # 从entry_id中提取arxiv ID（格式：http://arxiv.org/abs/1234.5678）
        arxiv_id = extract_arxiv_id(paper_id)
        if not arxiv_id:
            print(f"  无法从entry_id提取Arxiv ID: {paper_id}")
            return None
        
        # Arxiv的LaTeX源码URL
        latex_url = f"https://arxiv.org/e-print/{arxiv_id}"
        
        print(f"正在下载LaTeX源码: {arxiv_id}...")
        
        # 下载LaTeX源码（通常是tar.gz格式）
        response = requests.get(latex_url, timeout=30)
        if response.status_code == 200:
            # 尝试解压并提取.tex文件内容
            try:
                tar_file = tarfile.open(fileobj=io.BytesIO(response.content))
                all_tex_content = ""
                main_tex_file = None
                
                # 首先查找主文件（通常是包含\documentclass的文件）
                for member in tar_file.getmembers():
                    if member.name.endswith('.tex') and member.isfile():
                        try:
                            file_content = tar_file.extractfile(member).read().decode('utf-8', errors='ignore')
                            if '\\documentclass' in file_content:
                                main_tex_file = file_content
                                print(f"  找到主文件: {member.name}")
                            all_tex_content += file_content + "\n\n"
                        except Exception as e:
                            print(f"  读取文件 {member.name} 时出错: {e}")
                
                tar_file.close()
                
                # 优先使用主文件，否则使用所有内容
                latex_source = main_tex_file if main_tex_file else all_tex_content
                
                if latex_source:
                    # 解析LaTeX为可读文本
                    print(f"  正在解析LaTeX内容...")
                    parsed_text = parse_latex_to_text(latex_source)
                    if parsed_text:
                        return parsed_text
                    else:
                        # 如果解析失败，返回原始内容的前20000字符
                        return latex_source[:20000]
                else:
                    return None
            except Exception as e:
                print(f"解压LaTeX源码时出错: {e}")
                return None
        else:
            print(f"下载LaTeX源码失败，状态码: {response.status_code}")
            return None
    except Exception as e:
        print(f"获取LaTeX源码时出错: {e}")
        return None

def filter_papers_for_review(all_papers, target_count, keyword):
    """
    根据目标数量筛选论文用于综述撰写

    Args:
        all_papers: 所有搜索到的论文列表
        target_count: 目标筛选出的论文数量
        keyword: 搜索关键词

    Returns:
        筛选后的论文列表
    """
    if not all_papers:
        return []

    if len(all_papers) <= target_count:
        print(f"论文数量({len(all_papers)})已小于等于目标数量({target_count})，使用所有论文")
        return all_papers

    print(f"\n正在筛选文献（从{len(all_papers)}篇中筛选出{target_count}篇用于综述）...")

    try:
        from openai import OpenAI
        from config import get_openai_config
        import re
        from datetime import datetime

        openai_config = get_openai_config()
        client = OpenAI(
            base_url=openai_config['base_url'],
            api_key=openai_config['api_key'],
            timeout=openai_config['timeout']
        )

        # 构建论文信息摘要
        papers_content = ""
        for i, paper in enumerate(all_papers, 1):
            title = paper.get('title') or '未知标题'
            authors = paper.get('authors') or []
            published = paper.get('published') or '未知'
            venue = paper.get('venue') or ''
            citation_count = paper.get('citation_count') or 0
            summary = paper.get('summary') or '无摘要'

            papers_content += f"\n[论文 {i}]\n"
            papers_content += f"标题: {title}\n"
            papers_content += f"作者: {', '.join(authors) if authors else '未知'}\n"
            papers_content += f"发表时间: {published}\n"
            if venue:
                papers_content += f"来源: {venue}\n"
            papers_content += f"引用数: {citation_count}\n"
            # 只包含摘要的前300字符
            if summary and isinstance(summary, str):
                summary_short = summary[:300] + "..." if len(summary) > 300 else summary
            else:
                summary_short = '无摘要'
            papers_content += f"摘要: {summary_short}\n"
            papers_content += "-" * 60 + "\n"

        system_prompt = f"""你是一位专业的学术研究助手，擅长筛选指定数量的高度符合综述主题的学术论文用以撰写综述。

筛选标准：
1. 优先选择与综述主题高度相关的论文（最重要）
2. 优先选择期刊质量较高的论文
3. 优先选择日期较新或引用次数较高的论文
4. 确保选择的文献能够全面覆盖综述的主要观点和技术方向
5. 综合考虑论文的相关性、重要性和代表性

请仔细分析每篇论文的信息，选择最适合用于撰写关于"{keyword}"综述的论文。"""

        user_prompt = f"""请从以下关于"{keyword}"的{len(all_papers)}篇论文中，筛选出最合适的{target_count}篇论文用于撰写学术综述。

筛选标准：
1. 优先选择与综述主题高度相关的论文（最重要）
2. 优先选择期刊质量较高的论文
3. 优先选择日期较新或引用次数较高的论文
4. 确保选择的文献能够全面覆盖综述的主要观点和技术方向
5. 综合考虑论文的相关性、重要性和代表性

请严格按照以下格式输出，只输出论文编号，用逗号分隔：
编号1,编号2,编号3,...

例如：1,3,5,7,9

论文列表：
{papers_content}

请输出筛选出的{target_count}篇论文的编号（用逗号分隔）："""

        response = client.chat.completions.create(
            model=openai_config['model'],
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt}
            ],
            stream=False,
            temperature=0.3,
            timeout=60
        )

        if response and response.choices and len(response.choices) > 0:
            result_text = response.choices[0].message.content.strip()

            try:
                numbers = re.findall(r'\d+', result_text)
                selected_indices = [int(n) - 1 for n in numbers]  # 转换为0-based索引

                valid_indices = [idx for idx in selected_indices if 0 <= idx < len(all_papers)]

                # 去重并保持顺序
                seen = set()
                unique_indices = []
                for idx in valid_indices:
                    if idx not in seen:
                        seen.add(idx)
                        unique_indices.append(idx)

                # 如果数量不足，补充高引用或新日期的论文
                if len(unique_indices) < target_count:
                    remaining = [i for i in range(len(all_papers)) if i not in unique_indices]
                    # 按引用数和日期排序
                    remaining_papers = [(i, all_papers[i]) for i in remaining]
                    remaining_papers.sort(key=lambda x: (
                        x[1].get('citation_count') or 0,
                        x[1].get('published', '') or ''
                    ), reverse=True)
                    needed = target_count - len(unique_indices)
                    for i, _ in remaining_papers[:needed]:
                        unique_indices.append(i)

                # 如果数量过多，只取前target_count个
                unique_indices = unique_indices[:target_count]

                selected_papers = [all_papers[i] for i in unique_indices]
                print(f"  ✓ 大模型筛选完成：从{len(all_papers)}篇中选出{len(selected_papers)}篇文献")
                return selected_papers

            except Exception as e:
                print(f"  解析大模型返回结果时出错: {e}，使用备用筛选方案")

        # 备用方案：按日期和引用次数综合排序
        return filter_papers_fallback(all_papers, target_count)

    except Exception as e:
        print(f"  筛选文献时出错: {e}，使用备用筛选方案")
        return filter_papers_fallback(all_papers, target_count)

def filter_papers_fallback(papers, target_count):
    """备用筛选方案：按日期和引用次数综合排序"""
    from datetime import datetime

    def parse_date(date_str):
        if not date_str:
            return datetime(1900, 1, 1)
        try:
            if isinstance(date_str, str):
                if '-' in date_str and len(date_str) >= 10:
                    return datetime.strptime(date_str[:10], '%Y-%m-%d')
                elif date_str.isdigit() and len(date_str) == 4:
                    return datetime(int(date_str), 1, 1)
            return datetime(1900, 1, 1)
        except (ValueError, TypeError):
            return datetime(1900, 1, 1)

    # 为每篇论文计算综合得分
    papers_with_score = []
    current_year = datetime.now().year

    for paper in papers:
        paper_copy = paper.copy()

        # 日期得分
        date = parse_date(paper.get('published', ''))
        if date.year >= current_year - 3:
            date_score = 100 - (current_year - date.year) * 10
        else:
            date_score = max(0, 70 - (current_year - 3 - date.year) * 5)

        # 引用得分
        citation_count = int(paper.get('citation_count', 0) or 0)
        if citation_count > 0:
            citation_score = min(100, 20 * (1 + (citation_count ** 0.5)))
        else:
            citation_score = 0

        # 综合得分：日期权重40%，引用权重60%
        total_score = date_score * 0.4 + citation_score * 0.6
        paper_copy['_score'] = total_score
        papers_with_score.append(paper_copy)

    # 按得分排序
    sorted_papers = sorted(papers_with_score, key=lambda x: x['_score'], reverse=True)

    # 移除临时字段并返回
    selected_papers = []
    for paper in sorted_papers[:target_count]:
        paper.pop('_score', None)
        selected_papers.append(paper)

    print(f"  ✓ 备用筛选完成：按日期和引用次数排序选出{len(selected_papers)}篇文献")
    return selected_papers


def filter_papers_two_stage(all_papers, reference_count, citation_count, keyword):
    """
    两步筛选法：从所有论文中筛选参考文献，再从参考文献中筛选引用文献

    新流程：
    1. 第一步筛选：从所有论文中筛选出 reference_count 篇参考文献（用于综述撰写）
    2. 第二步筛选：从参考文献中筛选出 citation_count 篇引用文献（用于文中详细引用叙述）
    3. 重排序：对引用文献按发表时间（最新在前）进行重排序，生成序号映射

    Args:
        all_papers: 所有搜索到的论文列表
        reference_count: 参考文献数量（用于综述撰写）
        citation_count: 引用文献数量（用于文中详细引用叙述）
        keyword: 搜索关键词

    Returns:
        tuple: (reference_papers, citation_papers, citation_index_mapping)
            - reference_papers: 参考文献列表（用于综述撰写）
            - citation_papers: 引用文献列表（按发表时间重排序，用于文中详细引用）
            - citation_index_mapping: 序号映射字典 {新序号(1-based): 原始参考文献中的序号}
                例如：{1: 5, 2: 12, 3: 3} 表示新序号1对应参考文献中序号5的论文
    """
    from datetime import datetime

    def parse_date(date_str):
        """解析日期字符串"""
        if not date_str:
            return datetime(1900, 1, 1)
        try:
            if isinstance(date_str, str):
                if '-' in date_str and len(date_str) >= 10:
                    return datetime.strptime(date_str[:10], '%Y-%m-%d')
                elif date_str.isdigit() and len(date_str) == 4:
                    return datetime(int(date_str), 1, 1)
            return datetime(1900, 1, 1)
        except (ValueError, TypeError):
            return datetime(1900, 1, 1)

    if not all_papers:
        return [], [], {}

    print(f"\n{'='*80}")
    print("开始两步筛选文献...")
    print(f"{'='*80}")

    # ==================== 第一步：筛选参考文献 ====================
    print(f"\n【第一步】筛选参考文献（从{len(all_papers)}篇中筛选出{reference_count}篇用于综述撰写）...")

    if len(all_papers) <= reference_count:
        print(f"  论文数量({len(all_papers)})小于等于参考文献目标数量({reference_count})，所有论文作为参考文献")
        reference_papers = all_papers
    else:
        # 使用大模型筛选参考文献
        reference_papers = _select_reference_papers_with_llm(all_papers, reference_count, keyword)
        if not reference_papers:
            print("  大模型筛选参考文献失败，使用备用方案")
            reference_papers = filter_papers_fallback(all_papers, reference_count)

    print(f"  ✓ 参考文献筛选完成：共 {len(reference_papers)} 篇")

    # 为参考文献添加全局索引（记录原始在参考文献列表中的序号）
    for i, paper in enumerate(reference_papers, 1):
        paper['_ref_index'] = i  # 记录在参考文献中的原始序号

    # ==================== 第二步：从参考文献中筛选引用文献 ====================
    print(f"\n【第二步】从{len(reference_papers)}篇参考文献中筛选出{citation_count}篇用于文中详细引用叙述...")

    if len(reference_papers) <= citation_count:
        print(f"  参考文献数量({len(reference_papers)})小于等于引用文献目标数量({citation_count})，所有参考文献也作为引用文献")
        citation_papers = reference_papers
    else:
        # 使用大模型筛选引用文献
        citation_papers = _select_citation_papers_with_llm(reference_papers, citation_count, keyword)
        if not citation_papers:
            print("  大模型筛选引用文献失败，使用备用方案")
            citation_papers = _select_citation_papers_fallback(reference_papers, citation_count)

    print(f"  ✓ 引用文献筛选完成：共 {len(citation_papers)} 篇")

    # ==================== 第三步：对引用文献进行重排序 ====================
    print(f"\n【第三步】对引用文献进行重排序（按发表时间，最新在前）...")

    # 为每篇引用文献添加排序得分（发表时间越新得分越高）
    papers_with_score = []
    for paper in citation_papers:
        paper_copy = paper.copy()
        date = parse_date(paper.get('published', ''))
        # 发表年份得分：2024年得100分，每年减5分
        if date.year >= 2020:
            date_score = 100 - (2024 - date.year) * 5
        else:
            date_score = max(0, 50 - (2020 - date.year) * 2)
        paper_copy['_date_score'] = date_score
        paper_copy['_original_ref_index'] = paper.get('_ref_index', 0)  # 保存原始参考文献序号
        papers_with_score.append(paper_copy)

    # 按得分排序（降序）
    sorted_papers = sorted(papers_with_score, key=lambda x: x['_date_score'], reverse=True)

    # 移除临时字段，生成最终的引用文献列表和序号映射
    citation_papers_sorted = []
    citation_index_mapping = {}  # {新序号(1-based): 原始参考文献序号}
    for new_idx, paper in enumerate(sorted_papers, 1):
        original_ref_index = paper.pop('_date_score', None)
        original_ref_index = paper.pop('_original_ref_index', 0)
        paper.pop('_ref_index', None)  # 移除参考文献索引标记
        citation_papers_sorted.append(paper)
        citation_index_mapping[new_idx] = original_ref_index

    print(f"  ✓ 引用文献重排序完成")
    print(f"    新序号 -> 原始参考文献序号: {citation_index_mapping}")

    # 清理参考文献的临时字段
    for paper in reference_papers:
        paper.pop('_ref_index', None)

    # ==================== 显示筛选结果统计 ====================
    print(f"\n{'='*80}")
    print("文献筛选统计：")
    print(f"  搜索到的论文总数：{len(all_papers)}")
    print(f"  参考文献数量：{len(reference_papers)}（用于综述撰写）")
    print(f"  引用文献数量：{len(citation_papers_sorted)}（用于文中详细引用，按发表时间重排序）")
    print(f"  序号映射：{citation_index_mapping}")
    print(f"{'='*80}")

    return reference_papers, citation_papers_sorted, citation_index_mapping


def _select_reference_papers_with_llm(all_papers, target_count, keyword):
    """
    使用大模型从所有论文中筛选参考文献（用于综述撰写）

    筛选标准：
    1. 与综述主题高度相关
    2. 期刊质量较高
    3. 日期较新或引用次数较高
    4. 能够全面覆盖综述的主要观点和技术方向
    """
    try:
        # 构建论文信息摘要
        papers_content = ""
        for i, paper in enumerate(all_papers, 1):
            title = paper.get('title') or '未知标题'
            authors = paper.get('authors') or []
            published = paper.get('published') or '未知'
            venue = paper.get('venue') or ''
            citation_count = paper.get('citation_count') or 0
            summary = paper.get('summary') or '无摘要'

            papers_content += f"\n[论文 {i}]\n"
            papers_content += f"标题: {title}\n"
            papers_content += f"作者: {', '.join(authors) if authors else '未知'}\n"
            papers_content += f"发表时间: {published}\n"
            if venue:
                papers_content += f"来源: {venue}\n"
            papers_content += f"引用数: {citation_count}\n"
            if summary and isinstance(summary, str):
                summary_short = summary[:300] + "..." if len(summary) > 300 else summary
            else:
                summary_short = '无摘要'
            papers_content += f"摘要: {summary_short}\n"
            papers_content += "-" * 60 + "\n"

        system_prompt = f"""你是一位专业的学术研究助手，擅长筛选适合撰写学术综述的参考文献。

筛选标准（按重要性排序）：
1. 最重要：论文内容与综述主题高度相关
2. 论文发表在高质量期刊或会议
3. 优先选择近期发表的优秀期刊论文和高引用论文
4. 确保选择的文献能全面覆盖综述的主要观点和技术方向

请筛选出最能支撑关于"{keyword}"学术综述的参考文献。"""

        user_prompt = f"""请从以下{len(all_papers)}篇关于"{keyword}"的论文中，筛选出最适合作为综述参考文献的{target_count}篇论文。

要求：
1. 优先选择与综述主题高度相关的论文
2. 确保能全面覆盖综述的主要观点和技术方向
3. 考虑论文的期刊质量、发表日期和引用次数
4. 最终输出应能支撑一篇完整的学术综述

请严格按照以下格式输出，只输出论文编号，用逗号分隔：
编号1,编号2,编号3,...

例如：1,3,5,7,9

论文列表：
{papers_content}

请输出筛选出的{target_count}篇论文编号（用逗号分隔）："""

        response = client.chat.completions.create(
            model=openai_config['model'],
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt}
            ],
            stream=False,
            temperature=0.3,
            timeout=300
        )

        if response and response.choices and len(response.choices) > 0:
            result_text = response.choices[0].message.content.strip()

            try:
                numbers = re.findall(r'\d+', result_text)
                selected_indices = [int(n) - 1 for n in numbers]

                valid_indices = [idx for idx in selected_indices if 0 <= idx < len(all_papers)]

                # 去重并保持顺序
                seen = set()
                unique_indices = []
                for idx in valid_indices:
                    if idx not in seen:
                        seen.add(idx)
                        unique_indices.append(idx)

                # 如果数量不足，补充高引用或新日期的论文
                if len(unique_indices) < target_count:
                    remaining = [i for i in range(len(all_papers)) if i not in unique_indices]
                    remaining_papers = [(i, all_papers[i]) for i in remaining]
                    remaining_papers.sort(key=lambda x: (
                        x[1].get('citation_count') or 0,
                        x[1].get('published', '') or ''
                    ), reverse=True)
                    needed = target_count - len(unique_indices)
                    for i, _ in remaining_papers[:needed]:
                        unique_indices.append(i)

                # 如果数量过多，只取前target_count个
                unique_indices = unique_indices[:target_count]

                selected_papers = [all_papers[i] for i in unique_indices]
                print(f"  ✓ 大模型筛选参考文献完成：从{len(all_papers)}篇中选出{len(selected_papers)}篇")
                return selected_papers

            except Exception as e:
                print(f"  解析大模型返回结果时出错: {e}")

        return None

    except Exception as e:
        print(f"  筛选参考文献时出错: {e}")
        return None


def _select_citation_papers_with_llm(reference_papers, target_count, keyword):
    """
    使用大模型从参考文献中筛选引用文献（用于文中详细引用叙述）

    筛选标准：
    1. 论文内容充实，适合展开详细叙述
    2. 技术方法具体明确
    3. 实验结果和分析有价值
    4. 是该领域的代表性工作
    """
    try:
        # 构建论文信息摘要（包含更多信息用于选择）
        papers_content = ""
        for i, paper in enumerate(reference_papers, 1):
            title = paper.get('title') or '未知标题'
            authors = paper.get('authors') or []
            published = paper.get('published') or '未知'
            venue = paper.get('venue') or ''
            citation_count = paper.get('citation_count') or 0
            summary = paper.get('summary') or '无摘要'

            papers_content += f"\n[论文 {i}]\n"
            papers_content += f"标题: {title}\n"
            papers_content += f"作者: {', '.join(authors) if authors else '未知'}\n"
            papers_content += f"发表时间: {published}\n"
            if venue:
                papers_content += f"来源: {venue}\n"
            papers_content += f"引用数: {citation_count}\n"
            if summary and isinstance(summary, str):
                summary_short = summary[:400] + "..." if len(summary) > 400 else summary
            else:
                summary_short = '无摘要'
            papers_content += f"摘要: {summary_short}\n"
            papers_content += "-" * 60 + "\n"
        # print('papers_content:')
        # print(papers_content)
        system_prompt = f"""你是一位专业的学术综述撰写专家，擅长从参考文献中选择适合在文中详细引用叙述的论文。

选择标准（按重要性排序）：
1. 论文高度符合综述主题，适合进行关于该主题的技术详解
2. 论文提出的技术方法具有代表性，是该领域的重要工作
3. 论文的分析和讨论有价值，能为综述提供深度见解


请选择最适合在综述正文中间引用并进行详细叙述的论文。"""

        user_prompt = f"""请从以下{len(reference_papers)}篇参考文献中，选择出最适合在综述正文中间引用并进行详细叙述的{target_count}篇论文。

要求：
1. 论文高度符合综述主题，适合进行关于该主题的技术详解
2. 论文提出的技术方法具有代表性，是该领域的重要工作
3. 论文的分析和讨论有价值，能为综述提供深度见解

请严格按照以下格式输出，只输出论文编号，用逗号分隔：
编号1,编号2,编号3,...

例如：1,3,5,7,9

参考文献列表：
{papers_content}

请输出选择的{target_count}篇论文编号（用逗号分隔）："""

        response = client.chat.completions.create(
            model=openai_config['model'],
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt}
            ],
            stream=False,
            temperature=0.3,
            timeout=60
        )

        if response and response.choices and len(response.choices) > 0:
            result_text = response.choices[0].message.content.strip()

            try:
                numbers = re.findall(r'\d+', result_text)
                selected_indices = [int(n) - 1 for n in numbers]

                valid_indices = [idx for idx in selected_indices if 0 <= idx < len(reference_papers)]

                # 去重并保持顺序
                seen = set()
                unique_indices = []
                for idx in valid_indices:
                    if idx not in seen:
                        seen.add(idx)
                        unique_indices.append(idx)

                # 如果数量不足，补充高引用论文
                if len(unique_indices) < target_count:
                    remaining = [i for i in range(len(reference_papers)) if i not in unique_indices]
                    remaining_papers = [(i, reference_papers[i]) for i in remaining]
                    remaining_papers.sort(key=lambda x: (
                        x[1].get('citation_count') or 0,
                        x[1].get('published', '') or ''
                    ), reverse=True)
                    needed = target_count - len(unique_indices)
                    for i, _ in remaining_papers[:needed]:
                        unique_indices.append(i)

                # 如果数量过多，只取前target_count个
                unique_indices = unique_indices[:target_count]

                selected_papers = [reference_papers[i] for i in unique_indices]
                print(f"  ✓ 大模型筛选引用文献完成：从{len(reference_papers)}篇中选出{len(selected_papers)}篇")
                return selected_papers

            except Exception as e:
                print(f"  解析大模型返回结果时出错: {e}")

        return None

    except Exception as e:
        print(f"  筛选引用文献时出错: {e}")
        return None


def _select_citation_papers_fallback(reference_papers, target_count):
    """
    备用筛选方案：从参考文献中选择引用文献
    按内容充实度和引用价值综合排序
    """
    from datetime import datetime

    def parse_date(date_str):
        if not date_str:
            return datetime(1900, 1, 1)
        try:
            if isinstance(date_str, str):
                if '-' in date_str and len(date_str) >= 10:
                    return datetime.strptime(date_str[:10], '%Y-%m-%d')
                elif date_str.isdigit() and len(date_str) == 4:
                    return datetime(int(date_str), 1, 1)
            return datetime(1900, 1, 1)
        except (ValueError, TypeError):
            return datetime(1900, 1, 1)

    def calculate_summary_length(summary):
        """计算摘要长度作为内容充实度的指标"""
        if not summary or not isinstance(summary, str):
            return 0
        return len(summary)

    # 为每篇论文计算综合得分
    papers_with_score = []
    current_year = datetime.now().year

    for paper in reference_papers:
        paper_copy = paper.copy()

        # 内容充实度得分（摘要长度）
        summary_length = calculate_summary_length(paper.get('summary', ''))
        content_score = min(100, summary_length / 10)  # 每10个字符得1分，上限100

        # 引用价值得分
        citation_count = int(paper.get('citation_count', 0) or 0)
        citation_score = min(100, 20 * (1 + (citation_count ** 0.5)))

        # 时效性得分
        date = parse_date(paper.get('published', ''))
        if date.year >= current_year - 3:
            date_score = 100 - (current_year - date.year) * 10
        else:
            date_score = max(0, 70 - (current_year - 3 - date.year) * 5)

        # 综合得分：内容充实度50%，引用价值30%，时效性20%
        total_score = content_score * 0.5 + citation_score * 0.3 + date_score * 0.2
        paper_copy['_score'] = total_score
        papers_with_score.append(paper_copy)

    # 按得分排序
    sorted_papers = sorted(papers_with_score, key=lambda x: x['_score'], reverse=True)

    # 移除临时字段并返回
    selected_papers = []
    for paper in sorted_papers[:target_count]:
        paper.pop('_score', None)
        selected_papers.append(paper)

    print(f"  ✓ 备用筛选完成：按内容充实度和引用价值选出{len(selected_papers)}篇文献")
    return selected_papers
















