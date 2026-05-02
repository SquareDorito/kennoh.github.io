#!/usr/bin/env python3
"""Extract EXIF metadata from the Mother's Day gallery images.

This prints a JSON object keyed by relative image path. Each entry includes
best-effort capture time, camera model, and GPS coordinates when available.

Usage:
  python3 scripts/extract_photo_metadata.py
  python3 scripts/extract_photo_metadata.py --js
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image
from PIL.ExifTags import GPSTAGS, TAGS


ROOT = Path(__file__).resolve().parents[1]
IMG_ROOT = ROOT / "img"


def dms_to_decimal(dms, ref):
    def as_float(v):
        if hasattr(v, "numerator") and hasattr(v, "denominator"):
            return float(v.numerator) / float(v.denominator)
        if isinstance(v, tuple) and len(v) == 2:
            return float(v[0]) / float(v[1])
        return float(v)

    deg = as_float(dms[0])
    mins = as_float(dms[1])
    secs = as_float(dms[2])
    value = deg + mins / 60 + secs / 3600
    if ref in ("S", "W", b"S", b"W"):
        value = -value
    return round(value, 6)


def stringify_exif_value(value):
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8", "ignore")
        except Exception:
            return value.hex()
    if isinstance(value, tuple):
        return [stringify_exif_value(v) for v in value]
    return value


def place_from_gps(lat, lon):
    # Coarse, offline reverse-geocoding for the handful of recurring locations.
    places = [
        ((37.424, 37.432), (-122.196, -122.186), "Stanford, California"),
        ((37.384, 37.387), (-122.156, -122.153), "Los Altos Hills, California"),
        ((35.09, 35.12), (129.00, 129.05), "Busan, South Korea"),
        ((35.17, 35.20), (129.21, 129.24), "Busan, South Korea"),
        ((37.49, 37.52), (127.00, 127.02), "Seoul, South Korea"),
        ((41.48, 41.55), (-71.34, -71.29), "Newport, Rhode Island"),
        ((42.43, 42.47), (-76.50, -76.46), "Ithaca, New York"),
    ]
    for lat_range, lon_range, name in places:
        if lat_range[0] <= lat <= lat_range[1] and lon_range[0] <= lon <= lon_range[1]:
            return name
    return None


def extract_for(path: Path):
    try:
        image = Image.open(path)
        exif = image.getexif()
    except Exception:
        return None

    if not exif:
        return None

    tags = {TAGS.get(k, k): v for k, v in exif.items()}
    data = {}

    capture_time = tags.get("DateTimeOriginal") or tags.get("DateTime")
    if capture_time:
        data["time"] = capture_time.replace(":", "-", 2).replace(" ", " at ")

    model = tags.get("Model")
    make = tags.get("Make")
    if make or model:
        data["camera"] = " ".join(v for v in [make, model] if v).strip()

    gps_ifd = None
    if hasattr(exif, "get_ifd"):
        try:
            gps_ifd = exif.get_ifd(34853)
        except Exception:
            gps_ifd = None

    if gps_ifd:
        gps = {GPSTAGS.get(k, k): v for k, v in gps_ifd.items()}
        if "GPSLatitude" in gps and "GPSLongitude" in gps:
            lat = dms_to_decimal(gps["GPSLatitude"], gps.get("GPSLatitudeRef", "N"))
            lon = dms_to_decimal(gps["GPSLongitude"], gps.get("GPSLongitudeRef", "E"))
            data["gps"] = {"lat": lat, "lon": lon}
            place = place_from_gps(lat, lon)
            if place:
                data["location"] = place

    return data or None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--js", action="store_true", help="emit a JS assignment for window.EXIF_METADATA")
    args = parser.parse_args()

    out = {}
    for path in sorted(IMG_ROOT.rglob("*")):
        if path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".heic", ".tif", ".tiff", ".gif", ".webp", ".bmp"}:
            continue
        data = extract_for(path)
        if data:
            out[str(path.relative_to(ROOT)).replace("\\", "/")] = data

    if args.js:
        print("window.EXIF_METADATA = " + json.dumps(out, indent=2, sort_keys=True) + ";")
    else:
        print(json.dumps(out, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
