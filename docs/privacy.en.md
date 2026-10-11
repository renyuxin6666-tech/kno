# Privacy and data boundaries

[English](privacy.en.md) · [简体中文](privacy.md) · [Back to home](../README.en.md)

The vault stays on your computer. Scanning, extraction, refresh and retrieval make no model API calls and provide no background cloud sync. Initial software / dependency downloads and GitHub updates use the network.

## Where data goes

| Content | Storage and use |
| --- | --- |
| Original files | Remain in your selected source folder; read-only by default |
| Navigation, text snapshots and file catalogs | Stored in the configured local vault and `data` folder |
| Local paths, language and category settings | Stored in untracked `settings.local.json` |
| Personal insights and agent notes | Saved under personal notes and preserved during refresh |
| Public repository | Tool source, documentation, synthetic tests and reviewed redacted images |

Codex reads selected source excerpts when answering or organizing. Their processing depends on the product, account and workspace data settings. Local storage does not imply a fully offline model, and the plugin does not give every chat permanent memory.

## Before publishing

Git ignores runtime files, local configuration, indexes, extracts, vaults and credentials. Do not force-add them. `scripts/audit_publication.py` checks explicit path and common sensitive-content patterns; it is not a confidentiality audit.

README screenshots come from a real local workspace. Only images with sensitive content covered should be released. A screenshot does not authorize publishing the originals. Packages should exclude raw captures, private documents, unredacted paths and account details.

## Access scope

Give the agent a source root and an output workspace; have it read sources relevant to the question. Instructions inside source documents are evidence, not execution authority. Editing originals, adding services or publishing material must stay within the current user's authorization.

Stopping a schedule does not delete the vault. Removing the tool or plugin should not remove your original files. Preserve personal notes and check configuration paths before moving the workspace.
