"""Browser-vs-PDF visual regression for Presentation mode.

This test renders the production HTML helper and the Dashboard PDF from the
same stress payload at the 1366x768 reference viewport. It checks slides
1, 3, 5, and 7.

Test-only dependencies:
    playwright, pymupdf, pillow, numpy

Chromium must be installed for Playwright.
"""
from __future__ import annotations

import io
import sys
import tempfile
from pathlib import Path

import fitz
import numpy as np
from PIL import Image, ImageChops, ImageFilter
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from core.exports import build_presentation_pdf  # noqa: E402
from core.presentation import (  # noqa: E402
    REFERENCE_HEIGHT,
    REFERENCE_WIDTH,
    build_presentation_html,
)
from test_presentation_pdf import _sample_payload  # noqa: E402

BG = np.array([3, 42, 99], dtype=np.int16)
SLIDES = {
    "title": 0,
    "key_metrics": 2,
    "risks": 4,
    "finance": 6,
}


def _foreground_bbox(image: Image.Image):
    arr = np.asarray(image.convert("RGB"), dtype=np.int16)
    delta = np.max(np.abs(arr - BG), axis=2)
    mask = delta > 4
    # Slide number is absolute and intentionally excluded from flow-layout bbox.
    mask[:70, 1120:] = False
    ys, xs = np.where(mask)
    assert len(xs), "no foreground pixels detected"
    return (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)


def _bbox_delta(a, b):
    return tuple(abs(int(x) - int(y)) for x, y in zip(a, b))


def _blurred_mae(a: Image.Image, b: Image.Image):
    a = a.convert("RGB").filter(ImageFilter.GaussianBlur(radius=2)).resize((683, 384))
    b = b.convert("RGB").filter(ImageFilter.GaussianBlur(radius=2)).resize((683, 384))
    aa = np.asarray(a, dtype=np.float32)
    bb = np.asarray(b, dtype=np.float32)
    return float(np.mean(np.abs(aa - bb)) / 255.0)


def _region_mae(a: Image.Image, b: Image.Image, box):
    x, y, w, h = box
    left = max(0, int(round(x)))
    top = max(0, int(round(y)))
    right = min(REFERENCE_WIDTH, int(round(x + w)))
    bottom = min(REFERENCE_HEIGHT, int(round(y + h)))
    assert right > left and bottom > top
    return _blurred_mae(a.crop((left, top, right, bottom)), b.crop((left, top, right, bottom)))


def _save_diff(a: Image.Image, b: Image.Image, path: Path):
    diff = ImageChops.difference(a.convert("RGB"), b.convert("RGB"))
    diff.save(path)


def _browser_render(browser, payload, key, out_dir: Path):
    html = build_presentation_html(payload, include_ui=False, single_slide_key=key)
    html_path = out_dir / f"{key}.html"
    html_path.write_text(html, encoding="utf-8")

    page = browser.new_page(viewport={"width": REFERENCE_WIDTH, "height": REFERENCE_HEIGHT})
    page.goto(html_path.resolve().as_uri())
    page.wait_for_load_state("load")
    locator = page.locator(f'[data-slide-key="{key}"]')
    bbox = locator.bounding_box()
    assert bbox is not None
    assert round(bbox["x"]) == 0 and round(bbox["y"]) == 0
    assert round(bbox["width"]) == REFERENCE_WIDTH
    assert round(bbox["height"]) == REFERENCE_HEIGHT

    major_selectors = {
        "title": [".pres-title-h1", ".pres-filter-pills"],
        "key_metrics": [".pres-kpi-grid", ".pres-metric-rows"],
        "risks": [".pres-risk-grid", ".pres-risk-summary"],
        "finance": [".pres-fin-grid", ".pres-budget-card"],
    }[key]
    regions = {}
    for selector in major_selectors:
        box = page.locator(selector).bounding_box()
        assert box is not None, (key, selector)
        regions[selector] = box

    png = out_dir / f"browser_{key}.png"
    locator.screenshot(path=str(png), animations="disabled")
    page.close()
    return Image.open(png).convert("RGB"), regions


def _pdf_pages(payload, out_dir: Path):
    pdf = build_presentation_pdf(payload)
    assert pdf is not None and pdf.startswith(b"%PDF")
    (out_dir / "presentation_visual_fixture.pdf").write_bytes(pdf)
    doc = fitz.open(stream=pdf, filetype="pdf")
    assert len(doc) == 7
    rendered = {}
    for key, page_index in SLIDES.items():
        page = doc[page_index]
        pix = page.get_pixmap(matrix=fitz.Matrix(1, 1), alpha=False)
        assert pix.width == REFERENCE_WIDTH
        assert pix.height == REFERENCE_HEIGHT
        path = out_dir / f"pdf_{key}.png"
        pix.save(path)
        rendered[key] = Image.open(path).convert("RGB")
    doc.close()
    return rendered


def main():
    payload = _sample_payload()
    output_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "presentation_visual_artifacts"
    output_dir.mkdir(parents=True, exist_ok=True)

    pdf_images = _pdf_pages(payload, output_dir)
    results = []
    failures = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        for key in SLIDES:
            browser_image, regions = _browser_render(browser, payload, key, output_dir)
            pdf_image = pdf_images[key]
            _save_diff(browser_image, pdf_image, output_dir / f"diff_{key}.png")

            browser_bbox = _foreground_bbox(browser_image)
            pdf_bbox = _foreground_bbox(pdf_image)
            deltas = _bbox_delta(browser_bbox, pdf_bbox)
            mae = _blurred_mae(browser_image, pdf_image)

            limits = (12, 24, 24, 28)
            for side, delta, limit in zip(("left", "top", "right", "bottom"), deltas, limits):
                if delta > limit:
                    failures.append((key, side, delta, limit, browser_bbox, pdf_bbox))
            if mae > 0.075:
                failures.append((key, "global_mae", mae, 0.075))

            region_scores = {}
            for selector, box in regions.items():
                score = _region_mae(browser_image, pdf_image, box)
                region_scores[selector] = score
                if score > 0.16:
                    failures.append((key, selector, score, 0.16, box))

            results.append((key, browser_bbox, pdf_bbox, mae, region_scores))
        browser.close()

    for key, browser_bbox, pdf_bbox, mae, region_scores in results:
        print(
            f"VISUAL {key}: browser_bbox={browser_bbox} pdf_bbox={pdf_bbox} "
            f"mae={mae:.4f} regions={region_scores}"
        )
    if failures:
        raise AssertionError(f"visual parity failures: {failures}")
    print("test_presentation_visual: PASS")


if __name__ == "__main__":
    main()
