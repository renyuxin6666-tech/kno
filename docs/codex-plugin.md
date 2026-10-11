# Kno Codex plugin / Kno Codex 插件

[中文](#中文) · [English](#english)

## 中文

在有本机文件权限的 Codex 对话里说：

> 安装 https://github.com/renyuxin6666-tech/kno，接入我的「资料文件夹」，作为长期知识和工作项目管理工具，每周日 20:00 自动整理。

把「资料文件夹」替换成自己的路径。已有知识库时提供它的工作区或 `settings.local.json`，Codex 会复用，避免重复导入。首次建立只需确定资料目录；输出位置和中文/英文可从当前请求推断，不明确时再询问。

Kno 插件提供三个技能：

| 技能 | 用途 |
| --- | --- |
| `$setup-knowledge` | 连接资料、建立或重连知识库，并安排你要求的 Codex 定期任务 |
| `$knowledge-retrieval` | 回答前检索本机材料，核对来源是否存在、是否变化 |
| `$maintain-knowledge` | 刷新索引、解释有意义的变化，另存可追溯的理解笔记 |

技能可以按请求自动选择。范围覆盖学习记录、工作项目、决策、创作和研究；具体目录与分类由你的资料决定。

### 安装与状态

仓库包含标准 `plugin.json`、旧版客户端需要的 `.codex-plugin/plugin.json` 兼容清单，以及 `.agents/plugins/marketplace.json`。使用已经安装的 Python 运行：

```text
python scripts/install_codex_plugin.py install
```

安装器按明确的公开文件清单导出工具源码与已审核图片，临时 Markdown、原始截图、运行目录和本机配置均不按扩展名自动加入。清单不能代替清单内文件的内容审查。它通过 Codex 原生 CLI 注册仓库来源，有 `codex plugin add` 能力的版本会继续安装，并用 `codex plugin list --json` 核对 `installed` 和 `enabled`。它会备份现有 Codex 配置，仅更新自己的插件来源，保留其它插件。缺少安装命令的版本会停在“来源已注册”，提示刷新或重启应用后从该来源安装；不会把来源注册写成安装成功。当前对话的技能列表可能需要新对话或应用刷新才能更新。

标准仓库来源命令也可使用：

```text
codex plugin marketplace add renyuxin6666-tech/kno
```

这属于仓库/本机来源分发，尚未代表被通用公共插件目录审核收录。支持能力与刷新要求以当前 Codex 版本为准。[官方打包与来源文档](https://developers.openai.com/plugins/build/plugins)

### 插件升级不会丢失资料连接

运行工具和私有配置位于稳定的本机知识工作区，插件缓存仅带源码和技能。设置技能会准备工作区并记住你明确接入的路径。已有工作区可手动绑定：

```text
python scripts/install_codex_plugin.py bind-workspace --config /path/to/settings.local.json
python scripts/install_codex_plugin.py workspaces
```

路径登记保存在该插件自己的本机目录中。它不授予其它对话文件权限，也不让所有 Agent 自动读取全部资料。检索时只选择与你问题相关的片段；原件与知识库不会通过这个插件自动公开或云同步。

定期整理由真实的 Codex 自动化任务运行，设置时检查相同工作区的已有任务并复用。只有自动化工具确认成功后，才报告安排完成。电脑、应用和资料访问条件需要在执行时可用；无法创建任务时会提供可粘贴提示词并说明限制。[定期整理说明](automation.md)

## English

Say this in a Codex conversation with access to your local files:

> Install https://github.com/renyuxin6666-tech/kno, connect my “material folder” as a long-term personal knowledge and project workspace, and organize it every Sunday at 20:00.

Replace the folder with your own path. Supply an existing workspace or its `settings.local.json` to reconnect without importing another vault. Kno’s three skills handle setup (`$setup-knowledge`), evidence retrieval (`$knowledge-retrieval`) and meaningful upkeep (`$maintain-knowledge`). They support learning, work, decisions, creative projects and research in your chosen material language.

Run `python scripts/install_codex_plugin.py install` from the downloaded project. The installer exports an explicit list of public tool files and reviewed images; scratch Markdown, raw screenshots, runtime folders and local configuration are not included by file extension. The list does not replace a content review of those named files. It registers its own local marketplace through the native Codex CLI and installs when the host supports `codex plugin add`. It verifies the installed/enabled fields, backs up existing configuration and preserves unrelated plugins. Older hosts may require app refresh/restart and installation from the registered source; registration alone is not installation. A new conversation or app refresh may be needed to discover newly installed skills.

This is repository/local marketplace distribution, not approval for the universal public plugin directory. The portable manifest and marketplace follow the [official packaging documentation](https://developers.openai.com/plugins/build/plugins).

Runtime and private configuration live in a stable local output workspace, outside replaceable plugin caches. Explicit bindings can be inspected with `workspaces` and added with `bind-workspace --config ...`. Another chat still needs file access. Only relevant excerpts are retrieved; this plugin does not publish or cloud-sync your original material or vault.

Requested recurring work is scheduled through Codex's actual automation tool, reusing a matching existing task. A generated prompt is not a confirmed schedule. The local computer, app and file permissions must be available at execution time. See [scheduled upkeep](automation.en.md) for the workflow and limitations.
