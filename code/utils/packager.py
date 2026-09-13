"""Packaging utility to generate code.zip for submission.
Includes code/ and evaluation/usage_report.md while strictly excluding:
- virtual environments (.venv, venv, env)
- __pycache__ and bytecode
- dataset/ files and media
- output.csv, log.txt, temporary artifacts
"""
import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ZIP_PATH = REPO_ROOT / "code.zip"

EXCLUDE_PATTERNS = {
    "__pycache__",
    ".pytest_cache",
    ".venv",
    "venv",
    "env",
    ".git",
    ".gitignore",
    ".DS_Store",
    "dataset",
    "output.csv",
    "log.txt",
    "code.zip",
    ".idea",
    ".vscode",
}

def should_exclude(path: Path) -> bool:
    for part in path.parts:
        if part in EXCLUDE_PATTERNS or part.endswith(".pyc"):
            return True
    return False

def package_code(repo_root: Path = REPO_ROOT, output_zip: Path = ZIP_PATH) -> int:
    """Creates submission code.zip containing code/ and evaluation/usage_report.md."""
    print(f"Creating submission package at: {output_zip}")
    code_dir = repo_root / "code"

    if output_zip.exists():
        output_zip.unlink()

    packed_count = 0
    with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        # 1. Add all files from code/ under code/ prefix
        for p in code_dir.rglob("*"):
            if p.is_file() and not should_exclude(p):
                rel = p.relative_to(code_dir).as_posix()
                zf.write(p, arcname=f"code/{rel}")
                packed_count += 1

        # 2. Add top-level evaluation/usage_report.md for explicit compliance
        usage_md = code_dir / "evaluation" / "usage_report.md"
        if usage_md.exists():
            zf.write(usage_md, arcname="evaluation/usage_report.md")

        # 3. Add README.md as requested by submission upload instructions
        readme_md = repo_root / "README.md"
        if readme_md.exists():
            zf.write(readme_md, arcname="README.md")
            zf.write(readme_md, arcname="code/README.md")



    size_kb = output_zip.stat().st_size / 1024.0
    print(f"Successfully packaged {packed_count} source files into {output_zip.name} ({size_kb:.1f} KB)")

    # Verify archive contents
    print("\nVerifying archive contents:")
    with zipfile.ZipFile(output_zip, "r") as zf:
        namelist = zf.namelist()
        has_usage_report = any("usage_report.md" in n for n in namelist)
        has_main = any("main.py" in n for n in namelist)
        print(f"  - Total entries: {len(namelist)}")
        print(f"  - Contains main.py: {has_main}")
        print(f"  - Contains evaluation/usage_report.md: {has_usage_report}")

    return packed_count

if __name__ == "__main__":
    package_code()
