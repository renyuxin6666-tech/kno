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
EXTRACTABLE = {'.md','.markdown','.txt','.rst','.docx','.pdf','.pptx','.tex','.csv'}
STATUSES = {'extracted':'文字已提取','partial':'文字部分提取','empty':'空文档',
            'no_extractable_text':'未检出文字，可能需要 OCR','oversize':'超过 50MB，保留原文入口',
            'oversize_xml':'文档内部 XML 过大','unsupported_encoding':'编码无法确定',
            'binary_text_file':'扩展名是文本，内容为二进制','source_changed_during_read':'读取期间来源发生变化',
            'extraction_error':'提取失败','timeout':'提取超时','reference_only':'文件目录索引'}
state_path = DATA / 'generation-state.json'
state = json.loads(state_path.read_text(encoding='utf-8')) if state_path.exists() else {'outputs':{},'sources':{}}
conflicts=[]

def safe_name(s):
    return re.sub(r'[<>:"/\\|?*\[\]#^]', '_', s).strip(' .')[:75] or '资料'

def ident(s):
    return hashlib.sha256(s.encode('utf-8')).hexdigest()[:12]

def project_slug(s):
    return safe_name(s) + ('--' + ident(s) if CONFIG.stable_project_ids else '')

def wiki(path, label=None):
    return f'[[{path.removesuffix(".md")}|{(label or Path(path).stem).replace("|","_").replace("]","_")}]]'

def original(path, label='打开原文件'):
    return f'[{label.replace("[","_").replace("]","_")}]({Path(path).as_uri()})'

def write(rel, content, once=False):
    p=VAULT/rel
    if once and p.exists():
        return False
    digest=hashlib.sha256(content.encode('utf-8')).hexdigest()
    if p.exists():
        # Older Windows output used CRLF, but state hashes used LF. Normalize only
        # newlines so substantive manual edits remain protected.
        old=hashlib.sha256(p.read_text(encoding='utf-8').encode('utf-8')).hexdigest()
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
    return '研究资料'

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
    (DATA/'extracted').mkdir(exist_ok=True)
    if args.retry_failures:
        for p in (DATA/'extracted').glob('*.json'):
            if json.loads(p.read_text(encoding='utf-8')).get('status') not in {'extracted','partial','empty'}:
                p.unlink()
    by_project=defaultdict(list)
    for rec in records:
        by_project[rec['project']].append(rec)
    project_paths={name:f'01_项目/{project_slug(name)}.md' for name in summary['projects']}
    all_docs=[r for r in records if r['extension'] in EXTRACTABLE]
    skipped=[{**r,'reason':content_skip(r)} for r in all_docs if content_skip(r)]
    docs=[r for r in all_docs if not content_skip(r)]
    with (DATA/'text-extraction-skips.jsonl').open('w',encoding='utf-8') as f:
        for rec in skipped:
            f.write(json.dumps(rec,ensure_ascii=False)+'\n')
    print(f'Build: {len(records):,} file references; {len(docs):,} text documents; originals read-only',flush=True)
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
            rel=f'02_资料/{project_slug(rec["project"])}/{safe_name(Path(rec["path"]).stem)}--{key}.md'
            rec['note_path']=rel
            rec['extraction_status']=result['status']
            status=STATUSES.get(result['status'],result['status'])
            front={'kind':'source-extract','project':rec['project'],'source_path':rec['path'],
                   'source_modified_utc':rec['modified_utc'],'extraction_status':result['status'],
                   'source_sha256':result.get('sha256',''),'generated_at':now}
            header='---\n'+'\n'.join(f'{k}: {json.dumps(v,ensure_ascii=False)}' for k,v in front.items())+'\n---\n\n'
            body=f'# {Path(rec["path"]).name}\n\n{wiki(project_paths[rec["project"]],rec["project"])} · {original(rec["path"])}\n\n'
            body+=f'> [!info] 来源摘录\n> {status}。这是自动生成的检索副本；个人理解和判断请写入 `03_我的笔记`。原文件仍在研究目录。\n\n'
            body+=f'- 原路径：`{rec["path"]}`\n- 原文件修改时间（UTC）：{rec["modified_utc"]}\n'
            if result.get('total_pages') is not None:
                body+=f'- 已读取页数：{result.get("pages_read",0)}/{result["total_pages"]}\n'
            if result.get('redactions'):
                body+=f'- 已隐藏疑似凭据片段：{result["redactions"]}\n'
            if result['status']=='partial':
                body+='- 超出文字或页数上限；未提取部分请回到原文件核对。\n'
            body+='\n## 来源正文\n\n'+(fenced(result['text']) if result.get('text') else f'{status}。请通过上方链接查看原文。')+'\n'
            write(rel,header+body)
            output_notes[key]=rel
            if done%100==0 or done==len(docs):
                print(f'Text: {done}/{len(docs)}; extracted={statuses["extracted"]}, partial={statuses["partial"]}, gaps={done-statuses["extracted"]-statuses["partial"]}',flush=True)
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
            rel=f'04_目录清单/{project_slug(name)}/清单-{page+1:03d}.md'
            pages.append(rel)
            body=f'# {name} · 文件清单 {page+1}\n\n{wiki(project_paths[name],name)}\n\n'
            body+='模型、图纸、图片、代码等保留来源入口。密集数据集文件夹按目录汇总；全部单文件路径可用项目工具 `scripts/pipeline.py search --paths --query "关键词"` 检索。\n\n'
            for rec in display_records[page*350:(page+1)*350]:
                label=rec['relative_path'].split('/',1)[-1] if rec['project']!='根目录资料' else rec['relative_path']
                body+=f'- {original(rec["path"],label)} · {rec["size_bytes"]:,} bytes'
                if rec.get('grouped_count'):
                    body+=f' · **数据/产物文件夹：{rec["grouped_count"]:,} 个文件** · '+json.dumps(rec['extension_summary'],ensure_ascii=False)
                if rec.get('note_path'):
                    body+=' · '+wiki(rec['note_path'],'文字副本')
                body+='\n'
            write(rel,body)
            inventory_pages+=1
        candidates=sorted(text_docs,key=lambda r:r['modified_utc'],reverse=True)
        entry_docs=sorted(text_docs,key=lambda r:(0 if re.search(r'readme|pr[dD]|概览|报告|论文|manuscript|摘要|设计说明',Path(r['path']).name,re.I) else 1, -int(datetime.fromisoformat(r['modified_utc']).timestamp())))[:12]
        body=f'---\nkind: project-index\ncategory: {json.dumps(category_name,ensure_ascii=False)}\ngenerated_at: {json.dumps(now)}\n---\n\n# {name}\n\n'
        body+=f'{wiki("00_开始/项目导航.md","全部项目")} · {wiki("05_研究主题/"+category_name+".md",category_name)} · {original(info["path"],"打开原项目文件夹")}\n\n'
        body+=f'当前目录扫描：**{info["files"]:,} 个文件**，约 **{info["bytes"]/1024**3:.2f} GB**；生成 **{len(text_docs):,} 份文字副本**。\n\n'
        body+='> 分类根据文件夹名称初分，属于导航建议。目录日期、最近修改时间和文件标题不能证明研究已完成或仍在进行。\n\n'
        body+='## 从这些资料开始\n\n'+('\n'.join('- '+wiki(r['note_path'],Path(r['path']).name)+' · '+STATUSES.get(r['extraction_status'],r['extraction_status']) for r in entry_docs) or '这个文件夹暂未找到可提取的文字资料。')+'\n\n'
        body+='## 最近修改的文字资料\n\n'+('\n'.join('- '+wiki(r['note_path'],Path(r['path']).name)+f' · {r["modified_utc"][:10]}' for r in candidates[:8]) or '暂无文字资料。')+'\n\n'
        body+='## 文件清单\n\n'+('\n'.join('- '+wiki(p,Path(p).stem) for p in pages) or '这是一个空目录；已保留项目入口。')+'\n'
        write(project_paths[name],body)
    groups=defaultdict(list)
    for name in summary['projects']:
        groups[category(name)].append(name)
    navigation=f'# 项目导航\n\n{wiki("00_开始/首页.md","回到首页")}\n\n扫描时间：{now}。覆盖 {len(summary["projects"])} 个项目或资料分组。分类是根据目录名称的初步整理，可以在自己的主题笔记中重新组织。\n\n'
    for group,names in groups.items():
        navigation+=f'## {group}\n\n'
        navigation+='\n'.join(f'- {wiki(project_paths[n],n)} · {summary["projects"][n]["files"]:,} 个文件' for n in names)+'\n\n'
        group_body=f'# {group}\n\n{wiki("00_开始/项目导航.md","项目导航")} · {wiki("00_开始/我的研究地图.md","研究地图")}\n\n按来源目录初步归类；主题关联由你后续确认。\n\n'
        group_body+='\n'.join('- '+wiki(project_paths[n],n) for n in names)+'\n\n可以在 `03_我的笔记` 新建主题笔记，并链接这里的项目和来源。\n'
        write(f'05_研究主题/{group}.md',group_body)
    write('00_开始/项目导航.md',navigation)
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
            'automatic_sync':False,'external_upload':False}
    (DATA/'import-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    with (DATA/'catalog.jsonl').open('w',encoding='utf-8') as f:
        for rec in records:
            f.write(json.dumps(rec,ensure_ascii=False)+'\n')
    coverage=f'# 导入覆盖与缺口\n\n{wiki("00_开始/首页.md","首页")}\n\n更新：{now}\n\n'
    coverage+=f'- 扫描来源：`{summary["source_root"]}`\n- 项目/资料分组：{len(summary["projects"])}\n- 文件路径索引：{len(records):,}\n- 来源文件总大小：{summary["bytes"]/1024**3:.2f} GB（没有复制这些大文件）\n- 文字候选：{len(all_docs):,}；实际提取 {len(docs):,}，其中可搜索正文 {usable:,}\n- 测试夹具/生成文档/依赖文档：{len(skipped):,}，保留路径入口，未提取正文\n- 数据集/产物文件夹按目录聚合的文件：{grouped_files:,}；逐文件清单在工作目录的 `data/catalog.jsonl`\n- 自动更新：尚未启用；双击工作目录里的“更新研究索引.cmd”刷新\n- 对外上传：本导入脚本没有上传资料\n\n'
    coverage=coverage.replace('自动更新：尚未启用；双击工作目录里的“更新研究索引.cmd”刷新', '刷新入口：工具项目 Refresh.cmd；每周任务按项目说明另行配置')
    coverage+='## 文字提取状态\n\n| 状态 | 数量 |\n| --- | ---: |\n'+''.join(f'| {STATUSES.get(k,k)} | {v:,} |\n' for k,v in statuses.items())
    coverage+='\n每份文档最多读取 50MB、200000 字符；PDF 最多 100 页，单份提取最多 25 秒。Word 和幻灯片仅提取正文文字，不保留排版、图像或批注。扫描型 PDF 尚未 OCR。正文提取是检索副本，不是逐份研究理解或审核。\n\n'
    coverage+='## 未提取、截断或读取失败的资料\n\n'
    for rec in docs:
        if rec['extraction_status'] not in {'extracted','empty'}:
            coverage+='- '+wiki(rec['note_path'],rec['relative_path'])+' · '+STATUSES.get(rec['extraction_status'],rec['extraction_status'])+'\n'
    coverage+='\n## 扫描边界\n\n不进入依赖、缓存、版本库内部状态、工具运行状态、Unity 和 ROS 的生成缓存、链接目录及本知识库工作区。按常见凭据文件名排除密钥文件；正文中的疑似凭据已隐藏。这里只列被排除入口，不估算入口内部的文件总数。\n\n'
    for item in summary['omitted_entries']:
        coverage+=f'- `{item["path"]}` · {item["reason"]}\n'
    coverage+='\n## 目录扫描错误\n\n'+('无。\n' if not summary['scan_errors'] else '\n'.join(f'- `{x["path"]}` · {x["error"]}' for x in summary['scan_errors'])+'\n')
    if conflicts:
        coverage+='\n## 已保留的手工修改\n\n'+'\n'.join('- '+p for p in conflicts)+'\n'
    write('00_开始/导入覆盖与缺口.md',coverage)
    home=f'''# 我的研究知识库

把过去的研究找回来，继续下一步。

从 **{wiki('00_开始/项目导航.md','项目导航')}** 找到项目；按 **Ctrl + Shift + F** 搜索资料正文；把自己的理解写进 **{wiki('03_我的笔记/我的研究近况.md','我的研究近况')}**。

## 今天从这里开始

- {wiki('00_开始/我的研究地图.md','看看我的研究分布')}：先了解各条研究线。
- {wiki('研究全景.canvas','打开研究全景白板')}：按主题浏览项目。
- {wiki('00_开始/如何使用.md','第一次使用，只看这页')}：搜索、写笔记、链接来源。
- {wiki('00_开始/让 Codex 了解我的研究.md','让 Codex 了解我的研究')}：给它具体问题和来源入口。

## 已接入的资料

**{len(summary['projects'])} 个项目或资料分组 · {len(records):,} 个文件路径 · {usable:,} 份可搜索文字资料**

原资料保留在 `{summary['source_root']}`。文字副本保留来源路径；图纸、模型、图片和代码可从项目清单打开。{wiki('00_开始/导入覆盖与缺口.md','查看覆盖范围和提取缺口')}。

## 写下自己的理解

- {wiki('03_我的笔记/我的研究近况.md','我现在做什么、为什么做、下一步是什么')}
- {wiki('06_模板/研究笔记.md','研究笔记模板')}
- {wiki('06_模板/设计判断.md','设计判断模板')}
- {wiki('06_模板/文献阅读.md','文献阅读模板')}

最近索引更新：{now}。新增资料后，双击工具项目里的 **Refresh.cmd**。每周自动整理需按项目说明设置本机任务。
'''
    write('00_开始/首页.md',home)
    guide='''# 第一次使用

[[00_开始/首页|回到首页]]

## 找资料

按 **Ctrl + Shift + F** 搜全文，比如输入你的项目名或研究关键词。按 **Ctrl + O** 按标题跳转。点开来源摘录，再点“打开原文件”核对完整资料。资料正文是机器提取文字，缺失的图表、公式、页面和扫描文字要回到原文。

## 写自己的笔记

按 **Ctrl + N** 新建笔记；默认保存到 `03_我的笔记`。按 **Ctrl + P**，搜索“插入模板”，选择“研究笔记”“文献阅读”或“设计判断”。写 `[[`，输入项目或资料名称，选中即可建立链接。

只需要记录三件事：我看到了什么；我现在怎样理解；下一步要核对或做什么。引用来源后，反向链接会帮助你回到依据。不要把目录归组、自动摘录和自己的判断混在一起。

## 看项目关联

打开 [[研究全景.canvas|研究全景白板]]，双击主题或项目卡片。关系图谱默认只显示项目、主题和自己的笔记，避免数千份来源挤满屏幕。白板上的主题分类是初步导航，不代表已验证的研究关系。

## 保持资料更新

在文件管理器中打开工具项目，双击“Refresh.cmd”；等窗口显示完成后再返回 Obsidian。索引是快照，不会实时跟踪源目录。更新脚本保留手工修改过的自动笔记并报告冲突，也保留个人笔记；已删除来源的旧摘录不会自动删除，核对时以原文件是否存在为准。

这份库使用本地 Markdown 和 Obsidian 核心功能。已有仓库保留，可在 Obsidian 中切换。每周自动整理的配置见工具项目说明。

官方说明：[创建或打开本地仓库](https://obsidian.md/help/vault)、[全文搜索](https://obsidian.md/help/plugins/search)。
'''
    write('00_开始/如何使用.md',guide,once=True)
    codex='''# 让 Codex 了解我的研究

[[00_开始/首页|首页]] · [[00_开始/我的研究地图|研究地图]] · [[03_我的笔记/我的研究近况|我的研究近况]]

## 现在可以直接这样说

> 先读我的研究近况和项目导航，再根据当前来源文件告诉我：我有哪些研究线，每条线有哪些资料、哪些状态还需要我确认。每个结论都给出来源。

> 在知识库中查找这个项目的实验报告、论文稿和局限说明，区分计划、已运行结果和已验证结论；给我一条可核对的来源路径。

> 找出两个项目之间可以复用的判断，先列证据和适用条件，再把我确认的理解整理进个人笔记。

> 更新我的研究索引，再根据最近修改的研究资料帮我起草研究近况；把目录事实、文档陈述和你的推测分开。

## 它怎样了解我

Obsidian 是资料库；Codex 在有访问权限的当前项目里，根据问题读取导航、摘录和原始材料。工作目录的 `AGENTS.md` 提供读取路线，工具项目的 `scripts/pipeline.py context --query "关键词"` 提供有界的来源片段。先读 `03_我的笔记/我的研究近况.md`，再读相关项目和原文。

导入不会让模型永久记住整个硬盘，也没有把全部资料上传到云端。你在其他项目或聊天里使用时，请指明这个知识库路径并提供访问权限；不要默认那些聊天已经读过这里的资料。与 Codex 对话时，实际提供给模型的相关片段会按该产品当前的数据设置处理。

## 为什么要写研究近况

目录能说明你保存了哪些材料，不能准确说明你现在的优先级、采用了哪个版本、是否完成研究或为什么作出某个判断。把这些信息写进“我的研究近况”，比让 AI 猜测更可靠。这里的初步主题归类来自目录名称，需要你确认。
'''
    write('00_开始/让 Codex 了解我的研究.md',codex,once=True)
    write('03_我的笔记/我的研究近况.md','''# 我的研究近况

[[00_开始/首页|首页]] · [[00_开始/我的研究地图|资料中的研究分布]]

> 这页由你填写或在你确认后由 Codex 整理。目录扫描不能替你确认当前状态。

## 我现在最关注的问题

待填写。

## 正在推进的项目

- 项目：
- 当前版本与阶段：
- 本周进展：
- 下一步：
- 对应来源：

## 暂停或已完成的项目

待填写；不根据文件日期自动判定。

## 我希望 Codex 怎样帮助我

先查来源，再下结论；区分原始事实、文档陈述、系统推断和我确认的判断。整理结果保存为可编辑笔记，重要原文件修改需要按当次要求另行处理。
''',once=True)
    templates={
        '研究笔记':'# {{title}}\n\n日期：{{date}}\n\n## 我在解决什么问题\n\n\n## 原始资料与观察\n\n来源：[[项目或资料名称]]\n\n## 我的理解\n\n\n## 下一步与待核对事项\n\n- [ ] \n',
        '设计判断':'# {{title}}\n\n日期：{{date}}\n\n## 适用项目、版本与条件\n\n\n## 来源与证据\n\n\n## 我的判断及理由\n\n\n## 代价和不确定性\n\n\n## 下一版怎样验证\n\n- [ ] \n',
        '文献阅读':'# {{title}}\n\n日期：{{date}}\n\n## 文献信息\n\n作者、年份、版本、DOI：\n\n来源：[[文字副本]]\n\n## 原文实际研究了什么\n\n\n## 方法、结果与局限\n\n\n## 与我的研究的关系\n\n\n## 可以引用的证据位置\n\n页码、章节：\n',
        '每日记录':'# {{date}}\n\n## 今天推进的项目\n\n\n## 新资料与新的理解\n\n\n## 下一步\n\n- [ ] \n'}
    for title,body in templates.items():
        write(f'06_模板/{title}.md',body,once=True)
    overview='# 我的研究地图\n\n[[00_开始/首页|首页]] · [[00_开始/项目导航|完整导航]] · [[03_我的笔记/我的研究近况|补充当前研究近况]]\n\n这是一张根据当前目录整理的资料地图。它说明资料分布，不自动判断哪些项目在进行、已完成或已被采用。\n\n'
    for group,names in groups.items():
        overview+=f'## {group}\n\n'+wiki(f'05_研究主题/{group}.md','查看主题下的全部项目')+'\n\n'
        overview+='\n'.join('- '+wiki(project_paths[n],n) for n in names[:8])+'\n\n'
    overview+='## 需要由我确认\n\n- 当前最重要的研究问题和项目是什么？\n- 每条研究线采用哪个版本、处于什么阶段？\n- 哪些判断已完成验证，哪些还只是计划或草稿？\n\n答案写进 [[03_我的笔记/我的研究近况]]；不要从文件夹日期猜测。\n'
    write('00_开始/我的研究地图.md',overview)
    nodes=[{'id':'home','type':'file','file':'00_开始/首页.md','x':0,'y':0,'width':360,'height':230}]
    edges=[]
    for i,(group,names) in enumerate(groups.items()):
        x=(i%3)*800-800
        y=(i//3)*740+420
        gid=f'group{i}'
        nodes.append({'id':gid,'type':'file','file':f'05_研究主题/{group}.md','x':x,'y':y,'width':340,'height':190,'color':str(i%6+1)})
        edges.append({'id':f'e{i}','fromNode':'home','fromSide':'bottom','toNode':gid,'toSide':'top','label':'目录导航'})
        selected=sorted(names,key=lambda n:summary['projects'][n]['text_candidates'],reverse=True)[:3]
        for j,n in enumerate(selected):
            nid=f'p{i}-{j}'
            nodes.append({'id':nid,'type':'file','file':project_paths[n],'x':x-40+j*135,'y':y+260+j*90,'width':270,'height':130})
            edges.append({'id':f'ep{i}-{j}','fromNode':gid,'fromSide':'bottom','toNode':nid,'toSide':'top'})
    write('研究全景.canvas',json.dumps({'nodes':nodes,'edges':edges},ensure_ascii=False,indent=2),once=True)
    plugins={name:True for name in ['file-explorer','global-search','switcher','graph','backlink','canvas','outgoing-link','tag-pane','properties','page-preview','daily-notes','templates','note-composer','command-palette','editor-status','bookmarks','outline','word-count','file-recovery']}
    for name in ['publish','sync','markdown-importer','audio-recorder','slides','workspaces']:
        plugins[name]=False
    configs={
        'app.json':{'newFileLocation':'folder','newFileFolderPath':'03_我的笔记','attachmentFolderPath':'07_附件','alwaysUpdateLinks':True,'showLineNumber':False,'readableLineLength':True},
        'core-plugins.json':plugins,
        'appearance.json':{'baseFontSize':17,'cssTheme':'','enabledCssSnippets':['research-vault']},
        'templates.json':{'folder':'06_模板','dateFormat':'YYYY-MM-DD','timeFormat':'HH:mm'},
        'daily-notes.json':{'folder':'03_我的笔记/日记','template':'06_模板/每日记录','format':'YYYY-MM-DD'},
        'graph.json':{'search':'-path:"02_资料" -path:"04_目录清单" -path:"06_模板"','showTags':False,'showAttachments':False,'hideUnresolved':True,'showOrphans':True},
        'bookmarks.json':{'items':[{'type':'file','path':'00_开始/首页.md','title':'研究首页'},{'type':'file','path':'00_开始/项目导航.md','title':'全部项目'},{'type':'file','path':'03_我的笔记/我的研究近况.md','title':'我的研究近况'},{'type':'file','path':'研究全景.canvas','title':'研究全景'}]},
        'workspace.json':{'main':{'id':'main','type':'split','children':[{'id':'tabs','type':'tabs','children':[{'id':'homeleaf','type':'leaf','state':{'type':'markdown','state':{'file':'00_开始/首页.md','mode':'preview','source':False},'title':'我的研究知识库'}}]}],'direction':'vertical'},'active':'homeleaf','lastOpenFiles':['00_开始/首页.md']}}
    for name,obj in configs.items():
        write('.obsidian/'+name,json.dumps(obj,ensure_ascii=False,indent=2),once=True)
    write('.obsidian/snippets/research-vault.css','.markdown-preview-view { --file-line-width: 820px; }\n.markdown-preview-view h1 { margin-bottom: 1.1em; }\n.markdown-preview-view pre code { font-family: var(--font-text); font-size: 0.94em; white-space: pre-wrap; overflow-wrap: anywhere; }\n',once=True)
    (VAULT/'07_附件').mkdir(exist_ok=True)
    state['built_at']=now
    state_path.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
    report['protected_modified_notes']=list(conflicts)
    (DATA/'import-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
