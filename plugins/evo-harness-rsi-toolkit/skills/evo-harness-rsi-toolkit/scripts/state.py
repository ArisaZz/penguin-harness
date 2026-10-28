"""Install a frozen Evo export into native Skill slots before taking a snapshot.

No model calls, YAML edits, archive mutation or historical-format migration.
"""
import hashlib
import json
from pathlib import Path, PurePosixPath


def install_package(receipt, state):
    source = Path(receipt["directory"]).resolve()
    target = Path(state).resolve()
    if not (target / "system_config.yaml").is_file():
        raise ValueError("prepare a native Agent State before installing the package")
    actual = set()
    for path in source.rglob("*"):
        if path.is_symlink() or not (path.is_dir() or path.is_file()):
            raise ValueError("export contains a linked or special entry")
        if path.is_file():
            actual.add(path.relative_to(source).as_posix())
    if actual != set(receipt["sha256"]):
        raise ValueError("export inventory contains missing or extra files")
    files = {}
    for name, digest in receipt["sha256"].items():
        relative = PurePosixPath(name)
        if relative.is_absolute() or ".." in relative.parts or "\\" in name:
            raise ValueError("export path escapes package")
        path = source / name
        if path.resolve() != path or not path.is_file():
            raise ValueError("export file is missing or linked")
        content = path.read_bytes()
        if hashlib.sha256(content).hexdigest() != digest:
            raise ValueError("export changed after freezing")
        files[name] = content
    manifest = json.loads(files["manifest.json"])
    if manifest.get("version") != 1:
        raise ValueError("unsupported export manifest version")
    expected = {"SKILL.md", "manifest.json"} | {entry["path"] for entry in manifest["entries"]}
    if set(files) != expected or sum(map(len, files.values())) != receipt["bytes"]:
        raise ValueError("export inventory differs from its receipt")
    if receipt["bytes"] > 16000:
        raise ValueError("export exceeds the complete package budget")
    context = receipt["context"]
    if hashlib.sha256(context.encode()).hexdigest() != receipt["context_sha256"]:
        raise ValueError("frozen context changed")
    reader = files["SKILL.md"].decode().partition("\n---\n")
    if not reader[1]:
        raise ValueError("export Reader has no native frontmatter")
    parts = [reader[2]]
    for entry in manifest["entries"]:
        name = "evo-method-" + hashlib.sha256(entry["id"].encode()).hexdigest()[:20]
        if entry["path"] != f"{name}/SKILL.md":
            raise ValueError("export method path differs from its identity")
        if entry["level"] == "general" or entry.get("topic") == receipt["topic"]:
            body = files[entry["path"]].decode().partition("\n---\n")
            if not body[1]:
                raise ValueError("export method has no native frontmatter")
            parts.append(body[2])
    if "\n".join(parts) != context:
        raise ValueError("context does not contain exactly the frozen topic methods")
    agents = target / "AGENTS.md"
    if agents.is_symlink() or (agents.exists() and not agents.is_file()):
        raise ValueError("AGENTS.md must be a regular file")
    previous = agents.read_text(encoding="utf-8") if agents.exists() else ""
    marker = "<!-- evo-frozen-context -->"
    block = marker + "\n" + context + "\n<!-- /evo-frozen-context -->"
    if marker in previous and (previous.count(marker) != 1 or not previous.endswith(block)):
        raise ValueError("another frozen Evo context is installed; use a fresh base copy")
    updates = {"skills/evo-reader/SKILL.md": files["SKILL.md"],
               "skills/evo-reader/manifest.json": files["manifest.json"]}
    updates.update({"skills/" + name: content for name, content in files.items()
                    if name not in ("SKILL.md", "manifest.json")})
    wanted_dirs = {"evo-reader"} | {entry["path"].split("/")[0] for entry in manifest["entries"]}
    skills = target / "skills"
    if skills.exists() and {p.name for p in skills.iterdir()
                            if p.name == "evo-reader" or p.name.startswith("evo-method-")} - wanted_dirs:
        raise ValueError("State contains Evo methods outside this frozen package")
    # Validate every destination before changing any file. Existing user Skills stay intact.
    for name, content in updates.items():
        destination = target / name
        if destination.resolve() != destination:
            raise ValueError("native Skill slot is linked")
        if destination.exists() and (not destination.is_file() or destination.read_bytes() != content):
            raise ValueError("native Skill slot already contains different content")
    for name, content in updates.items():
        destination = target / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            destination.write_bytes(content)
    if marker not in previous:
        agents.write_text(previous + ("\n\n" if previous else "") + block, encoding="utf-8")
    return {"state": str(target), "context_sha256": receipt["context_sha256"],
            "installed": {name: hashlib.sha256(content).hexdigest() for name, content in updates.items()}}
