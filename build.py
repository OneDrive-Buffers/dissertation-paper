from __future__ import annotations

import argparse
import os
import re
import shutil
import stat
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "src"
CHAPTERS_DIR = SRC_DIR / "chapters"
BUILD_DIR = ROOT_DIR / "build"
EXPORT_DIR = ROOT_DIR / "export"
MAIN_TEX = SRC_DIR / "main.tex"
OUTPUT_PDF = BUILD_DIR / "main.pdf"
EXPORT_PDF = EXPORT_DIR / "main.pdf"

REF_PATTERN = re.compile(r"\\(?:auto|page)?ref\{([^}]+)\}")
CITE_PATTERN = re.compile(r"\\cite[a-zA-Z*]*\{")
LABEL_PATTERN = re.compile(r"\\label\{([^}]+)\}")
INPUTENC_PATTERN = re.compile(r"\\usepackage\[(.*?)\]\{inputenc\}")
BACKEND_PATTERN = re.compile(r"backend\s*=\s*([a-zA-Z0-9_-]+)")


@dataclass
class Issue:
    severity: str
    message: str
    path: Path | None = None
    line: int | None = None

    def format(self) -> str:
        prefix = f"[{self.severity}]"
        if self.path is None:
            return f"{prefix} {self.message}"
        rel_path = self.path.relative_to(ROOT_DIR)
        if self.line is None:
            return f"{prefix} {rel_path}: {self.message}"
        return f"{prefix} {rel_path}:{self.line}: {self.message}"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def line_number_from_index(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def iter_tex_files() -> list[Path]:
    tex_files = sorted(path for path in SRC_DIR.rglob("*.tex") if path != MAIN_TEX)
    return [MAIN_TEX, *tex_files]


def extract_backend(main_text: str) -> str:
    match = BACKEND_PATTERN.search(main_text)
    if not match:
        return "bibtex"
    return match.group(1).lower()


def collect_labels() -> dict[str, list[tuple[Path, int]]]:
    labels: dict[str, list[tuple[Path, int]]] = {}
    for path in iter_tex_files():
        text = read_text(path)
        for match in LABEL_PATTERN.finditer(text):
            label = match.group(1).strip()
            labels.setdefault(label, []).append((path, line_number_from_index(text, match.start())))
    return labels


def collect_refs() -> list[tuple[str, Path, int]]:
    refs: list[tuple[str, Path, int]] = []
    for path in iter_tex_files():
        text = read_text(path)
        for match in REF_PATTERN.finditer(text):
            labels = [item.strip() for item in match.group(1).split(",") if item.strip()]
            line = line_number_from_index(text, match.start())
            for label in labels:
                refs.append((label, path, line))
    return refs


def collect_doctor_issues() -> list[Issue]:
    issues: list[Issue] = []

    if not MAIN_TEX.exists():
        issues.append(Issue("ERROR", "Missing src/main.tex.", MAIN_TEX))
        return issues

    main_text = read_text(MAIN_TEX)
    backend = extract_backend(main_text)

    required_commands = ["pdflatex"]
    if backend == "biber":
        required_commands.append("biber")
    else:
        required_commands.append("bibtex")

    for command in required_commands:
        if shutil.which(command) is None:
            issues.append(Issue("ERROR", f"Required command '{command}' is not available on PATH."))

    latexmk_available = shutil.which("latexmk") is not None
    texify_available = shutil.which("texify") is not None
    perl_available = shutil.which("perl") is not None

    if not latexmk_available and not texify_available:
        issues.append(
            Issue(
                "ERROR",
                "Neither latexmk nor texify is available, so no TeX build driver can be used.",
            )
        )
    elif latexmk_available and os.name == "nt" and not perl_available and texify_available:
        issues.append(
            Issue(
                "WARN",
                "Perl is not available, so builds will fall back from latexmk to texify on this machine.",
            )
        )
    elif latexmk_available and os.name == "nt" and not perl_available and not texify_available:
        issues.append(
            Issue(
                "ERROR",
                "latexmk is installed but Perl is unavailable, and texify is not present as a fallback.",
            )
        )

    inputenc_match = INPUTENC_PATTERN.search(main_text)
    if inputenc_match and inputenc_match.group(1).strip().lower() == "utf-8":
        issues.append(
            Issue(
                "ERROR",
                "Use 'utf8' instead of 'utf-8' for the inputenc package option.",
                MAIN_TEX,
                line_number_from_index(main_text, inputenc_match.start()),
            )
        )

    labels = collect_labels()
    for label, locations in sorted(labels.items()):
        if len(locations) <= 1:
            continue
        first_path, first_line = locations[0]
        duplicates = ", ".join(
            f"{path.relative_to(ROOT_DIR)}:{line}" for path, line in locations[1:]
        )
        issues.append(
            Issue(
                "ERROR",
                f"Duplicate label '{label}' also appears at {duplicates}.",
                first_path,
                first_line,
            )
        )

    for label, path, line in collect_refs():
        if label not in labels:
            issues.append(Issue("ERROR", f"Reference targets missing label '{label}'.", path, line))

    author_marker = r"\author{Your Name}"
    marker_index = main_text.find(author_marker)
    if marker_index != -1:
        issues.append(
            Issue(
                "WARN",
                "Author metadata still uses the template value 'Your Name'.",
                MAIN_TEX,
                line_number_from_index(main_text, marker_index),
            )
        )

    appendix_marker = r"\chapter{Sample Appendix}"
    marker_index = main_text.find(appendix_marker)
    if marker_index != -1:
        issues.append(
            Issue(
                "WARN",
                "The document still includes the template chapter title 'Sample Appendix'.",
                MAIN_TEX,
                line_number_from_index(main_text, marker_index),
            )
        )

    return issues


def collect_lint_issues() -> list[Issue]:
    issues: list[Issue] = []

    placeholder_patterns = [
        (re.compile(r"\\textit\{\[[^]]+\]\}"), "Bracketed placeholder text remains in this chapter."),
        (re.compile(r"(?i)\bTODO\b|\bTBD\b|\bFIXME\b"), "TODO/TBD/FIXME marker remains in the document."),
        (re.compile(r"(?i)\bplaceholder\b"), "Placeholder text remains in the document."),
    ]

    chapter_prefixes = tuple(f"{n:02d}" for n in range(1, 9))
    for path in sorted(CHAPTERS_DIR.glob("*.tex")):
        text = read_text(path)

        for pattern, message in placeholder_patterns:
            for match in pattern.finditer(text):
                issues.append(
                    Issue(
                        "WARN",
                        message,
                        path,
                        line_number_from_index(text, match.start()),
                    )
                )

        cite_count = len(CITE_PATTERN.findall(text))
        if path.name == "02-literature-review.tex" and cite_count == 0:
            issues.append(
                Issue(
                    "WARN",
                    "Literature review contains no citation commands.",
                    path,
                    1,
                )
            )
        elif path.name.startswith(chapter_prefixes) and cite_count == 0:
            issues.append(
                Issue(
                    "WARN",
                    "Chapter contains no citation commands.",
                    path,
                    1,
                )
            )

    return issues


def print_issues(title: str, issues: list[Issue]) -> None:
    print(title)
    if not issues:
        print("  No issues found.")
        return
    for issue in issues:
        print(f"  {issue.format()}")


def has_errors(issues: list[Issue]) -> bool:
    return any(issue.severity == "ERROR" for issue in issues)


def run_doctor() -> int:
    issues = collect_doctor_issues()
    print_issues("Doctor report:", issues)
    return 1 if has_errors(issues) else 0


def run_lint(strict: bool = False) -> int:
    issues = collect_lint_issues()
    print_issues("Lint report:", issues)
    if strict and issues:
        return 1
    return 0


def remove_readonly(func, path, _excinfo) -> None:
    os.chmod(path, stat.S_IWRITE)
    func(path)


def stage_sources_into_build() -> None:
    for item in SRC_DIR.iterdir():
        destination = BUILD_DIR / item.name
        if item.is_dir():
            shutil.copytree(item, destination, dirs_exist_ok=True)
        else:
            shutil.copy2(item, destination)


def clean() -> None:
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR, onexc=remove_readonly)
    if EXPORT_PDF.exists():
        EXPORT_PDF.unlink()
    if EXPORT_DIR.exists() and not any(EXPORT_DIR.iterdir()):
        try:
            EXPORT_DIR.rmdir()
        except PermissionError:
            pass


def select_build_command(backend: str) -> tuple[str, list[str], Path]:
    latexmk_available = shutil.which("latexmk") is not None
    texify_available = shutil.which("texify") is not None
    perl_available = shutil.which("perl") is not None

    if latexmk_available and (os.name != "nt" or perl_available):
        command = [
            "latexmk",
            "-pdf",
            "-interaction=nonstopmode",
            "-halt-on-error",
            "-file-line-error",
            f"-outdir={BUILD_DIR}",
            "main.tex",
        ]
        if backend == "biber":
            command.insert(1, "-use-biber")
        elif backend == "bibtex":
            command.insert(1, "-bibtex")
        return ("latexmk", command, SRC_DIR)

    if texify_available:
        stage_sources_into_build()
        command = [
            "texify",
            "--pdf",
            "--batch",
            "--quiet",
            "--max-iterations=5",
            "--tex-option=--halt-on-error",
            "--tex-option=--file-line-error",
            "main.tex",
        ]
        return ("texify", command, BUILD_DIR)

    command = [
        "latexmk",
        "-pdf",
        "-interaction=nonstopmode",
        "-halt-on-error",
        "-file-line-error",
        f"-outdir={BUILD_DIR}",
        "main.tex",
    ]
    if backend == "biber":
        command.insert(1, "-use-biber")
    elif backend == "bibtex":
        command.insert(1, "-bibtex")
    return ("latexmk", command, SRC_DIR)


def build() -> int:
    doctor_issues = collect_doctor_issues()
    print_issues("Doctor report:", doctor_issues)
    if has_errors(doctor_issues):
        print("Build stopped because doctor found blocking issues.")
        return 1

    lint_issues = collect_lint_issues()
    print_issues("Lint report:", lint_issues)

    clean()
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)

    main_text = read_text(MAIN_TEX)
    backend = extract_backend(main_text)

    driver, command, command_cwd = select_build_command(backend)

    print("Build command:")
    print(f"  {' '.join(command)}")
    print(f"  Driver: {driver}")

    result = subprocess.run(
        command,
        cwd=command_cwd,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print("LaTeX build failed.")
        if result.stdout.strip():
            print(result.stdout.strip())
        if result.stderr.strip():
            print(result.stderr.strip())
        log_path = BUILD_DIR / "main.log"
        if log_path.exists():
            print(f"See build log: {log_path}")
        return result.returncode

    if not OUTPUT_PDF.exists():
        print("LaTeX build finished without producing build/main.pdf.")
        return 1

    shutil.copy2(OUTPUT_PDF, EXPORT_PDF)
    print(f"Build succeeded. PDF copied to {EXPORT_PDF}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build, validate, and lint the dissertation project."
    )
    parser.add_argument(
        "command",
        nargs="?",
        choices=["build", "doctor", "lint", "clean"],
        default="build",
        help="Command to run.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Make lint exit non-zero when warnings are found.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.command == "doctor":
        return run_doctor()
    if args.command == "lint":
        return run_lint(strict=args.strict)
    if args.command == "clean":
        clean()
        print("Removed build artifacts.")
        return 0
    return build()


if __name__ == "__main__":
    sys.exit(main())
