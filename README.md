# Obsidian Research Pipeline

把已有研究文件夹变成有来源、可搜索、可持续整理的本机 Obsidian 知识库。原文件保留在原处，个人理解写进独立笔记；Agent 可以按问题检索、核对原文，再保存有依据的结论。

## 三步开始（Windows 10/11）

1. 下载本项目 ZIP 并解压到一个固定、可写的文件夹。不要只在 ZIP 预览中运行。
2. 双击 **Start.cmd**，选择研究资料所在文件夹。已有 Python 3.11+ 和 Obsidian 会被复用；缺少时通过 Windows Package Manager 安装，Python 依赖放在项目自己的 `.runtime/venv`。
3. 等待首页打开，按 **Ctrl + Shift + F** 搜索资料，在 **03_我的笔记** 写自己的理解。在 Codex 中打开输出工作区，告诉它先读研究近况，再按来源回答。

默认输出是项目的 `.runtime/workspace/研究知识库`。大规模目录的首次扫描和文字提取可能需要数分钟；Obsidian 之后还会建立自己的搜索索引。首次运行需要联网安装缺少的软件和依赖；整理和检索本身不调用网络或模型 API。如果已有 Obsidian 正在运行且新仓库尚未注册，脚本完成建库后会提示关闭 Obsidian 一次，再双击 **Open.cmd**；已有仓库和登录配置会被保留。

缺少 `winget` 时先安装 Microsoft App Installer。Obsidian 来自其发布渠道，本项目不分发或改变 Obsidian 的许可。[Obsidian 下载](https://obsidian.md/download)、[Microsoft 安装参数说明](https://learn.microsoft.com/en-us/windows/package-manager/winget/install)。

## 你会得到什么

| 入口 | 用途 |
| --- | --- |
| `00_开始` | 首页、项目导航、研究地图、覆盖报告、使用说明 |
| `01_项目` / `05_研究主题` | 按来源目录整理的导航；分类仅是可配置建议 |
| `02_资料` | Markdown、TXT、PDF、Word、幻灯片等的文字快照与来源路径 |
| `03_我的笔记` | 作者近况、自己的判断、每次整理的变化记录 |
| `04_目录清单` | 图片、代码、模型等的原文件入口；密集数据集按目录汇总 |
| `研究全景.canvas` | Obsidian 内可编辑的项目地图 |
| `data/import-report.json` | 覆盖、缺口、扫描错误和受保护的手工修改 |

**Refresh.cmd** 更新索引，**Open.cmd** 打开首页。主题规则可以在忽略提交的 `settings.local.json` 中加入 `categories`，格式见 `settings.example.json`。换位置前请同步修改本机配置和自动任务；原文件链接使用绝对路径。

## 每周自动整理

有两种入口，选一个即可：

- **只需要自动更新索引**：双击 **Enable-Weekly.cmd**，创建 Windows 本机任务，每周日 20:00 运行。电脑需要开机且用户已登录；错过执行后可在下一次可运行时补跑。不会调用付费模型。移除命令：`powershell -NoProfile -File scripts/schedule.ps1 -Remove`。
- **希望 Agent 解读新资料并提醒**：在 Codex 中打开输出工作区，创建每周日 20:00 的自动化任务，使用 [自动整理提示词](docs/automation.md)。它先刷新，再核对有变化的原文，把理解和版本冲突写成另一份个人笔记。没有变化时保持安静。需要本机目录权限、现有 Codex 登录及运行环境。

本项目不会自动把 Windows 定时任务和 Codex 自动化同时打开。GitHub Actions 只测试合成样例，不访问你的电脑或研究库。

## Agent 怎样借鉴

在输出工作区开始 Codex 任务，生成的 `AGENTS.md` 会告诉它先读作者近况、按问题检索、检查覆盖与来源。Codex 的项目指令发现方式见 [OpenAI Docs](https://learn.chatgpt.com/docs/agent-configuration/agents-md)。其他 Agent 也可以执行同一组 CLI 命令；需由你给予目录访问权限。这个库不使所有聊天自动获得永久记忆。

```powershell
# 在项目根目录执行；中文、空格路径均支持。
.runtime\venv\Scripts\python.exe scripts\pipeline.py context --config settings.local.json --query "实验 局限" --limit 8
.runtime\venv\Scripts\python.exe scripts\pipeline.py search --config settings.local.json --query "模型" --paths --limit 8
```

`context` 返回作者近况、覆盖报告和有界来源片段。匹配结果标记原文件是否存在、是否与摘录哈希相符。重要结论必须回看原文的页码、段落或版本；图片和模型需要额外工具。把最后理解保存在 `03_我的笔记`，附来源与不确定性。示例指令：

> 先读我的研究近况，从知识库找到与这个问题有关的资料，核对原文后回答。区分原文陈述、你的推断和我确认的判断。把有依据的结论另存成个人笔记。

## 保留与覆盖规则

原研究目录只读；大型资产不复制。刷新以大小和修改时间发现来源变化，并缓存提取结果。生成页有内容哈希，手动改过的页会保留并记录冲突；个人近况和笔记不会覆盖。已删除原文件的摘录保留为历史，Agent 检索会标注原文已不存在。

每次完整变化保存在 `data/runs/<run_id>/changes.jsonl`；Markdown 记录每类前 100 条，避免大量资产挤满笔记。无变化且无错误时不新增整理笔记。目录变化记录是可核对的事实，Agent 的解释、作者确认和验证结果需要分别记载。

源码仓库忽略本机配置、运行时、资料索引、摘录、知识库和凭据。不要用 `git add -f` 加入这些目录。发布前可运行 `python scripts/audit_publication.py` 核对已暂存文件；它只做明确规则检查，不替代保密审查。使用云端 Agent 时，被选择提供给模型的资料片段仍按相应产品的数据设置处理。

## 当前缺陷与后续扩展

| 现有限制 | 下一步可扩展 |
| --- | --- |
| 扫描 PDF 无 OCR；图表、公式、批注和 CAD 几何没有完整理解 | 按需 OCR、页面图像核对与模型查看器 |
| 字面检索需要关键词相近，尚无语义检索或排序 | 本机全文数据库、中文分词与可选本机向量索引 |
| 目录名分类是建议；文件日期不能判断研究完成或当前重点 | 作者确认近况、条件明确的判断卡、版本冲突列表 |
| 大目录每次仍重新扫描，构建会加载完整目录清单 | 流式构建、增量文件监听、按项目刷新 |
| 原文件迁移会使绝对链接失效；笔记移动后生成保护仍依赖原路径 | 路径映射、稳定文档 ID 与移动迁移工具 |
| 无跨机器同步、MCP 服务、自动 AI API 调用或全部原文审查 | 有访问范围的检索 MCP；可选同步与人工确认的写回 |

## 开发与验证

Python 3.11+；核心管线也可以在 Linux 上运行，软件安装和桌面入口目前针对 Windows。已有 Python 时：

```powershell
python -m pip install -r requirements.txt
python scripts/pipeline.py setup --source "C:\Research" --workspace ".runtime\workspace"
python -m unittest discover -s tests -v
```

测试只使用合成资料，验证来源不变、提取格式、来源变化、手工笔记保护、删除快照、无变化安静、路径排除、名称冲突和检索时的原文哈希。CI 在 Windows / Linux 的 Python 3.11 和 3.12 上运行。不在 CI 中安装 Obsidian，也不把这些测试当成新电脑安装或研究结论的验证。

代码采用 MIT License；各依赖、Obsidian 和用户资料分别遵循自己的许可。
