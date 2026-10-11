"""Build a provenance-aware Obsidian vault from the read-only inventory."""
import argparse
import hashlib
import json
import math
import re
import subprocess
import sys
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo

from settings import Settings
CONFIG = Settings()
HERE = Path(__file__).resolve().parent.parent
VAULT = CONFIG.vault
DATA = CONFIG.data
T = CONFIG.text
P = CONFIG.rel
L = CONFIG.label
EXTRACTABLE = {'.md','.markdown','.txt','.rst','.docx','.pdf','.pptx','.tex','.csv'}
STATUSES = {key:T(zh,en) for key,zh,en in [
    ('extracted','文字已提取','Text extracted'), ('partial','文字部分提取','Partially extracted'),
    ('empty','空文档','Empty document'), ('no_extractable_text','未检出文字，可能需要 OCR','No text found; OCR may be needed'),
    ('oversize','超过 50MB，保留原文入口','Over 50 MB; original linked'),
    ('oversize_xml','文档内部 XML 过大','Document XML too large'),
    ('unsupported_encoding','编码无法确定','Unknown text encoding'),
    ('binary_text_file','扩展名是文本，内容为二进制','Text extension contains binary data'),
    ('source_changed_during_read','读取期间来源发生变化','Source changed during extraction'),
    ('extraction_error','提取失败','Extraction failed'), ('timeout','提取超时','Extraction timed out'),
    ('reference_only','文件目录索引','File reference only')]}
state_path = DATA / 'generation-state.json'
state = json.loads(state_path.read_text(encoding='utf-8')) if state_path.exists() else {'outputs':{},'sources':{}}
conflicts=[]

def safe_name(s):
    return re.sub(r'[<>:"/\\|?*\[\]#^]', '_', s).strip(' .')[:75] or T('资料','Material')

def ident(s):
    return hashlib.sha256(s.encode('utf-8')).hexdigest()[:12]

def project_slug(s):
    return safe_name(s) + ('--' + ident(s) if CONFIG.stable_project_ids else '')

def wiki(path, label=None):
    return f'[[{path.removesuffix(".md")}|{(label or Path(path).stem).replace("|","_").replace("]","_")}]]'

def link(key, label=None):
    return wiki(P(key),label or L(key))

def original(path, label=None):
    label = label or T('打开原文件','Open original')
    return f'[{label.replace("[","_").replace("]","_")}]({Path(path).as_uri()})'

def write(rel, content, once=False):
    p=VAULT/rel
    if once and p.exists():
        return False
    digest=hashlib.sha256(content.encode('utf-8')).hexdigest()
    if p.exists():
        # Older Windows output used CRLF, but state hashes used LF. Normalize only
        # newlines so substantive manual edits remain protected.
        old=hashlib.sha256(p.read_bytes().replace(b'\r\n', b'\n')).hexdigest()
        if old==digest:
            state['outputs'][rel]=digest
            return True
        prior=state['outputs'].get(rel)
        if prior is None or old!=prior:
            conflicts.append(rel)
            return False
    p.parent.mkdir(parents=True,exist_ok=True)
    temp=p.with_name(p.name+'.writing')
    temp.write_text(content,encoding='utf-8',newline='\n')
    temp.replace(p)
    state['outputs'][rel]=digest
    return True

def category(name):
    for label, keywords in CONFIG.categories.items():
        if any(str(word).casefold() in name.casefold() for word in keywords):
            return label
    return T('其他资料','Other Materials')

def content_skip(rec):
    p=rec['relative_path'].lower()
    # Preserve exact paths in catalog, but don't treat synthetic fixtures as research prose.
    if '/docs/audit/' in p and ('/runtime/' in p or '/ignored-package/' in p):
        return 'synthetic_test_fixture'
    if '/tests/' in p and ('/fixtures/' in p or '/runtime/' in p):
        return 'synthetic_test_fixture'
    if '/.generated/' in p:
        return 'generated_documentation_copy'
    if '/runtime/' in p and any(s in p for s in ['/python/', '/vendor/', '/resources/']):
        return 'bundled_dependency_documentation'
    return None

def extract(rec):
    key=ident(rec['relative_path'])
    cache=DATA/'extracted'/f'{key}.json'
    try:
        st=Path(rec['path']).stat()
        if cache.exists():
            saved=json.loads(cache.read_text(encoding='utf-8'))
            if saved.get('source_size')==st.st_size and saved.get('source_mtime_ns')==st.st_mtime_ns:
                return rec,saved
        completed=subprocess.run([sys.executable,str(HERE/'scripts'/'extract_document.py'),rec['path']],
                                 capture_output=True,encoding='utf-8',timeout=25,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        try:
            result=json.loads(completed.stdout)
        except (ValueError,TypeError):
            result={'status':'extraction_error','error':'InvalidWorkerResult','text':''}
        # Cache failures too; --retry-failures clears failed cache entries.
        result.setdefault('source_size',st.st_size)
        result.setdefault('source_mtime_ns',st.st_mtime_ns)
        cache.parent.mkdir(exist_ok=True)
        cache.write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8')
        return rec,result
    except subprocess.TimeoutExpired:
        return rec,{'status':'timeout','text':''}
    except OSError as exc:
        return rec,{'status':'extraction_error','error':type(exc).__name__,'text':''}

def fenced(text):
    longest=max([len(m.group()) for m in re.finditer(r'`+',text)]+[2])
    fence='`'*(longest+1)
    return f'{fence}text\n{text}\n{fence}'

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--retry-failures',action='store_true')
    args=parser.parse_args()
    summary=json.loads((DATA/'inventory-summary.json').read_text(encoding='utf-8'))
    records=[json.loads(s) for s in (DATA/'inventory.jsonl').read_text(encoding='utf-8').splitlines()]
    now=datetime.now(ZoneInfo(CONFIG.timezone)).strftime('%Y-%m-%d %H:%M')
    VAULT.mkdir(exist_ok=True)
    for key in ('start','projects','sources','notes','files','topics','templates','attachments'):
        CONFIG.path(key).mkdir(exist_ok=True)
    (DATA/'extracted').mkdir(exist_ok=True)
    if args.retry_failures:
        for p in (DATA/'extracted').glob('*.json'):
            if json.loads(p.read_text(encoding='utf-8')).get('status') not in {'extracted','partial','empty'}:
                p.unlink()
    by_project=defaultdict(list)
    for rec in records:
        by_project[rec['project']].append(rec)
    project_paths={name:f'{P("projects")}/{project_slug(name)}.md' for name in summary['projects']}
    all_docs=[r for r in records if r['extension'] in EXTRACTABLE]
    skipped=[{**r,'reason':content_skip(r)} for r in all_docs if content_skip(r)]
    docs=[r for r in all_docs if not content_skip(r)]
    with (DATA/'text-extraction-skips.jsonl').open('w',encoding='utf-8') as f:
        for rec in skipped:
            f.write(json.dumps(rec,ensure_ascii=False)+'\n')
    print(T(f'整理中：{len(records):,} 个文件入口，{len(docs):,} 份文字资料；原文件只读',f'Building: {len(records):,} file references; {len(docs):,} text documents; originals read-only'),flush=True)
    extracted={}
    statuses=Counter()
    output_notes={}
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures=[pool.submit(extract,rec) for rec in docs]
        for done,future in enumerate(as_completed(futures),1):
            rec,result=future.result()
            key=ident(rec['relative_path'])
            extracted[key]=result
            statuses[result['status']]+=1
            rel=f'{P("sources")}/{project_slug(rec["project"])}/{safe_name(Path(rec["path"]).stem)}--{key}.md'
            rec['note_path']=rel
            rec['extraction_status']=result['status']
            status=STATUSES.get(result['status'],result['status'])
            front={'kind':'source-extract','project':rec['project'],'source_path':rec['path'],
                   'source_modified_utc':rec['modified_utc'],'extraction_status':result['status'],
                   'source_sha256':result.get('sha256',''),'generated_at':now}
            header='---\n'+'\n'.join(f'{k}: {json.dumps(v,ensure_ascii=False)}' for k,v in front.items())+'\n---\n\n'
            body=f'# {Path(rec["path"]).name}\n\n{wiki(project_paths[rec["project"]],rec["project"])} · {original(rec["path"])}\n\n'
            body+=T(f'> [!info] 来源摘录\n> {status}。这是自动生成的检索副本；个人理解和判断请写入 `{P("notes")}`。原文件保留在来源目录。\n\n',f'> [!info] Source extract\n> {status}. This is a generated search copy. Write your interpretations and decisions in `{P("notes")}`. Originals remain in their source folder.\n\n')
            body+=T(f'- 原路径：`{rec["path"]}`\n- 原文件修改时间（UTC）：{rec["modified_utc"]}\n',f'- Original path: `{rec["path"]}`\n- Source modified (UTC): {rec["modified_utc"]}\n')
            if result.get('total_pages') is not None:
                body+=T(f'- 已读取页数：{result.get("pages_read",0)}/{result["total_pages"]}\n',f'- Pages read: {result.get("pages_read",0)}/{result["total_pages"]}\n')
            if result.get('redactions'):
                body+=T(f'- 已隐藏疑似凭据片段：{result["redactions"]}\n',f'- Suspected credential snippets hidden: {result["redactions"]}\n')
            if result['status']=='partial':
                body+=T('- 超出文字或页数上限；未提取部分请回到原文件核对。\n','- Text or page limit reached. Check omitted content in the original.\n')
            body+=T('\n## 来源正文\n\n','\n## Source Text\n\n')+(fenced(result['text']) if result.get('text') else T(f'{status}。请通过上方链接查看原文。',f'{status}. Follow the original link above.'))+'\n'
            write(rel,header+body)
            output_notes[key]=rel
            if done%100==0 or done==len(docs):
                print(T(f'文字：{done}/{len(docs)}；已提取 {statuses["extracted"]}，部分提取 {statuses["partial"]}，缺口 {done-statuses["extracted"]-statuses["partial"]}',f'Text: {done}/{len(docs)}; extracted={statuses["extracted"]}, partial={statuses["partial"]}, gaps={done-statuses["extracted"]-statuses["partial"]}'),flush=True)
    # Exact individual paths stay in catalog; dense asset folders use grouped navigation.
    inventory_pages=0
    grouped_files=0
    for name,info in summary['projects'].items():
        subset=by_project[name]
        text_docs=[r for r in subset if r.get('note_path')]
        category_name=category(name)
        folder_records=defaultdict(list)
        for rec in subset:
            folder_records[str(Path(rec['path']).parent)].append(rec)
        dense={p:rs for p,rs in folder_records.items() if len(rs)>500 and sum(bool(r.get('note_path')) for r in rs)<16}
        display_records=[]
        seen=set()
        for rec in subset:
            folder=str(Path(rec['path']).parent)
            if folder in dense:
                if folder not in seen:
                    members=dense[folder]
                    display_records.append({'path':folder,'relative_path':str(Path(folder).relative_to(Path(summary['source_root']))),
                                            'project':name,'size_bytes':sum(r['size_bytes'] for r in members),
                                            'grouped_count':len(members),'extension_summary':dict(Counter(r['extension'] for r in members).most_common(4))})
                    seen.add(folder)
                    grouped_files+=len(members)
            else:
                display_records.append(rec)
        pages=[]
        for page in range(math.ceil(len(display_records)/350)):
            rel=f'{P("files")}/{project_slug(name)}/{T("清单","File List")}-{page+1:03d}.md'
            pages.append(rel)
            body=f'# {name} · {T("文件清单","File List")} {page+1}\n\n{wiki(project_paths[name],name)}\n\n'
            body+=T('图片、表格、图纸、模型和代码保留来源入口。密集文件夹按目录汇总；用工具 `scripts/pipeline.py search --paths --query "关键词"` 查找具体文件路径。\n\n','Images, spreadsheets, drawings, models and code remain original file links. Dense folders are grouped; use `scripts/pipeline.py search --paths --query "keywords"` to find individual paths.\n\n')
            for rec in display_records[page*350:(page+1)*350]:
                label=rec['relative_path'].split('/',1)[-1] if rec['project']!=T('根目录资料','Root Files') else rec['relative_path']
                body+=f'- {original(rec["path"],label)} · {rec["size_bytes"]:,} bytes'
                if rec.get('grouped_count'):
                    body+=T(f' · **文件夹汇总：{rec["grouped_count"]:,} 个文件** · ',f' · **Folder summary: {rec["grouped_count"]:,} files** · ')+json.dumps(rec['extension_summary'],ensure_ascii=False)
                if rec.get('note_path'):
                    body+=' · '+wiki(rec['note_path'],T('文字副本','Text Copy'))
                body+='\n'
            write(rel,body)
            inventory_pages+=1
        candidates=sorted(text_docs,key=lambda r:r['modified_utc'],reverse=True)
        entry_docs=sorted(text_docs,key=lambda r:(0 if re.search(r'readme|pr[dD]|概览|报告|论文|manuscript|摘要|设计说明',Path(r['path']).name,re.I) else 1, -int(datetime.fromisoformat(r['modified_utc']).timestamp())))[:12]
        body=f'---\nkind: project-index\ncategory: {json.dumps(category_name,ensure_ascii=False)}\ngenerated_at: {json.dumps(now)}\n---\n\n# {name}\n\n'
        body+=f'{wiki(P("navigation"),T("全部项目","All Projects"))} · {wiki(P("topics")+"/"+category_name+".md",category_name)} · {original(info["path"],T("打开原文件夹","Open Source Folder"))}\n\n'
        body+=T(f'当前目录扫描：**{info["files"]:,} 个文件**，约 **{info["bytes"]/1024**3:.2f} GB**；生成 **{len(text_docs):,} 份文字副本**。\n\n',f'Current scan: **{info["files"]:,} files**, about **{info["bytes"]/1024**3:.2f} GB**, with **{len(text_docs):,} text copies**.\n\n')
        body+=T('> 分类来自文件夹名称，是导航建议。目录日期、修改时间和标题不能说明项目的优先级、完成状态或采用情况。\n\n','> Categories are navigation suggestions based on folder names. Dates, modification times and titles do not establish priorities, completion or adoption.\n\n')
        body+=T('## 从这些资料开始\n\n','## Start with These Sources\n\n')+('\n'.join('- '+wiki(r['note_path'],Path(r['path']).name)+' · '+STATUSES.get(r['extraction_status'],r['extraction_status']) for r in entry_docs) or T('这个文件夹暂未找到可提取的文字资料。','No extractable text found in this folder yet.'))+'\n\n'
        body+=T('## 最近修改的文字资料\n\n','## Recently Modified Text Sources\n\n')+('\n'.join('- '+wiki(r['note_path'],Path(r['path']).name)+f' · {r["modified_utc"][:10]}' for r in candidates[:8]) or T('暂无文字资料。','No text sources yet.'))+'\n\n'
        body+=T('## 文件清单\n\n','## File Lists\n\n')+('\n'.join('- '+wiki(p,Path(p).stem) for p in pages) or T('这是一个空目录；已保留入口。','Empty folder; its entry is retained.'))+'\n'
        write(project_paths[name],body)
    groups=defaultdict(list)
    for name in summary['projects']:
        groups[category(name)].append(name)
    navigation=f'# {L("navigation")}\n\n{wiki(P("home"),L("home"))}\n\n'+T(f'扫描时间：{now}。覆盖 {len(summary["projects"])} 个项目或资料分组。分类来自目录名称，可以在自己的主题笔记中重新组织。\n\n',f'Scanned: {now}. Includes {len(summary["projects"])} project or material groups. Folder-based categories can be reorganized in your own topic notes.\n\n')
    for group,names in groups.items():
        navigation+=f'## {group}\n\n'
        navigation+='\n'.join(f'- {wiki(project_paths[n],n)} · {summary["projects"][n]["files"]:,} {T("个文件","files")}' for n in names)+'\n\n'
        group_body=f'# {group}\n\n{wiki(P("navigation"),L("navigation"))} · {wiki(P("map"),L("map"))}\n\n'+T('按来源目录初步归类；主题关联由你后续确认。\n\n','Grouped by source folders; confirm meaningful topic relationships yourself.\n\n')
        group_body+='\n'.join('- '+wiki(project_paths[n],n) for n in names)+T(f'\n\n在 `{P("notes")}` 新建主题笔记，并链接相关项目和来源。\n',f'\n\nCreate topic notes in `{P("notes")}` and link relevant projects and sources.\n')
        write(f'{P("topics")}/{group}.md',group_body)
    write(P('navigation'),navigation)
    usable=statuses['extracted']+statuses['partial']
    report={'built_at':now,'source_root':summary['source_root'],'vault':str(VAULT),
            'projects':len(summary['projects']),'indexed_files':len(records),'indexed_bytes':summary['bytes'],
            'document_candidates':len(all_docs),'extraction_candidates':len(docs),'searchable_documents':usable,'extraction_statuses':dict(statuses),
            'text_candidates_reference_only':len(skipped),'reference_only_reasons':dict(Counter(r['reason'] for r in skipped)),
            'files_in_grouped_asset_folders':grouped_files,
            'directory_index_pages':inventory_pages,'excluded_entries':len(summary['omitted_entries']),
            'scan_errors':summary['scan_errors'],'protected_modified_notes':conflicts,
            'extract_limits':{'max_source_bytes':50*1024*1024,'max_characters':200000,'max_pdf_pages':100,'timeout_seconds':25},
            'fulltext_is_complete':statuses['partial']==0 and sum(v for k,v in statuses.items() if k not in {'extracted','empty'})==0,
            'automatic_sync':False,'external_upload':False,'language':CONFIG.language,'vault_name':CONFIG.vault_name,'layout':CONFIG.layout}
    (DATA/'import-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    with (DATA/'catalog.jsonl').open('w',encoding='utf-8') as f:
        for rec in records:
            f.write(json.dumps(rec,ensure_ascii=False)+'\n')
    coverage=f'# {L("coverage")}\n\n{wiki(P("home"),L("home"))}\n\n{T("更新","Updated")}: {now}\n\n'
    coverage+=T(f'- 扫描来源：`{summary["source_root"]}`\n- 项目/资料分组：{len(summary["projects"])}\n- 文件路径索引：{len(records):,}\n- 来源文件总大小：{summary["bytes"]/1024**3:.2f} GB（原文件未复制）\n- 文字候选：{len(all_docs):,}；实际提取 {len(docs):,}，可搜索正文 {usable:,}\n- 测试夹具/生成文档/依赖文档：{len(skipped):,}，保留路径入口\n- 密集文件夹汇总的文件：{grouped_files:,}；逐文件清单见 `data/catalog.jsonl`\n- 刷新入口：Refresh.cmd；Codex 定期任务需另行配置\n- 对外上传：导入脚本没有上传资料\n\n',f'- Source folder: `{summary["source_root"]}`\n- Project/material groups: {len(summary["projects"])}\n- Indexed file paths: {len(records):,}\n- Source size: {summary["bytes"]/1024**3:.2f} GB (originals are not copied)\n- Text candidates: {len(all_docs):,}; extracted: {len(docs):,}; searchable: {usable:,}\n- Test fixtures/generated/dependency docs: {len(skipped):,}; paths retained\n- Files grouped in dense folders: {grouped_files:,}; individual paths in `data/catalog.jsonl`\n- Refresh: Refresh.cmd; configure Codex recurring tasks separately\n- External upload: the importer does not upload your sources\n\n')
    coverage+=T('## 文字提取状态\n\n| 状态 | 数量 |\n| --- | ---: |\n','## Text Extraction Status\n\n| Status | Count |\n| --- | ---: |\n')+''.join(f'| {STATUSES.get(k,k)} | {v:,} |\n' for k,v in statuses.items())
    coverage+=T('\n每份文档上限：50MB、200000 字符、PDF 100 页、25 秒。Word 和幻灯片只提取正文，不保留排版、图像或批注。扫描 PDF 尚未 OCR。检索副本不代表逐份资料的理解或审核。\n\n','\nPer-document limits: 50 MB, 200,000 characters, 100 PDF pages and 25 seconds. Word and slides retain text only, without layout, images or comments. Scanned PDFs have no OCR. Search copies do not imply each document has been understood or reviewed.\n\n')
    coverage+=T('## 未提取、截断或读取失败的资料\n\n','## Missing, Truncated or Unreadable Text\n\n')
    for rec in docs:
        if rec['extraction_status'] not in {'extracted','empty'}:
            coverage+='- '+wiki(rec['note_path'],rec['relative_path'])+' · '+STATUSES.get(rec['extraction_status'],rec['extraction_status'])+'\n'
    coverage+=T('\n## 扫描边界\n\n排除依赖、缓存、版本库与工具状态、Unity/ROS 生成缓存、链接目录及输出工作区。常见凭据文件名会被排除，疑似凭据片段会被隐藏；这些规则不能替代安全审核。这里只列被排除入口，不估算其内部文件数。\n\n','\n## Scan Boundaries\n\nDependencies, caches, repository/tool state, Unity/ROS generated caches, linked folders and the output workspace are excluded. Common credential filenames are excluded and suspected credential snippets are hidden; these rules are not a security audit. Only excluded entries are listed, without estimating their contents.\n\n')
    for item in summary['omitted_entries']:
        coverage+=f'- `{item["path"]}` · {item["reason"]}\n'
    coverage+=T('\n## 目录扫描错误\n\n','\n## Folder Scan Errors\n\n')+(T('无。\n','None.\n') if not summary['scan_errors'] else '\n'.join(f'- `{x["path"]}` · {x["error"]}' for x in summary['scan_errors'])+'\n')
    if conflicts:
        coverage+=T('\n## 已保留的手工修改\n\n','\n## Preserved Manual Edits\n\n')+'\n'.join('- '+p for p in conflicts)+'\n'
    write(P('coverage'),coverage)
    home=T(f'''# {CONFIG.product_name}

把保存过的资料，变成下一步可用的知识。

工作项目、长期学习、个人记录、生活计划和研究探索，都可以从同一个工作台继续。先在 **{link('navigation')}** 找资料，按 **Ctrl + Shift + F** 搜正文，再把自己的理解写进 **{link('profile')}**。

## 今天从这里开始

- {link('map')}：看资料分布，找到一个入口。
- {link('canvas')}：按主题浏览项目与资料。
- {link('guide')}：搜索、写笔记、链接来源。
- {link('codex')}：让 Codex 参考相关资料，帮你整理下一步。

## 已接入的资料

**{len(summary['projects'])} 个资料分组 · {len(records):,} 个文件入口 · {usable:,} 份可搜索文字资料**

原文件保留在 `{summary['source_root']}`。文字副本带来源路径；图片、表格、图纸、模型和代码保留原文件入口。{link('coverage')}。

## 留下可以继续使用的理解

- {link('profile')}：我现在关注什么、采用哪个版本、下一步是什么。
- {link('knowledge_template')}：记录一个问题、依据和当前理解。
- {link('decision_template')}：记录选择、适用条件和代价。
- {link('reading_template')}：记录书籍、文章或课程中的可用知识。

最近索引更新：{now}。新增资料后运行 **Refresh.cmd**。可以请 Codex 配置定期整理；频率与范围由你决定。
''',f'''# {CONFIG.product_name}

Turn saved material into knowledge you can use next.

Continue work projects, long-term learning, personal notes, life planning and research from one workspace. Start with **{link('navigation')}**, search text with **Ctrl + Shift + F**, then write your own understanding in **{link('profile')}**.

## Start Here Today

- {link('map')}: find an entry in your material collection.
- {link('canvas')}: browse projects and sources by topic.
- {link('guide')}: search, write notes and connect sources.
- {link('codex')}: let Codex consult relevant sources and help with next steps.

## Connected Material

**{len(summary['projects'])} material groups · {len(records):,} file references · {usable:,} searchable text sources**

Originals remain in `{summary['source_root']}`. Text copies include source paths; images, spreadsheets, drawings, models and code retain original links. See {link('coverage')}.

## Capture Understanding You Can Reuse

- {link('profile')}: current focus, adopted versions and next steps.
- {link('knowledge_template')}: a question, evidence and current understanding.
- {link('decision_template')}: choices, conditions and trade-offs.
- {link('reading_template')}: useful knowledge from books, articles and courses.

Last index update: {now}. Run **Refresh.cmd** after adding material. Ask Codex to configure recurring upkeep at your chosen frequency and scope.
''')
    write(P('home'),home)
    guide=T(f'''# 第一次使用

{link('home')}

## 找到资料

按 **Ctrl + Shift + F** 搜关键词，按 **Ctrl + O** 按标题跳转。进入来源摘录，点“打开原文件”核对完整内容。图表、公式、批注和扫描文字可能没有被提取，要回到原文查看。

## 留下自己的理解

按 **Ctrl + N** 新建笔记，默认保存到 `{P('notes')}`。按 **Ctrl + P** 搜“插入模板”，选择知识、阅读或决策模板。输入 `[[`，选择项目或来源，就能建立链接。

先记录三件事：我看到了什么；我怎样理解；下一步要核对或行动什么。工作、学习、生活和研究都可以这样积累。把来源内容与自己的判断分开，后续才能知道一个结论从哪里来、适用于什么情况。

## 看见关联

打开 {link('canvas')}，双击主题或项目卡片。关系图谱优先显示项目、主题和自己的笔记。自动主题分类只是导航建议，具体关联由你确认。

## 保持可继续使用

运行 **Refresh.cmd** 刷新索引。它保留个人笔记和手工修改的生成页，报告冲突；已删除来源的旧摘录作为历史保留，使用前需核对原文件是否存在。

请 Codex 建立定期任务，就可以按你选定的范围整理新增资料、提炼可复用理解，并标出版本冲突与待确认事项。没有变化时可以保持安静。

资料库使用本地 Markdown 和 Obsidian 核心功能。已有仓库会保留，可以在 Obsidian 中切换。

官方说明：[本地仓库](https://obsidian.md/help/vault)、[全文搜索](https://obsidian.md/help/plugins/search)。
''',f'''# Getting Started

{link('home')}

## Find Material

Search keywords with **Ctrl + Shift + F**, or jump to a title with **Ctrl + O**. Open a source extract and follow **Open original** to check the complete content. Charts, formulas, comments and scanned text may be missing from extracts.

## Record Your Understanding

Create a note with **Ctrl + N**; it goes into `{P('notes')}` by default. Use **Ctrl + P**, find **Insert template**, and choose a knowledge, reading or decision template. Type `[[` and choose a project or source to link it.

Begin with three things: what you observed, how you understand it, and what to check or do next. This works for work, learning, life and research. Separate source content from your own judgment so future decisions retain their evidence and conditions.

## See Connections

Open {link('canvas')} and double-click a topic or project card. The graph favors projects, topics and your own notes. Automatic categories are navigation suggestions; you confirm meaningful connections.

## Keep the Workspace Useful

Run **Refresh.cmd** to update the index. It preserves personal notes and manually edited generated pages, reports conflicts, and keeps extracts from removed sources as history. Check that an original still exists before relying on it.

Ask Codex to create a recurring task for the scope you choose: organize new material, draft reusable insights, and flag version conflicts or unanswered questions. It can stay quiet when nothing meaningful changes.

The vault uses local Markdown and Obsidian core features. Existing vaults are preserved and remain available in the vault switcher.

Official help: [Local vaults](https://obsidian.md/help/vault), [Search](https://obsidian.md/help/plugins/search).
''')
    write(P('guide'),guide,once=True)
    codex=T(f'''# 与 Codex 一起工作

{link('home')} · {link('map')} · {link('profile')}

## 可以直接这样说

> 先读我的近况和项目导航，找到与这个问题有关的资料，再给我建议。区分来源说了什么、你推断了什么和我已经确认的判断，每个结论给出来源。

> 从我的工作记录和学习笔记中找出可以复用的方法，说明适用条件，再整理成一份带来源的知识笔记。

> 比较这个项目的两个版本，找出新证据、冲突和待核对事项；不要把草稿或计划当成已完成结果。

> 每周整理新增资料，更新索引，把可复用的理解写成独立笔记；没有有意义的变化时保持安静。

## 它怎样参考知识库

Codex 在有访问权限的当前项目中，按问题读取导航、摘录和相关原文。工作目录的 `AGENTS.md` 提供读取路线；`scripts/pipeline.py context --query "关键词"` 返回有界的来源片段和版本标记。

先读 `{P('profile')}`，再读相关项目和原文。目录能说明你保存了什么，不能替你确认当前优先级、采用版本和为什么作出选择。近况中的空白代表未知。

索引不会让模型永久记住整个硬盘，也不会把整个资料库上传。其他聊天需要明确的目录访问和读取；实际交给 Codex 的相关片段按该产品的数据设置处理。

## 定期整理

请 Codex 按你选择的频率创建定期任务，使用当前配置刷新索引。读取 `data/maintenance-latest.json` 及它指向的变化文件，再回查相关来源，把解释保存到 `{P('automation')}` 的独立日期笔记。保留你的近况和手写笔记，自动记录与 Agent 判断分开。
''',f'''# Working with Codex

{link('home')} · {link('map')} · {link('profile')}

## Say It Directly

> Read my current focus and project navigation. Find sources relevant to this question, then give advice. Separate source claims, your inferences and my confirmed decisions, and cite each conclusion.

> Find methods I can reuse from my work records and learning notes. Explain their conditions, then write a source-linked knowledge note.

> Compare two versions of this project. Identify new evidence, conflicts and unanswered questions. Keep drafts and plans separate from completed results.

> Organize new material weekly, refresh the index and write reusable insights as separate notes. Stay quiet when nothing meaningful changes.

## How Codex Consults the Vault

With access to this workspace, Codex reads navigation, extracts and relevant originals for the question at hand. The workspace `AGENTS.md` supplies the reading route; `scripts/pipeline.py context --query "keywords"` returns bounded source excerpts and version flags.

Read `{P('profile')}` first, then relevant projects and originals. Folders show what you saved, but do not establish your current priorities, adopted versions or reasons for decisions. Blank profile fields mean unknown.

Indexing does not create permanent model memory or upload the whole vault. Other chats require explicit directory access and source reading. Relevant excerpts provided to Codex are handled under the product's current data settings.

## Recurring Upkeep

Ask Codex to create a recurring task at your chosen frequency, using this config to refresh. Read `data/maintenance-latest.json` and its referenced change file, recheck relevant originals, then save interpretations as separate dated notes under `{P('automation')}`. Preserve your profile and handwritten notes; keep automatic logs separate from Agent judgment.
''')
    write(P('codex'),codex,once=True)
    profile=T(f'''# 我的近况

{link('home')} · {link('map')}

> 由你填写，或在你确认后由 Codex 整理。空白代表未知；不从文件日期猜测当前状态。

## 我现在最关注什么

待填写。可以是工作、学习、生活或研究中的问题。

## 正在推进的事情

- 项目或目标：
- 当前版本与阶段：
- 最新进展：
- 下一步：
- 来源与相关笔记：

## 长期积累的主题

待填写。

## 暂停或已完成的事情

待填写；完成状态由我确认。

## 我希望 Codex 怎样帮助我

先查来源，再提建议。区分资料陈述、观察结果、系统推断和我确认的判断。整理为可编辑笔记，保留适用条件和不确定性。
''',f'''# My Current Focus

{link('home')} · {link('map')}

> Fill this in yourself, or ask Codex to organize it after your confirmation. Blank means unknown; file dates do not establish current status.

## What Matters to Me Now

To fill in. This can concern work, learning, life or research.

## Things I Am Moving Forward

- Project or goal:
- Current version and stage:
- Latest progress:
- Next step:
- Sources and related notes:

## Topics I Am Building Over Time

To fill in.

## Paused or Completed Work

To fill in; I confirm completion.

## How I Want Codex to Help

Check sources before giving advice. Separate source claims, observed results, system inference and my confirmed judgment. Save editable notes with conditions and uncertainties.
''')
    write(P('profile'),profile,once=True)
    templates={
        'knowledge_template':T('# {{title}}\n\n日期：{{date}}\n\n## 我在解决什么问题\n\n\n## 来源与观察\n\n来源：[[项目或资料名称]]\n\n## 我的理解与适用条件\n\n\n## 下一步与待核对事项\n\n- [ ] \n','# {{title}}\n\nDate: {{date}}\n\n## Question I Am Working On\n\n\n## Sources and Observations\n\nSource: [[Project or Source]]\n\n## My Understanding and Its Conditions\n\n\n## Next Steps and Open Questions\n\n- [ ] \n'),
        'decision_template':T('# {{title}}\n\n日期：{{date}}\n\n## 事情、版本与条件\n\n\n## 可选方案与来源依据\n\n\n## 我的选择及理由\n\n\n## 代价和不确定性\n\n\n## 怎样验证或重新考虑\n\n- [ ] \n','# {{title}}\n\nDate: {{date}}\n\n## Context, Version and Conditions\n\n\n## Options and Source Evidence\n\n\n## My Choice and Reasoning\n\n\n## Trade-offs and Uncertainties\n\n\n## How to Check or Reconsider\n\n- [ ] \n'),
        'reading_template':T('# {{title}}\n\n日期：{{date}}\n\n## 书籍、文章或课程\n\n作者、日期、版本、链接：\n\n来源：[[文字副本]]\n\n## 来源实际说了什么\n\n\n## 方法、观点与局限\n\n\n## 对我的工作或生活有什么用\n\n\n## 可以回查的位置\n\n页码、章节、时间点：\n','# {{title}}\n\nDate: {{date}}\n\n## Book, Article or Course\n\nAuthor, date, version and link:\n\nSource: [[Text Copy]]\n\n## What the Source Actually Says\n\n\n## Methods, Ideas and Limits\n\n\n## How I Can Use This\n\n\n## Where to Check the Evidence\n\nPage, section or timestamp:\n'),
        'daily_template':T('# {{date}}\n\n## 今天推进了什么\n\n\n## 新资料与新的理解\n\n\n## 下一步\n\n- [ ] \n','# {{date}}\n\n## What I Moved Forward Today\n\n\n## New Sources and Understanding\n\n\n## Next Steps\n\n- [ ] \n')}
    for key,body in templates.items():
        write(P(key),body,once=True)
    overview=f'# {L("map")}\n\n{link("home")} · {link("navigation")} · {link("profile")}\n\n'+T('这张地图来自当前资料目录，展示资料分布，不自动判定优先级、完成状态或采用情况。\n\n','This map shows material distribution in current source folders. It does not establish priorities, completion or adoption.\n\n')
    for group,names in groups.items():
        overview+=f'## {group}\n\n'+wiki(f'{P("topics")}/{group}.md',T('查看相关项目','Browse Related Projects'))+'\n\n'
        overview+='\n'.join('- '+wiki(project_paths[n],n) for n in names[:8])+'\n\n'
    overview+=T('## 由我确认\n\n- 当前最重要的事情是什么？\n- 哪个版本与阶段适用于现在？\n- 哪些判断已核对，哪些仍是想法或草稿？\n\n','## For Me to Confirm\n\n- What matters most now?\n- Which version and stage apply today?\n- Which judgments are checked, and which remain ideas or drafts?\n\n')+link('profile')+'\n'
    write(P('map'),overview)
    nodes=[{'id':'home','type':'file','file':P('home'),'x':0,'y':0,'width':360,'height':230}]
    edges=[]
    for i,(group,names) in enumerate(groups.items()):
        x=(i%3)*800-800
        y=(i//3)*740+420
        gid=f'group{i}'
        nodes.append({'id':gid,'type':'file','file':f'{P("topics")}/{group}.md','x':x,'y':y,'width':340,'height':190,'color':str(i%6+1)})
        edges.append({'id':f'e{i}','fromNode':'home','fromSide':'bottom','toNode':gid,'toSide':'top','label':T('资料导航','Material Navigation')})
        selected=sorted(names,key=lambda n:summary['projects'][n]['text_candidates'],reverse=True)[:3]
        for j,n in enumerate(selected):
            nid=f'p{i}-{j}'
            nodes.append({'id':nid,'type':'file','file':project_paths[n],'x':x-40+j*135,'y':y+260+j*90,'width':270,'height':130})
            edges.append({'id':f'ep{i}-{j}','fromNode':gid,'fromSide':'bottom','toNode':nid,'toSide':'top'})
    write(P('canvas'),json.dumps({'nodes':nodes,'edges':edges},ensure_ascii=False,indent=2),once=True)
    plugins={name:True for name in ['file-explorer','global-search','switcher','graph','backlink','canvas','outgoing-link','tag-pane','properties','page-preview','daily-notes','templates','note-composer','command-palette','editor-status','bookmarks','outline','word-count','file-recovery']}
    for name in ['publish','sync','markdown-importer','audio-recorder','slides','workspaces']:
        plugins[name]=False
    css_name='research-vault' if CONFIG.legacy_layout else 'knowledge-workspace'
    configs={
        'app.json':{'newFileLocation':'folder','newFileFolderPath':P('notes'),'attachmentFolderPath':P('attachments'),'alwaysUpdateLinks':True,'showLineNumber':False,'readableLineLength':True},
        'core-plugins.json':plugins,
        'appearance.json':{'baseFontSize':17,'cssTheme':'','enabledCssSnippets':[css_name]},
        'templates.json':{'folder':P('templates'),'dateFormat':'YYYY-MM-DD','timeFormat':'HH:mm'},
        'daily-notes.json':{'folder':P('diary'),'template':P('daily_template').removesuffix('.md'),'format':'YYYY-MM-DD'},
        'graph.json':{'search':' '.join(f'-path:"{P(key)}"' for key in ('sources','files','templates')),'showTags':False,'showAttachments':False,'hideUnresolved':True,'showOrphans':True},
        'bookmarks.json':{'items':[{'type':'file','path':P(key),'title':L(key)} for key in ('home','navigation','profile','canvas')]},
        'workspace.json':{'main':{'id':'main','type':'split','children':[{'id':'tabs','type':'tabs','children':[{'id':'homeleaf','type':'leaf','state':{'type':'markdown','state':{'file':P('home'),'mode':'preview','source':False},'title':CONFIG.product_name}}]}],'direction':'vertical'},'active':'homeleaf','lastOpenFiles':[P('home')]}}
    for name,obj in configs.items():
        write('.obsidian/'+name,json.dumps(obj,ensure_ascii=False,indent=2),once=True)
    write(f'.obsidian/snippets/{css_name}.css','.markdown-preview-view { --file-line-width: 820px; }\n.markdown-preview-view h1 { margin-bottom: 1.1em; }\n.markdown-preview-view pre code { font-family: var(--font-text); font-size: 0.94em; white-space: pre-wrap; overflow-wrap: anywhere; }\n',once=True)
    CONFIG.path('attachments').mkdir(exist_ok=True)
    state['built_at']=now
    state_path.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
    report['protected_modified_notes']=list(conflicts)
    (DATA/'import-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
