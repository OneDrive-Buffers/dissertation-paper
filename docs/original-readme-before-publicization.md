# Dissertation: An Interactive Ontology-Based Framework for Computer Science Education

This project uses a Python-based build driver to validate and compile the dissertation from the LaTeX sources in `src/`.

## Commands

On Windows:

```text
build.bat
build.bat doctor
build.bat lint
build.bat clean
```

On Linux or macOS:

```text
./build.sh
./build.sh doctor
./build.sh lint
./build.sh clean
```

You can also run the driver directly:

```text
python build.py build
python build.py doctor
python build.py lint
python build.py clean
```

## What Each Command Does

- `build`: runs doctor, runs lint, clears old build artifacts, compiles with `latexmk` when available, falls back to MiKTeX `texify` on Windows when needed, and copies `build/main.pdf` to `export/main.pdf`
- `doctor`: checks the build environment and catches blocking document-structure problems before compilation
- `lint`: reports dissertation-specific writing issues such as placeholders and chapters with no citation commands
- `clean`: removes the generated build cache and exported PDF

## Project Structure

```text
paper/
|-- build.py
|-- build.bat
|-- build.sh
|-- src/
|   |-- include/
|   |-- figures/
|   |-- assets/
|   |-- main.tex
|   |-- bibliography.bib
|   `-- chapters/
|-- build/
`-- export/
```

## Doctor Checks

The `doctor` command verifies:

- required tools are available on `PATH`
- `src/main.tex` exists
- `inputenc` is configured with a valid encoding token
- LaTeX references point to existing labels
- labels are not duplicated
- template markers like `Your Name` and `Sample Appendix` are still visible

## Lint Checks

The `lint` command reports:

- bracketed placeholder text such as `\textit{[...]}`
- `TODO`, `TBD`, `FIXME`, and generic placeholder markers
- chapter files with no `\cite{...}` commands
- a literature review chapter with no citations

Lint warnings do not block the `build` command by default. If you want lint to fail when warnings exist, run:

```text
python build.py lint --strict
```

## Notes

- edit only the files in `src/`
- keep `src/main.tex` as a short orchestration file and move longer configuration into `src/include/`
- `build/` is generated output and debug cache
- `export/main.pdf` is the final compiled PDF
- bibliography reports in the top-level `bibliography/` folder are guidance material, not build inputs
