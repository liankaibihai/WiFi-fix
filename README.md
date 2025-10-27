# PDF → DWG Converter

This project provides a command-line utility that extracts vector content from PDF drawings and exports it into CAD-friendly DXF files, with optional DWG generation when paired with an external converter such as the [ODA File Converter](https://www.opendesign.com/guestfiles/oda_file_converter).

## Features

- Parses PDF vector geometry using [PyMuPDF](https://pymupdf.readthedocs.io/) and recreates it as DXF entities via [ezdxf](https://ezdxf.readthedocs.io/).
- Supports Bézier curve approximation with configurable precision.
- Optional text extraction with `TEXT` or `MTEXT` output entities.
- Command-line interface that can call out to an external DXF→DWG converter.

## Installation

Install the package in a virtual environment together with the required dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Usage

```bash
pdf-to-dwg input.pdf --dxf output.dxf
```

To additionally create a DWG file you must provide a converter executable that can process DXF input:

```bash
pdf-to-dwg input.pdf --dxf output.dxf --dwg output.dwg --dwg-converter /path/to/ODAFileConverter
```

### Command options

- `--bezier-segments`: control the smoothness of curved paths (default `24`).
- `--unit-scale`: apply a custom unit conversion (e.g. `1/72` to convert PDF points to inches).
- `--text-mode`: choose how text is exported (`none`, `text`, or `mtext`).
- `--dxf-version`: pick the DXF version supported by your CAD workflow.

## Testing

The repository contains unit tests that validate the geometry helpers:

```bash
pytest
```

## Limitations

- Raster images embedded in the PDF are ignored.
- Complex shading patterns and gradient fills are not exported.
- DWG creation requires an external converter tool.
