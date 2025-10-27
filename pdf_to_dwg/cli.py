"""Command line interface for converting PDF drawings to DXF / DWG."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .converters import (
    ConversionSettings,
    PdfToCadConverter,
    TextExportMode,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert vector-based PDFs into DXF/DWG CAD files.",
    )
    parser.add_argument("pdf", type=Path, help="Input PDF drawing to convert")
    parser.add_argument(
        "--dxf",
        type=Path,
        help="Output DXF file (defaults to <input>.dxf)",
    )
    parser.add_argument(
        "--dwg",
        type=Path,
        help="Optional DWG output path (requires --dwg-converter)",
    )
    parser.add_argument(
        "--dwg-converter",
        type=Path,
        help="External converter CLI capable of DXF→DWG (e.g. ODAFileConverter)",
    )
    parser.add_argument(
        "--bezier-segments",
        type=int,
        default=24,
        help="Number of segments used to approximate Bézier curves (default: 24)",
    )
    parser.add_argument(
        "--unit-scale",
        type=float,
        default=1.0,
        help=(
            "Scale factor applied to all coordinates. "
            "Use 1/72 to convert PDF points to inches."
        ),
    )
    parser.add_argument(
        "--text-mode",
        choices=[mode.value for mode in TextExportMode],
        default=TextExportMode.TEXT.value,
        help="How to export PDF text objects (default: text)",
    )
    parser.add_argument(
        "--dxf-version",
        default="R2010",
        help="DXF version string supported by ezdxf (default: R2010)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    pdf_path: Path = args.pdf
    if not pdf_path.exists():
        parser.error(f"Input PDF '{pdf_path}' does not exist")

    output_dxf = args.dxf or pdf_path.with_suffix(".dxf")
    output_dwg = args.dwg
    dwg_converter = args.dwg_converter

    if output_dwg and not dwg_converter:
        parser.error("--dwg requires --dwg-converter to be specified")

    settings = ConversionSettings(
        pdf_path=pdf_path,
        output_dxf_path=output_dxf,
        output_dwg_path=output_dwg,
        bezier_approximation_segments=args.bezier_segments,
        unit_scale=args.unit_scale,
        text_mode=TextExportMode(args.text_mode),
        dxf_version=args.dxf_version,
        dwg_converter_cli=dwg_converter,
    )

    converter = PdfToCadConverter(settings)
    try:
        result = converter.convert()
    except Exception as exc:  # pragma: no cover - CLI level failure
        parser.exit(status=1, message=f"Conversion failed: {exc}\n")

    print(f"DXF saved to: {result.dxf_path}")
    if result.dwg_path:
        print(f"DWG saved to: {result.dwg_path}")
    if result.warnings:
        print("Warnings:")
        for warning in result.warnings:
            print(f"  - {warning}")

    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
