# Scheduled knowledge-base upkeep

[English](automation.en.md) · [简体中文](automation.md) · [Back to home](../README.en.md)

In a local Codex task with access to the output workspace, say:

> Organize this knowledge base every Sunday at 20:00 in my time zone. Refresh changes, check relevant originals and save a separate interpretation note. Stay quiet when there is nothing useful to report.

The installation prompt already includes this step. Check for an existing task before creating one; reuse or update the matching schedule. Confirm the source folder, output workspace, frequency and time zone. If no source folder was supplied, ask the user to select one rather than scanning the whole computer.

## Set up and verify

Create an actual schedule through Codex's scheduling capability or configure it in the desktop app's Scheduled view. A saved prompt or settings file is not proof that a task is active. Verify its name, workspace, recurrence, time zone and enabled state, then run one local refresh and inspect the result.

Local scheduled work needs the computer and desktop app running, with the folder and permissions available. Web tasks cannot directly read local folders. [OpenAI scheduled-task guidance](https://learn.chatgpt.com/docs/automations). For index updates only, use **Enable-Weekly.cmd** instead; it makes no model calls. Avoid enabling both schedules.

## Reusable task prompt

This prompt follows workspace instructions to locate the vault, so it works with English, Chinese and existing research vaults:

```text
Use the Obsidian Knowledge Workspace maintain-knowledge workflow to organize this local personal knowledge base.

First read this workspace's AGENTS.md, the configured current-focus note, coverage and gaps, and the previous upkeep record. Run pipeline.py refresh with the Python and settings paths in the workspace instructions. Run only one refresh process at a time.

Read data/maintenance-latest.json and the exact changes.jsonl it references. Treat original files as read-only. Preserve the current-focus note, personal notes, manually edited generated pages and historical extracts. Do not upload or push private files, change account login, or install new services.

When sources were added or modified, select relevant material for the current focus. Check source existence, hashes, versions and extraction gaps. Explain which ongoing work the new material may support, with specific conflicts, limitations and open questions. Keep file changes, document claims, your inference, author confirmation and actual validation distinct. Dates, plans, drafts and test samples do not prove completed work.

Save supported interpretation as a new dated note under the vault's personal-notes upkeep folder. Cite accurate source paths and relevant paragraphs or pages. Do not overwrite automatic change logs, current focus or previous notes.

Stay quiet when there is no useful change or actionable issue. Notify me about important changes, clear conflicts, failures or decisions I need to make. If a folder is inaccessible or refresh fails, state the specific failure without expanding access. Do not create a second recurring task automatically.
```

## What a run leaves behind

- `data/maintenance-latest.json`: run status and the location of the exact change record.
- `data/runs/<run_id>/changes.jsonl`: inspectable source changes; Markdown logs show only the first 100 entries in each category.
- Automatic upkeep logs in personal notes: the pipeline's account of file changes.
- A separate agent note: source-checked interpretation, conflicts and open questions.

Changes and interpretations are separate so you can trace their evidence. The pipeline does not automatically send every original to a model; selected content remains subject to the product's data settings. [Privacy guidance](privacy.en.md).
