# 版本记录 / Release notes

[简体中文首页](../README.md) · [English home](../README.en.md)

## v0.2.0 — 个人知识工作台 / Personal knowledge workspace

- 从研究资料工具拓展为工作、学习、创作、生活计划与研究的长期个人知识工作台。
- GitHub 仓库重命名为 [`obsidian-knowledge-workspace`](https://github.com/renyuxin6666-tech/obsidian-knowledge-workspace)；现有本机文件夹、知识库路径、配置与定期任务继续使用。
- 增加中文、英文 README，真实脱敏界面图与流程说明；最先展示一句话交给 Codex 安装的入口。
- 新建知识库支持中文 / 英文页面、模板与指引；保留原有研究库目录，避免链接和笔记被改名。
- 提供 Codex 插件包、仓库 marketplace 与安装、检索、定期整理工作流。仓库分发不等于通用公开 Plugins Directory 上架。
- 定期整理复用已有任务，按本机工作区核对变化，分别保存自动日志与 Agent 理解。

Expanded from a research-only tool into a personal workspace for work, learning, creative projects, planning and research. Added bilingual documentation, redacted real screenshots, new-vault language selection and a repository-distributed Codex plugin with setup, retrieval and upkeep workflows. The GitHub repository is now `obsidian-knowledge-workspace`. Existing local folders, vault paths, settings and schedules are preserved.

## v0.1.1 — 中文路径打开修复 / Chinese-path opening fix

修复 Windows 中文路径打开首页时的 “Vault not found”。打开入口使用已注册仓库 ID 和笔记相对路径，保留现有注册和语言；本机首页与桌面快捷方式经过实际验证。加入仓库注册与 URI 回归测试。

Fixed Windows home-page launching with Chinese paths by using the registered vault ID and a relative note path. Existing registration and language are preserved. The local home page and desktop shortcut were checked in Obsidian.

## v0.1.0 — 首次发布 / Initial release

选择资料文件夹，建立可追溯的本机 Obsidian 知识库；提供文字快照、来源检索、Agent 上下文入口、每周整理提示词与可选 Windows 定时索引。

Initial local-vault pipeline: source-folder selection, text snapshots, source-linked retrieval, bounded agent context, weekly upkeep guidance and optional Windows index scheduling.

## 验证范围 / Validation scope

发布包只含工具、文档、审查后的脱敏图片和合成测试。已有软件复用、独立依赖安装、合成资料建库及中文路径打开已在本机验证。Windows / Linux CI 运行核心管线测试；测试数量与结果以对应版本的工作流记录为准。

本机 Codex 原生 CLI 已实装并确认插件处于 installed / enabled 状态，现有知识库已绑定；已有配置和其他插件保持不变。新建中英文知识库、默认本机时区、来源校验与旧库兼容通过本地测试。缺少 Obsidian / Python 时的 WinGet 安装分支已实现，尚未在全新 Windows 电脑完整验收；新对话中的技能自动选择仍需独立验收。

Packages contain tools, documentation, reviewed redacted images and synthetic tests. Existing-software reuse, isolated dependency setup, synthetic vault creation and Chinese-path opening have been verified locally. The native Codex CLI confirmed installed/enabled plugin state and the existing workspace was bound, preserving other settings and plugins. Windows / Linux CI covers the core pipeline; consult the matching release workflow for results. Fresh-machine software installation and automatic skill selection in a new conversation still require separate acceptance checks.

扫描 PDF 无 OCR，尚无语义检索、跨机器同步或完整的图像 / 模型理解。原文件与个人笔记保留；删除来源可留下历史快照，引用前需要检查原文。
