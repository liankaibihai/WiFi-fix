"""Core conversion workflow for PDF → DXF/DWG."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Iterator, List, Optional, Sequence, Tuple
import math
import subprocess

try:  # pragma: no cover - runtime dependency check
    import fitz  # type: ignore
except ImportError:  # pragma: no cover - optional for test environments
    fitz = None  # type: ignore

try:  # pragma: no cover - runtime dependency check
    import ezdxf  # type: ignore
except ImportError:  # pragma: no cover - optional for test environments
    ezdxf = None  # type: ignore


Point = Tuple[float, float]


class TextExportMode(str, Enum):
    """Controls how text extracted from the PDF should be exported."""

    NONE = "none"
    TEXT = "text"
    MTEXT = "mtext"


@dataclass(slots=True)
class ConversionSettings:
    """Parameters controlling how the conversion should be performed."""

    pdf_path: Path
    output_dxf_path: Path
    output_dwg_path: Optional[Path] = None
    unit_scale: float = 1.0
    bezier_approximation_segments: int = 24
    text_mode: TextExportMode = TextExportMode.TEXT
    dxf_version: str = "R2010"
    dwg_converter_cli: Optional[Path] = None

    def ensure_output_directory(self) -> None:
        """Create output directories if they do not exist."""

        self.output_dxf_path.parent.mkdir(parents=True, exist_ok=True)
        if self.output_dwg_path is not None:
            self.output_dwg_path.parent.mkdir(parents=True, exist_ok=True)


@dataclass(slots=True)
class ConversionResult:
    """Returned after a conversion attempt."""

    dxf_path: Path
    pages_converted: int
    dwg_path: Optional[Path] = None
    warnings: List[str] = field(default_factory=list)


class PdfToCadConverter:
    """Main entry point for converting PDFs into DXF (and optionally DWG)."""

    def __init__(self, settings: ConversionSettings) -> None:
        self.settings = settings

    def convert(self) -> ConversionResult:
        """Convert the configured PDF into CAD friendly formats."""

        if fitz is None:
            raise RuntimeError(
                "PyMuPDF (the `fitz` module) is required. Install it via `pip install pymupdf`."
            )
        if ezdxf is None:
            raise RuntimeError(
                "The `ezdxf` package is required. Install it via `pip install ezdxf`."
            )

        self.settings.ensure_output_directory()
        doc = fitz.open(self.settings.pdf_path)  # type: ignore[call-arg]
        try:
            dxf_path = self.settings.output_dxf_path
            doc_info = doc.metadata
            dxf_doc = ezdxf.new(self.settings.dxf_version)
            if doc_info.get("title"):
                dxf_doc.header["$PROJECTNAME"] = doc_info["title"]
            modelspace = dxf_doc.modelspace()

            warnings: List[str] = []
            for page_index in range(doc.page_count):
                page = doc.load_page(page_index)
                page_warnings = self._export_page(page, modelspace)
                warnings.extend(page_warnings)

            dxf_doc.saveas(dxf_path)

            dwg_path = None
            if self.settings.output_dwg_path is not None:
                dwg_path = self._export_dwg_via_cli(dxf_path)

            return ConversionResult(
                dxf_path=dxf_path,
                pages_converted=doc.page_count,
                dwg_path=dwg_path,
                warnings=warnings,
            )
        finally:
            doc.close()

    # ------------------------------------------------------------------
    def _export_dwg_via_cli(self, dxf_path: Path) -> Path:
        """Convert DXF to DWG using an external converter CLI if provided."""

        converter_cli = self.settings.dwg_converter_cli
        if converter_cli is None:
            raise RuntimeError(
                "A DWG output path was specified but no converter CLI was provided."
            )
        if not converter_cli.exists():
            raise FileNotFoundError(f"DWG converter executable '{converter_cli}' not found")

        output_path = self.settings.output_dwg_path
        assert output_path is not None  # mypy safety

        cmd = [
            str(converter_cli),
            str(dxf_path),
            str(output_path),
        ]
        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as exc:  # pragma: no cover - system dep.
            raise RuntimeError(
                f"DWG converter failed with exit code {exc.returncode}: {' '.join(cmd)}"
            ) from exc
        return output_path

    # ------------------------------------------------------------------
    def _export_page(self, page: "fitz.Page", modelspace: "ezdxf.layouts.BaseLayout") -> List[str]:
        """Export a single PDF page into the DXF modelspace."""

        page_warnings: List[str] = []
        page_height = page.rect.height
        scale = self.settings.unit_scale

        for drawing in page.get_drawings():
            try:
                for polyline in self._iter_polylines(drawing["items"], page_height):
                    if len(polyline) < 2:
                        continue
                    scaled = [(x * scale, y * scale) for x, y in polyline]
                    is_closed = _is_closed_polyline(polyline)
                    entity = modelspace.add_polyline2d(
                        scaled,
                        dxfattribs={
                            "layer": f"PDF_PAGE_{page.number + 1}",
                        },
                    )
                    if is_closed:
                        entity.close(True)
            except Exception as exc:  # pragma: no cover - defensive logging
                page_warnings.append(
                    f"Failed to export vector path on page {page.number + 1}: {exc}"
                )

        if self.settings.text_mode != TextExportMode.NONE:
            texts = page.get_text("dict")
            for block in texts.get("blocks", []):
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text = span.get("text", "").strip()
                        if not text:
                            continue
                        x, y = span.get("origin", (0.0, 0.0))
                        converted_point = self._pdf_to_cad_point((x, y), page_height)
                        scaled_point = (converted_point[0] * scale, converted_point[1] * scale)
                        font_height = span.get("size", 12.0) * scale
                        self._add_text_entity(modelspace, text, scaled_point, font_height)

        return page_warnings

    def _add_text_entity(
        self,
        modelspace: "ezdxf.layouts.BaseLayout",
        text: str,
        position: Point,
        height: float,
    ) -> None:
        """Insert a text entity into the DXF modelspace based on the configured mode."""

        if self.settings.text_mode == TextExportMode.TEXT:
            entity = modelspace.add_text(text, dxfattribs={"height": height})
            entity.set_pos(position, align="LEFT")
        elif self.settings.text_mode == TextExportMode.MTEXT:
            mtext = modelspace.add_mtext(text, dxfattribs={"height": height})
            mtext.set_location(position)

    def _iter_polylines(
        self,
        items: Sequence[Sequence[object]],
        page_height: float,
    ) -> Iterator[List[Point]]:
        """Yield polylines extracted from PDF drawing instructions."""

        polyline: List[Point] = []
        start_point: Optional[Point] = None

        for item in items:
            if not item:
                continue
            cmd = item[0]
            if cmd == "m":  # move
                if polyline:
                    yield polyline
                point = self._pdf_to_cad_point(item[1], page_height)
                polyline = [point]
                start_point = point
            elif cmd == "l":
                point = self._pdf_to_cad_point(item[1], page_height)
                if not polyline:
                    polyline = [point]
                    start_point = point
                else:
                    polyline.append(point)
            elif cmd == "c":  # cubic bezier
                if not polyline:
                    continue
                controls = [self._pdf_to_cad_point(ctrl, page_height) for ctrl in item[1:]]
                bezier_points = approximate_cubic_bezier(
                    polyline[-1], controls[0], controls[1], controls[2],
                    segments=self.settings.bezier_approximation_segments,
                )
                polyline.extend(bezier_points[1:])
            elif cmd == "re":  # rectangle
                rect = item[1]
                points = [
                    (rect.x0, rect.y0),
                    (rect.x1, rect.y0),
                    (rect.x1, rect.y1),
                    (rect.x0, rect.y1),
                    (rect.x0, rect.y0),
                ]
                converted = [self._pdf_to_cad_point(p, page_height) for p in points]
                if polyline:
                    yield polyline
                    polyline = []
                yield converted
                start_point = None
            elif cmd == "h":  # close path
                if polyline and start_point is not None:
                    polyline.append(start_point)
            else:
                # Ignore commands we do not handle explicitly (e.g., quad curves)
                continue

        if polyline:
            yield polyline

    def _pdf_to_cad_point(self, point: Sequence[float], page_height: float) -> Point:
        """Convert a PDF point (origin top-left) into CAD coordinates (origin bottom-left)."""

        x, y = point
        return (float(x), float(page_height - y))


# ----------------------------------------------------------------------
def approximate_cubic_bezier(
    p0: Point,
    p1: Point,
    p2: Point,
    p3: Point,
    *,
    segments: int = 24,
) -> List[Point]:
    """Approximate a cubic Bézier curve with a list of points."""

    if segments < 1:
        raise ValueError("segments must be >= 1")

    points: List[Point] = []
    for step in range(segments + 1):
        t = step / segments
        mt = 1 - t
        x = (
            mt ** 3 * p0[0]
            + 3 * mt ** 2 * t * p1[0]
            + 3 * mt * t ** 2 * p2[0]
            + t ** 3 * p3[0]
        )
        y = (
            mt ** 3 * p0[1]
            + 3 * mt ** 2 * t * p1[1]
            + 3 * mt * t ** 2 * p2[1]
            + t ** 3 * p3[1]
        )
        points.append((x, y))
    return points


def _is_closed_polyline(polyline: Sequence[Point]) -> bool:
    """Return True if the first and last vertex are identical."""

    if len(polyline) < 3:
        return False
    first = polyline[0]
    last = polyline[-1]
    return math.isclose(first[0], last[0]) and math.isclose(first[1], last[1])


__all__ = [
    "ConversionSettings",
    "ConversionResult",
    "PdfToCadConverter",
    "TextExportMode",
    "approximate_cubic_bezier",
]
