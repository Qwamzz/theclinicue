"""Build the submission ZIP.

Regenerates the PDFs, substitutes the student's details and deployment links
into every artefact, assembles the required folder structure, and zips it.

    python tools/package.py --student "Ama Mensah" --student-id "10891234" \
        --live-url https://theclinicue.onrender.com \
        --repo-url https://github.com/you/theclinicue
"""

from __future__ import annotations

import argparse
import shutil
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
BUILD = ROOT / "Submission"

# Source code and supporting material that goes into Supporting_Files/.
INCLUDE_DIRS = ["app", "tests", "tools", "docs", ".github"]
INCLUDE_FILES = [
    "wsgi.py", "requirements.txt", "requirements-dev.txt", "pytest.ini",
    "Dockerfile", "Procfile", ".env.example", ".gitignore",
    "README.md", "DEPLOY.md", "startup.sh", "azure-setup.sh",
    "azure-deploy-direct.sh",
]
EXCLUDE_PARTS = {
    "__pycache__", ".pytest_cache", ".venv", ".git", "htmlcov",
    "_preview", "node_modules",
}
EXCLUDE_SUFFIXES = {".pyc", ".pyo", ".sqlite3", ".sqlite3-wal", ".sqlite3-shm"}
EXCLUDE_NAMES = {"_contact_sheet.html", "test-results.xml", ".coverage", ".env"}

PLACEHOLDERS = {
    "[STUDENT NAME]": "student",
    "[STUDENT ID]": "student_id",
    "[LIVE APPLICATION URL]": "live_url",
    "[SOURCE REPOSITORY URL]": "repo_url",
}


def keep(path: Path) -> bool:
    if any(part in EXCLUDE_PARTS for part in path.parts):
        return False
    if path.suffix.lower() in EXCLUDE_SUFFIXES or path.name in EXCLUDE_NAMES:
        return False
    return True


def substitute(text: str, values: dict[str, str]) -> str:
    for placeholder, key in PLACEHOLDERS.items():
        if values.get(key):
            text = text.replace(placeholder, values[key])
    return text


def apply_to_markdown(values: dict[str, str]) -> list[Path]:
    """Write substituted copies of the Markdown sources to a staging area."""
    staging = BUILD / "_md"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)

    written = []
    for source in sorted(DOCS.glob("*.md")):
        target = staging / source.name
        target.write_text(substitute(source.read_text(encoding="utf-8"), values),
                          encoding="utf-8")
        written.append(target)

    # Diagrams must sit alongside so relative image paths resolve.
    shutil.copytree(DOCS / "diagrams", staging / "diagrams",
                    ignore=shutil.ignore_patterns("_preview", "_contact_sheet.html"))
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--student", default="[STUDENT NAME]")
    parser.add_argument("--student-id", default="[STUDENT ID]")
    parser.add_argument("--live-url", default="")
    parser.add_argument("--repo-url", default="")
    parser.add_argument("--project-name", default="TheClinicue")
    args = parser.parse_args(argv)

    values = {
        "student": args.student,
        "student_id": args.student_id,
        "live_url": args.live_url,
        "repo_url": args.repo_url,
    }

    safe_id = "".join(c for c in args.student_id if c.isalnum()) or "STUDENTID"
    folder_name = f"{safe_id}_{args.project_name}"
    staged = BUILD / folder_name
    if staged.exists():
        shutil.rmtree(staged)
    (staged / "Supporting_Files").mkdir(parents=True)

    # 1. PDFs, from substituted Markdown so the details appear inside them.
    print("1. Rendering PDFs")
    md_files = apply_to_markdown(values)
    from tools.md2pdf import DEFAULT_SET, render

    staging = BUILD / "_md"
    for source_name, target_name in DEFAULT_SET:
        source = staging / source_name
        if not source.exists():
            print(f"   ! missing {source_name}")
            continue
        render(source, staged / target_name, args.student, args.student_id)
        print(f"   ok  {target_name}")

    # 2. Links file.
    print("2. Links file")
    links = BUILD / "Deployment_and_Source_Links.txt"
    (staged / "Deployment_and_Source_Links.txt").write_text(
        substitute(links.read_text(encoding="utf-8"), values), encoding="utf-8")
    print("   ok  Deployment_and_Source_Links.txt")

    # 3. Supporting files.
    print("3. Supporting files")
    support = staged / "Supporting_Files"
    count = 0
    for name in INCLUDE_DIRS:
        source_dir = ROOT / name
        if not source_dir.exists():
            continue
        for item in source_dir.rglob("*"):
            if not item.is_file() or not keep(item):
                continue
            destination = support / item.relative_to(ROOT)
            destination.parent.mkdir(parents=True, exist_ok=True)
            if item.suffix == ".md" and item.parent == DOCS:
                destination.write_text(
                    substitute(item.read_text(encoding="utf-8"), values), encoding="utf-8")
            else:
                shutil.copy2(item, destination)
            count += 1
    for name in INCLUDE_FILES:
        item = ROOT / name
        if item.exists():
            shutil.copy2(item, support / name)
            count += 1
    print(f"   ok  {count} files")

    # 4. Zip.
    print("4. Archive")
    archive = BUILD / f"{folder_name}.zip"
    if archive.exists():
        archive.unlink()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for item in sorted(staged.rglob("*")):
            if item.is_file():
                zf.write(item, item.relative_to(BUILD))
    shutil.rmtree(staging, ignore_errors=True)

    size = archive.stat().st_size / (1024 * 1024)
    with zipfile.ZipFile(archive) as zf:
        entries = zf.namelist()

    print(f"   ok  {archive.name}  ({size:.2f} MB, {len(entries)} entries)\n")
    print(f"Submission ready: {archive}")

    remaining = [p for p, key in PLACEHOLDERS.items() if not values.get(key)]
    if remaining:
        print("\nPlaceholders still unfilled (pass the matching option and re-run):")
        for placeholder in remaining:
            print(f"   {placeholder}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
