# src/app.py
import os
import json
import uuid
import base64
import io

from flask import (
    Flask,
    render_template,
    send_from_directory,
    abort,
    request,
    redirect,
    url_for,
)

from PIL import Image
from PIL.ExifTags import TAGS
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv

load_dotenv()  # load .env if present

import os
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")

app = Flask(__name__, template_folder=TEMPLATE_DIR, static_folder=STATIC_DIR)

# ---- Personal gallery metadata ----
METADATA_PATH = "assets/data/photos.json"
PROCESSED_DIR = "assets/photos_processed"


def load_photos():
    if not os.path.exists(METADATA_PATH):
        return []
    with open(METADATA_PATH) as f:
        data = json.load(f)
        print("Loaded photo entries:", data)  # <-- ADD THIS
        return data


photos = load_photos()

# ---- EXIF helpers for uploads ----
def extract_exif_from_bytes(data: bytes) -> dict:
    img = Image.open(io.BytesIO(data))
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


# ---- Azure Blob Storage Setup ----
AZURE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
AZURE_CONTAINER = os.getenv("AZURE_STORAGE_CONTAINER", "uploads")

blob_service = None
container_client = None

if AZURE_CONNECTION_STRING:
    blob_service = BlobServiceClient.from_connection_string(
        AZURE_CONNECTION_STRING
    )
    container_client = blob_service.get_container_client(AZURE_CONTAINER)
    try:
        container_client.create_container()
    except Exception:
        # container may already exist
        pass


# ---- Routes ----
@app.route("/")
def home():
    return render_template("index.html")


@app.route("/gallery")
def gallery():
    return render_template("gallery.html", photos=photos)


@app.route("/photo/<filename>")
def photo_page(filename):
    photo = next((p for p in photos if p["filename"] == filename), None)
    if photo is None:
        abort(404)
    return render_template("photo.html", photo=photo)


@app.route("/images/<path:filename>")
def images(filename):
    return send_from_directory(PROCESSED_DIR, filename)


@app.route("/analyze", methods=["POST"])
def analyze():
    if "photo" not in request.files:
        return "No file uploaded", 400

    file = request.files["photo"]
    if file.filename == "":
        return "No selected file", 400

    # read bytes once
    data = file.read()

    # upload to Azure Blob (temporary)
    blob_name = None
    if container_client:
        ext = file.filename.rsplit(".", 1)[-1].lower()
        blob_name = f"{uuid.uuid4()}.{ext}"
        container_client.upload_blob(blob_name, data, overwrite=True)

    # EXIF extraction from bytes
    raw_exif = extract_exif_from_bytes(data)
    meta = clean_metadata(raw_exif)

    # base64 encode image to display without hitting blob again
    img_b64 = base64.b64encode(data).decode("utf-8")
    mime = "image/jpeg"  # good default

    return render_template(
        "result.html",
        meta=meta,
        image_data=img_b64,
        mime=mime,
        blob_name=blob_name,
    )


@app.route("/delete_blob/<blob_name>")
def delete_blob(blob_name):
    if container_client and blob_name:
        try:
            container_client.delete_blob(blob_name)
        except Exception:
            pass
    return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)

