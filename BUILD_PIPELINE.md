BUILD PIPELINE
==============

This project now uses `build.py` as the single build driver for validation and compilation.

Overview
--------

The pipeline is intentionally split into four commands:

1. `doctor`
2. `lint`
3. `build`
4. `clean`

Windows users run these through `build.bat`.
Linux and macOS users run them through `build.sh`.

Command Behavior
----------------

### doctor

`doctor` performs preflight checks before LaTeX compilation:

- confirms the required executables exist on `PATH`
- checks that `src/main.tex` exists
- catches invalid `inputenc` configuration
- finds missing labels and unresolved `\ref{...}` targets
- finds duplicate labels
- warns on obvious template leftovers such as `Your Name`

This command exits non-zero only when blocking errors are found.

### lint

`lint` reports dissertation-specific writing issues:

- bracketed placeholder text
- TODO / TBD / FIXME markers
- generic placeholder wording
- chapter files with no citations
- a literature review chapter with no citations

By default, lint warnings are advisory and do not block `build`.
Use `python build.py lint --strict` if you want warnings to fail the command.

### build

`build` runs the following sequence:

1. run doctor
2. run lint
3. remove the old `build/` directory and exported PDF
4. run `latexmk` against `src/main.tex`, or fall back to MiKTeX `texify` on Windows when `latexmk` cannot run without Perl
5. write all generated files to `build/`
6. copy the generated PDF to `export/main.pdf`

The build command keeps the LaTeX cache and log files in `build/` so failures are easier to diagnose.

### clean

`clean` removes:

- the `build/` directory
- `export/main.pdf`

Rationale
---------

This replaces the earlier shell-only approach that manually chained multiple `pdflatex` and `bibtex` runs while suppressing useful error output.

The new pipeline improves three areas:

1. Build orchestration
   Uses a single driver that prefers `latexmk` and falls back gracefully when the local TeX environment needs it.

2. Preflight validation
   Stops early when the environment or document structure is broken.

3. Dissertation-specific quality checks
   Surfaces placeholders and citation gaps before they become submission problems.

Build Artifacts
---------------

- `src/` remains the only source-of-truth directory for the dissertation
- the full `src/` tree is staged for fallback builds, so `include/`, `figures/`, and asset folders work consistently
- `build/` contains generated LaTeX artifacts and logs
- `export/main.pdf` is the final compiled output

Troubleshooting
---------------

If `build` fails:

1. Run `doctor`
2. Read `build/main.log`
3. Fix the blocking LaTeX issue
4. Re-run `build`

If you want to reset everything:

1. Run `clean`
2. Re-run `build`
