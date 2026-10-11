<p align="center">
  <a href="README.md">简体中文</a> · <a href="README.en.md">English</a>
</p>

<h1 align="center">Obsidian 个人知识工作台</h1>

<p align="center"><strong>把散落的资料，变成可以积累、查找、继续工作的个人知识库。</strong></p>

<p align="center">Obsidian 保存资料与理解 · Codex 按来源回答 · 定期任务帮你持续整理</p>

<p align="center">
  <a href="https://github.com/renyuxin6666-tech/obsidian-research-pipeline/actions/workflows/test.yml"><img src="https://github.com/renyuxin6666-tech/obsidian-research-pipeline/actions/workflows/test.yml/badge.svg" alt="管线测试"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-467B70" alt="MIT License"></a>
  <img src="https://img.shields.io/badge/vault-中文%20%2F%20English-7562A8" alt="中文与英文知识库">
</p>

## Obsidian 是什么？

[Obsidian](https://obsidian.md/) 是一款把笔记保存在本机的知识管理软件。你可以写笔记、搜索内容，把相关笔记互相链接，或者用白板梳理资料与项目的关系。它把一组笔记所在的文件夹叫作 **Vault（知识库）**；笔记是普通的 Markdown 文本文件，方便长期保存和继续编辑。

**这个项目帮你把它用起来。** Obsidian 负责保存、阅读和连接笔记；本工具把已有资料建立成带来源的导航与可搜索摘录；Codex 帮你查资料、核对原文、保存理解，并按你选的时间持续整理。可以从工作、学习、生活或研究文件夹开始。

![资料、知识库与 Codex 的工作关系](docs/assets/hero.svg)

<p align="center"><a href="#开始使用">开始使用</a> · <a href="#看看整理后的样子">实际界面</a> · <a href="#让-codex-接着你的积累工作">与 Codex 一起工作</a> · <a href="#每周自动整理">定期整理</a> · <a href="#常见问题">常见问题</a></p>

## 开始使用

在能访问本机文件夹的 **Codex 桌面任务** 中，发送这一句话：

> 安装 https://github.com/renyuxin6666-tech/obsidian-research-pipeline，接入我的「资料文件夹」，用于长期知识与项目管理，并按我的时区每周日 20:00 自动整理。

把「资料文件夹」换成实际路径；还没选好时，直接让 Codex 帮你选择。它会复用已有软件，建立知识库，核对打开结果，再在支持本机定期任务的客户端中创建或复用任务。首次安装需要网络、可用的 Python / Obsidian 安装渠道及相应权限；遇到这些条件不足时，Codex 会说明具体缺口。

**无需先学命令，也无需预先把资料整理好。** 工作资料、课程与阅读、生活计划、创作和研究都可以从现有文件夹开始。

<details>
<summary>不用 Codex，直接在 Windows 建库</summary>

1. 从 [Releases](https://github.com/renyuxin6666-tech/obsidian-research-pipeline/releases/latest) 下载 ZIP，解压到固定的可写文件夹。
2. 双击 **Start.cmd**，选择资料文件夹。已有 Python 3.11+ 和 Obsidian 会被复用；缺少时尝试通过 Windows Package Manager 安装。
3. 首页打开后，按 **Ctrl + Shift + F** 搜索，在 **我的笔记** 中保存自己的理解。

默认知识库是 `.runtime/workspace/个人知识库`。**Refresh.cmd** 更新资料，**Open.cmd** 打开首页。首次大目录扫描和 Obsidian 搜索索引需要时间。

需要英文界面时，让 Codex 使用英文建立工作台，或运行 `powershell -NoProfile -File scripts/bootstrap.ps1 -Language en`。原有研究知识库继续使用原来的目录和笔记，不会自动改名。

没有 `winget` 时，先安装 [Microsoft App Installer](https://learn.microsoft.com/en-us/windows/package-manager/winget/)。Obsidian 从其发布渠道安装：[官方下载](https://obsidian.md/download)。

</details>

## 看看整理后的样子

![真实个人知识库的首页，敏感内容已遮盖](docs/assets/workspace-redacted.png)

*实际本机知识库首页，已遮盖作者标识、本机路径和私人项目标签。来源入口、覆盖说明和个人笔记放在一起。*

![真实个人知识库的项目地图，敏感内容已遮盖](docs/assets/map-redacted.png)

*实际 Obsidian Canvas 资料地图，私人项目标签已遮盖。它帮助你找到已有材料；项目状态与结论是否已采用，需要由你确认。截图来自保留原命名的研究资料案例，新知识库使用通用命名。*

## 从保存资料，到继续工作

| 你的积累 | 工作台怎样帮助你 |
| --- | --- |
| 工作项目、会议记录、产品资料 | 找回相关来源，记录决策理由与下一步，保留不同版本 |
| 阅读、课程、长期学习 | 搜索已有摘录，连接主题，把自己的理解写成可复用笔记 |
| 创作、设计、生活计划 | 汇总材料入口，记录选择、条件与复盘，延续之前的工作 |
| 论文、实验、研究资料 | 回到原文和版本，标出提取缺口、证据与待确认判断 |

原文件留在原处。知识库保存导航、文字快照、来源链接和你的理解；图片、代码、模型等大型资产以原文件入口为主。

| 知识库入口 | 中文 / English | 用途 |
| --- | --- | --- |
| 开始 | `00_开始` / `00_Start` | 首页、资料地图、使用方法、覆盖与缺口 |
| 项目与主题 | `01_项目`、`05_主题` / `01_Projects`、`05_Topics` | 按来源整理的导航，可继续重新组织 |
| 资料 | `02_资料` / `02_Sources` | 文本快照及准确的原文路径 |
| 我的笔记 | `03_我的笔记` / `03_My_Notes` | 当前重点、自己的判断、整理记录 |
| 清单与模板 | `04_目录清单`、`06_模板` / `04_File_Lists`、`06_Templates` | 非文本资产入口，阅读、知识与决策笔记模板 |

中文和英文模式也覆盖新建知识库的页面、模板和工作指引。已有知识库保留原路径，避免打断链接和手写笔记。

## 让 Codex 接着你的积累工作

> 从我的知识库找出与这个问题有关的资料，核对原文后回答，并把有依据的结论保存成个人笔记。

先在 **我的近况 / My Current Focus** 写下当前重点、正在做的事情与待解决问题。空白字段会被当作未知；目录名和文件日期不会替你决定优先级。

本项目包含 Codex 插件包和三个工作流：

| 工作流 | 用途 |
| --- | --- |
| `$setup-knowledge` | 安装、选择资料、建立或接入本机知识库 |
| `$knowledge-retrieval` | 按问题读取有限的来源片段，核对版本后回答 |
| `$maintain-knowledge` | 刷新变化，写独立理解笔记，维护定期整理任务 |

插件通过项目自己的 [marketplace](.agents/plugins/marketplace.json) 分发；这是本机 / 仓库安装入口，尚未上架通用公开 Plugins Directory。支持的客户端可以加载插件工作流，普通本机 Codex 任务也可以直接按项目指引使用管线。[插件安装与管理](docs/codex-plugin.md) · [OpenAI 官方文档](https://developers.openai.com/plugins/build/plugins)。

Agent 会检查原文件是否仍存在、摘录是否匹配来源哈希，再回看原文。**知识库提供可查的上下文；其他聊天需要获得目录访问权限并实际读取这些资料。** 它不会自动变成所有模型的永久记忆。

## 每周自动整理

![每周整理流程：更新资料、核对来源、保存理解、必要时提醒](docs/assets/weekly-flow.svg)

首次给 Codex 的安装指令已经包含每周日 20:00。也可以随时说：

> 把我的知识库整理改成每周五 18:00；没有有用变化时保持安静，有重要变化、明确冲突或运行失败时提醒我。

每次任务先刷新索引，读取本次变化，再选读相关原文。自动变化日志和 Agent 的理解分别保存，原资料与手写笔记得到保留。已有任务会被复用或修改，避免重复执行。[完整整理提示词](docs/automation.md)。

本机任务运行时，电脑需要开机、桌面应用保持运行、目录可访问；网页端任务不能直接整理本机文件夹。具体运行条件见 [OpenAI 定期任务说明](https://learn.chatgpt.com/docs/automations)。

只想定时更新索引时，可以用 **Enable-Weekly.cmd** 创建 Windows 本机任务。它不调用模型；与 Codex 定期整理选一个即可。GitHub Actions 只验证合成样例，不访问你的资料。

## 常见问题

**原资料会被移动或覆盖吗？** 原资料只读，新内容写入知识库。刷新会保护手工修改的生成页和个人笔记。原文件删除后，历史摘录可能保留；引用前仍需检查原文存在性。

**资料会上传到 GitHub 吗？** 发布包只包含工具、文档、脱敏图片和合成测试，本机配置与知识库被排除。使用 Codex 时，它选择读取的内容仍受对应产品的数据设置约束。[隐私与资料边界](docs/privacy.md)。

**能完整理解扫描 PDF、图片和 CAD 吗？** 当前无 OCR、语义检索或完整的图像 / 模型理解。PDF、Word、幻灯片等做有上限的文字提取，覆盖报告会记录缺口；重要结论需要原文核对。

**只能用来做研究吗？** 工作、学习、创作、生活和研究都适用。仓库地址保留早期名称，方便现有安装继续更新；新知识库采用通用命名。

**支持哪些系统？** 双击安装入口针对 Windows 10/11。Python 核心管线在 Windows / Linux 的 CI 中验证；其他系统的软件安装与桌面入口需要自行配置。缺少软件的 WinGet 分支已实现，尚未在全新 Windows 电脑完整验收。

<details>
<summary>开发、命令与现有限制</summary>

Python 3.11+。在项目根目录执行：

```powershell
python -m pip install -r requirements.txt
python scripts/pipeline.py setup --source "C:/Knowledge" --workspace ".runtime/workspace" --language zh
python scripts/pipeline.py context --config settings.local.json --query "决策 条件" --limit 8
python -m unittest discover -s tests -v
```

`context` 提供当前重点、覆盖信息和有限的来源片段；`search --paths` 查找非文本资产。`settings.local.json` 保存本机路径、语言与分类规则，不应提交。

扫描和文字提取有大小、字符、页数与时间上限；完整刷新仍扫描目录，大型资产清单会占用内存。绝对来源链接在资料搬家后需要调整。扫描 PDF 无 OCR，尚无语义检索、跨机器同步或后台云服务。可继续扩展本机全文检索、按需 OCR、稳定文档 ID、按项目增量整理和有范围的 MCP 检索。

测试使用合成资料，验证来源保护、变化记录、手工笔记保护、历史快照、检索来源哈希、中文路径打开和语言模式。测试通过不等于所有新电脑安装或资料结论已被验证。[版本记录](docs/release-notes.md)。

</details>

代码采用 [MIT License](LICENSE)。Obsidian、依赖软件和你的资料各自遵循其许可。
