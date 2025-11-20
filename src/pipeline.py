# src/pipeline.py
from PIL import Image
Image.MAX_IMAGE_PIXELS = None

import os
import json
from pathlib import Path
from PIL import Image
from PIL.ExifTags import TAGS

RAW_DIR = Path("assets/photos_raw")
PROCESSED_DIR = Path("assets/photos_processed")
DATA_DIR = Path("assets/data")
OUTPUT_JSON = DATA_DIR / "photos.json"


def extract_exif(img_path: Path) -> dict:
    img = Image.open(img_path)
    img.thumbnail((3000, 3000))
    exif_data = img._getexif()
    extracted = {}

    if exif_data:
        for tag, value in exif_data.items():
            tag_name = TAGS.get(tag, tag)
            extracted[tag_name] = value

    return extracted


def format_exposure(exposure_value):
    try:
        num, den = exposure_value
        return f"1/{int(den/num)}"
    except Exception:
        return str(exposure_value) if exposure_value is not None else None


def clean_metadata(raw: dict) -> dict:
    return {
        "camera": raw.get("Model"),
        "lens": raw.get("LensModel"),
        "iso": raw.get("ISOSpeedRatings"),
        "aperture": f"f/{raw.get('FNumber')}" if raw.get("FNumber") else None,
        "shutter": format_exposure(raw.get("ExposureTime")),
        "focal_length": str(raw.get("FocalLength")) if raw.get("FocalLength") else None,
        "timestamp": raw.get("DateTimeOriginal") or raw.get("DateTime"),
    }


def run_pipeline():
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    metadata_list = []

    for filename in os.listdir(RAW_DIR):
        if not filename.lower().endswith((".jpg", ".jpeg", ".png")):
            continue

        raw_path = RAW_DIR / filename
        processed_path = PROCESSED_DIR / filename

        img = Image.open(raw_path)
        img.save(processed_path)

        raw_exif = extract_exif(raw_path)
        cleaned = clean_metadata(raw_exif)
        cleaned["filename"] = filename

        metadata_list.append(cleaned)

    with open(OUTPUT_JSON, "w") as f:
        json.dump(metadata_list, f, indent=4)

    print(f"Pipeline complete. Extracted metadata for {len(metadata_list)} photos.")


if __name__ == "__main__":
    run_pipeline()

