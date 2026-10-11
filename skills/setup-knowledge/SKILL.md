---
name: setup-knowledge
description: Set up or reconnect a local Obsidian personal knowledge workspace for long-term learning, work, projects or research, and arrange user-requested Codex upkeep. 安装或接入个人知识工作台，按需安排定期整理。
---

# Set up a personal knowledge workspace

Use this skill when the user wants local material to become an Obsidian knowledge workspace. Follow the user's language. A request such as “接入我的资料文件夹，每周日 20:00 自动整理” already supplies the intended source and recurring work; do not ask for those choices again.

## Find the package and the existing workspace

Resolve `<plugin-root>` from this loaded skill: it is the parent of `skills/`, including when installed inside a plugin cache. The package includes `scripts/install_codex_plugin.py` and `scripts/pipeline.py`. Do not assume a separate checkout or standalone skill exists.

When this setup starts from a downloaded/cloned repository in response to an installation request, explicitly complete plugin installation before claiming it is available. First run the read-only check:

```text
python <plugin-root>/scripts/install_codex_plugin.py status
```

If its selector is already `installed=true` and `enabled=true`, reuse it; do not reinstall or update it merely to run setup. If `package_origin` is `cached_plugin`, this skill is already executing from the installed plugin package: do not recursively install another copy. For a repo-origin install request with a confirmed missing/disabled plugin, run:

```text
python <plugin-root>/scripts/install_codex_plugin.py install
```

Inspect the resulting native installation/enabled state. Registering a marketplace alone is not installing the plugin. If the host cannot confirm native installation, follow the returned app refresh/install guidance and report that limitation while finishing the local workspace; do not guess success from a process exit code. New conversations may need an app refresh to discover the skills. A loaded plugin's onboarding workflow should continue directly to its workspace setup instead of installing itself again.

First use a configuration explicitly linked by the current user or this workspace's `AGENTS.md`. Otherwise run:

```text
python <plugin-root>/scripts/install_codex_plugin.py workspaces
```

Those entries are local path pointers, not permission to read every workspace. Reuse the current matching workspace; if multiple entries fit, ask which one. Do not create another vault when a valid linked configuration already exists.

For a new workspace, infer the source and output location from the current request when clear. Ask only for a missing source folder or material language that cannot be inferred. Generated output must be separate from the original material; originals remain read-only. Use the user's language (`zh` or `en` currently supported) for new navigation. Existing vault names and language stay as configured unless the user asks to change them.

## Prepare stable tools and open the vault

Plugin caches can be replaced on upgrades. Store Python runtime, local configuration and generated knowledge in the user's stable output workspace rather than writing them into `<plugin-root>`.

For an existing configuration, use:

```text
python <plugin-root>/scripts/install_codex_plugin.py prepare-workspace --config <existing-config>
```

For a new output workspace, use:

```text
python <plugin-root>/scripts/install_codex_plugin.py prepare-workspace --workspace <output-folder>
```

Read the returned `tool_root`, `config` and `workspace`. For a **new** Windows workspace, invoke `<tool_root>/scripts/bootstrap.ps1` with `-Source`, `-Workspace`, `-Language` and `-TimeZone` using the known client IANA timezone (for example, Asia/Shanghai when that is the current client context); this reuses or installs Python and Obsidian, provisions dependencies, builds the vault and requests opening its home note.

For an **existing** workspace, preserve and use the exact returned config in every `pipeline.py` command. Reconnect with `open --config <config>`; refresh only when indexing is needed. Do not use the new-workspace bootstrap to repair an arbitrary existing config: it defaults to `settings.local.json` in the tool root. If dependencies need repair, prepare the local Python environment and install `requirements.txt` separately, then run `open` or `refresh` with the original config. Do not create or replace configuration to work around a missing runtime.

On macOS/Linux, use Python 3.11+, create a workspace-local virtual environment, install `<tool_root>/requirements.txt`, and run the pipeline's `setup --source ... --workspace ... --language ... --timezone <client-IANA-zone> --config ...`. Obsidian installation is manual on these systems; the Windows package-manager bootstrap does not cover them. Preserve the configured timezone of an existing workspace unless the user asks to change it; recurring task schedules follow the client's timezone.

After a successful setup or verified reconnection, remember this explicit link:

```text
python <plugin-root>/scripts/install_codex_plugin.py bind-workspace --config <config>
```

Read the coverage and maintenance reports, and verify the actual Obsidian home view when desktop inspection is available. A successful process launch is only a launch request; say when the visible app could not be checked. A missing/scanned/oversize source is a coverage gap, not a completed import.

## Arrange the requested recurring upkeep

When the user requests a recurring cadence, create or update a real Codex automation through the available built-in automation tool. Prefer a heartbeat attached to the current local conversation unless the user explicitly wants a standalone scheduled project. Resolve the user's timezone, cadence and current authorized workspace from context; do not silently assume all users use Sunday 20:00 or Asia/Shanghai.

Inspect existing automations through the tool or their local `automation.toml` metadata. Reuse one that maintains this exact workspace. Preserve its schedule unless a change was requested. Do not write raw automation TOML, install a second scheduler, or claim a task was created merely because you generated a prompt.

Make the automation prompt self-contained: include the exact stable Python executable, pipeline path and config path; require reading workspace `AGENTS.md`; refresh once; inspect `data/maintenance-latest.json` and its referenced change file; use the maintain-knowledge workflow to write separate source-linked interpretations; preserve personal notes; notify only for meaningful changes, concrete conflicts or failures. It needs no cloud sync or public upload.

If scheduling tools are unavailable, complete the usable local workspace and provide a ready-to-paste prompt with that exact limitation. Report scheduling success only from the automation tool's confirmed result. A local task still needs the computer, app and file access available when it runs.

Return the knowledge workspace entry point, what was checked, and the confirmed schedule or concrete limitation. The user should be able to keep working from that result.
