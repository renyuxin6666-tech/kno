"""Read-only inventory; never follows links or enters the generated vault."""
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from settings import Settings
CONFIG = Settings()
ROOT = CONFIG.source
WORKSPACE = CONFIG.workspace
DATA = WORKSPACE / "data"
T = CONFIG.text
PRUNE = {".git", ".svn", ".hg", "node_modules", ".venv", "venv", "__pycache__",
         ".cache", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".next", ".nuxt",
         ".turbo", ".codex", ".agents", ".ssh", ".aws", ".azure", ".accelerate",
         ".obsidian", "site-packages", "$recycle.bin", "system volume information",
         ".local", ".workbuddy", ".worktrees", ".codex_tmp", ".test-runs",
         ".smoke-store", ".demo-store", "_cacache", "cache", "caches", "temp", "tmp"}
TEXT_EXT = {".md", ".markdown", ".txt", ".rst", ".docx", ".pdf"}

def sensitive(name):
    n = name.lower()
    return (n == ".env" or n.startswith(".env.") or n.endswith((".pem", ".key", ".p12", ".pfx"))
            or n in {"credentials.json", "credentials", "token.json", "tokens.json", "secrets.json", "auth.json", "id_rsa", "id_ed25519"}
            or n.startswith("client_secret"))

def main():
    DATA.mkdir(parents=True, exist_ok=True)
    records, omissions, projects = [], [], {}
    errors = []
    def walk(folder, project):
        try:
            entries = sorted(os.scandir(folder), key=lambda e: e.name.casefold())
        except OSError as e:
            errors.append({"path": str(folder), "error": type(e).__name__})
            return
        for entry in entries:
            p = Path(entry.path)
            rel = p.relative_to(ROOT).as_posix()
            try:
                st = entry.stat(follow_symlinks=False)
                if entry.is_symlink() or getattr(st, "st_file_attributes", 0) & 0x400:
                    omissions.append({"path": rel, "reason": "link_or_reparse_point"})
                elif entry.is_dir(follow_symlinks=False):
                    unity_cache = entry.name.lower() in {"library", "obj", "logs"} and (Path(folder) / "Assets").is_dir()
                    ros_cache = entry.name.lower() in {"build", "install", "log"} and (Path(folder) / "src").is_dir()
                    if CONFIG.is_excluded(p) or entry.name.lower() in PRUNE or unity_cache or ros_cache:
                        omissions.append({"path": rel, "reason": "dependency_cache_or_tool_state"})
                    else:
                        walk(p, project)
                elif entry.is_file(follow_symlinks=False):
                    if sensitive(entry.name):
                        omissions.append({"path": rel, "reason": "credential_filename"})
                        continue
                    ext = p.suffix.lower()
                    records.append({"path": str(p), "relative_path": rel, "project": project,
                                    "extension": ext, "size_bytes": st.st_size,
                                    "modified_utc": datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat(),
                                    "text_candidate": ext in TEXT_EXT})
                    if len(records) % 20000 == 0:
                        print(T(f'目录索引：{len(records)} 个文件；当前分组：{project}',f'Inventory: {len(records)} files; current group: {project}'), flush=True)
            except OSError as e:
                errors.append({"path": rel, "error": type(e).__name__})
    for entry in sorted(os.scandir(ROOT), key=lambda e: e.name.casefold()):
        p = Path(entry.path)
        if entry.is_dir(follow_symlinks=False):
            if CONFIG.is_excluded(p.resolve()) or entry.name.lower() in PRUNE or entry.is_symlink() or getattr(entry.stat(follow_symlinks=False), 'st_file_attributes', 0) & 0x400:
                omissions.append({"path": entry.name, "reason": "generated_workspace" if CONFIG.is_excluded(p.resolve()) else "dependency_cache_or_tool_state"})
                continue
            projects[entry.name] = {"path": str(p)}
            walk(p, entry.name)
            print(T(f'已扫描：{entry.name}；累计 {len(records)} 个文件',f'Scanned: {entry.name}; cumulative files: {len(records)}'), flush=True)
        elif entry.is_file(follow_symlinks=False) and not sensitive(entry.name):
            st = entry.stat(follow_symlinks=False)
            projects.setdefault(T('根目录资料','Root Files'), {"path": str(ROOT)})
            records.append({"path": str(p), "relative_path": p.name, "project": T('根目录资料','Root Files'),
                            "extension": p.suffix.lower(), "size_bytes": st.st_size,
                            "modified_utc": datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat(),
                            "text_candidate": p.suffix.lower() in TEXT_EXT})
    for name, info in projects.items():
        subset = [r for r in records if r["project"] == name]
        info.update(files=len(subset), bytes=sum(r["size_bytes"] for r in subset),
                    text_candidates=sum(r["text_candidate"] for r in subset),
                    extensions=dict(Counter(r["extension"] for r in subset).most_common(12)))
    summary = {"generated_utc": datetime.now(timezone.utc).isoformat(), "source_root": str(ROOT),
               "file_count": len(records), "bytes": sum(r["size_bytes"] for r in records),
               "text_candidates": sum(r["text_candidate"] for r in records),
               "extensions": dict(Counter(r["extension"] for r in records).most_common(30)),
               "projects": projects, "omitted_entries": omissions, "scan_errors": errors,
               "policy": "original files read-only; dependencies/cache/tool state/credentials/links excluded; this workspace excluded"}
    target = DATA / "inventory.jsonl"
    temp = target.with_suffix(".tmp")
    with temp.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    temp.replace(target)
    (DATA / "inventory-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k:v for k,v in summary.items() if k not in {"projects", "omitted_entries", "scan_errors"}}, ensure_ascii=False))
    print(json.dumps({"projects": len(projects), "excluded_entries":len(omissions), "scan_errors": len(errors)}, ensure_ascii=False))
    for name, info in sorted(projects.items(), key=lambda kv: kv[1]["text_candidates"], reverse=True)[:12]:
        print(json.dumps({"project":name, **info}, ensure_ascii=False))

if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
