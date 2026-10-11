---
name: maintain-knowledge
description: Refresh an explicitly linked local knowledge workspace, interpret meaningful changes and preserve source-linked notes for personal learning, work, projects or research. 定期整理新增资料、核对冲突并保留可追溯的个人积累。
---

# Maintain a personal knowledge workspace

Use the exact local workspace/config given by the user, scheduled task or current `AGENTS.md`. If needed, resolve `<plugin-root>` from this skill's location and use `scripts/install_codex_plugin.py workspaces` to find an explicit binding. Do not silently expand to other sources or bind a different folder.

Read workspace `AGENTS.md`, its author-confirmed profile/priorities, coverage report and previous maintenance interpretation. Keep blank priorities unknown and source-derived drafts distinct from author confirmation. Follow the actual vault name, note folders and language in that workspace.

Run one refresh using its stable Python and config:

```text
python <tool-root>/scripts/pipeline.py refresh --config <config>
```

The pipeline uses a single refresh lock, preserves personal notes and protects manually edited generated pages. If another refresh owns the lock, report or retry once after it finishes; do not start a competing legacy script. Read `data/maintenance-latest.json` and the exact change file it references. Inspect new errors and protected-page conflicts as well as added/modified/removed sources.

If there are meaningful changes, select the relevant original sources and check their existence, current version and extract limits before interpreting them. Connect new evidence to ongoing work when the material supports it. Identify concrete conflicts and questions for the author. Do not infer completed work from file timestamps, plans or test fixtures, and do not promote every changed file into a new conclusion.

Save an interpretation only when it adds useful understanding, in a separate dated note under the workspace's personal-notes/automatic-upkeep folder. Include exact source links, observed changes, your inference and unresolved questions. Preserve generated change logs, handwritten notes and author-confirmed priorities. Removed originals can leave historical extracts; label them before relying on them. Never rewrite original material unless the current user separately authorized that edit.

Stay quiet when there is no meaningful change or actionable failure. Report concrete new evidence, conflicts, extraction/access errors or something the user must handle. A routine refresh is not permission to upload private material, change credentials, install another service or add a second scheduler.

If the user asks to change the cadence, use the real built-in Codex automation tool, match this workspace's existing task and preserve unrelated automations. Use setup-knowledge's scheduling guidance from `../setup-knowledge/SKILL.md` when needed. A saved prompt is not an active schedule; verify the tool result.
