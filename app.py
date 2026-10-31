from flask import Flask, render_template, request, jsonify, send_from_directory
from PIL import Image, ImageEnhance, ImageFilter, ImageOps, UnidentifiedImageError
from pathlib import Path
from werkzeug.utils import secure_filename
from uuid import uuid4
import json
import time

app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
PROCESSED_DIR = BASE_DIR / "processed"
HISTORY_FILE = BASE_DIR / "history.json"

for directory in (UPLOAD_DIR, PROCESSED_DIR):
    directory.mkdir(parents=True, exist_ok=True)

app.config["MAX_CONTENT_LENGTH"] = 15 * 1024 * 1024
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}


def json_error(message, status=400):
    return jsonify({"error": message}), status


def safe_name(name):
    return (
        isinstance(name, str)
        and name == Path(name).name
        and name not in {"", ".", ".."}
        and "/" not in name
        and "\\" not in name
    )


def load_image(path):
    """Open an image safely and apply camera orientation metadata."""
    with Image.open(path) as source:
        source.verify()
    with Image.open(path) as source:
        image = ImageOps.exif_transpose(source)
        image.load()
        return image.copy()


def output_extension(fmt):
    return {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}[fmt]


def save_image(image, fmt="JPEG", quality=85):
    fmt = fmt.upper()
    if fmt not in ALLOWED_FORMATS:
        raise ValueError("Unsupported output format.")

    output_name = f"{uuid4().hex}.{output_extension(fmt)}"
    output_path = PROCESSED_DIR / output_name

    if fmt == "JPEG":
        if image.mode in ("RGBA", "LA") or "transparency" in image.info:
            rgba = image.convert("RGBA")
            background = Image.new("RGB", rgba.size, (255, 255, 255))
            background.paste(rgba, mask=rgba.getchannel("A"))
            image = background
        else:
            image = image.convert("RGB")
        image.save(output_path, format="JPEG", quality=quality, optimize=True)
    elif fmt == "WEBP":
        image.save(output_path, format="WEBP", quality=quality, method=6)
    else:
        if image.mode not in ("RGB", "RGBA", "L", "LA", "P"):
            image = image.convert("RGBA" if "A" in image.getbands() else "RGB")
        image.save(output_path, format="PNG", optimize=True)

    return output_name, output_path


def add_history(entry):
    try:
        history = json.loads(HISTORY_FILE.read_text(encoding="utf-8")) if HISTORY_FILE.exists() else []
        history.insert(0, entry)
        history = history[:50]
        HISTORY_FILE.write_text(json.dumps(history, indent=2), encoding="utf-8")
    except (OSError, json.JSONDecodeError):
        # History is helpful but should never prevent image processing.
        pass


@app.get("/")
def home():
    return render_template("index.html")


@app.post("/api/upload")
def upload():
    if "image" not in request.files:
        return json_error("Choose an image first.")

    uploaded = request.files["image"]
    if not uploaded.filename:
        return json_error("Choose an image first.")

    cleaned = secure_filename(uploaded.filename)
    extension = Path(cleaned).suffix.lower().lstrip(".")
    if extension not in ALLOWED_EXTENSIONS:
        return json_error("Use JPG, JPEG, PNG, or WEBP images.")

    stored_name = f"{uuid4().hex}.{extension}"
    stored_path = UPLOAD_DIR / stored_name

    try:
        uploaded.save(stored_path)
        image = load_image(stored_path)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        stored_path.unlink(missing_ok=True)
        return json_error("The selected file is not a valid or supported image.")

    if image.width > 12000 or image.height > 12000:
        stored_path.unlink(missing_ok=True)
        return json_error("Image dimensions are too large. Maximum dimension is 12000 pixels.")

    return jsonify({
        "message": "Image uploaded successfully.",
        "filename": stored_name,
        "url": f"/media/uploads/{stored_name}",
        "width": image.width,
        "height": image.height,
        "format": image.format or extension.upper(),
        "size": stored_path.stat().st_size
    })


@app.post("/api/process")
def process():
    data = request.get_json(silent=True) or {}
    filename = data.get("filename")
    operation = data.get("operation")

    if not safe_name(filename):
        return json_error("Invalid image filename.")

    source_path = UPLOAD_DIR / filename
    if not source_path.is_file():
        source_path = PROCESSED_DIR / filename
    if not source_path.is_file():
        return json_error("Image not found. Please upload it again.", 404)

    try:
        image = load_image(source_path)
    except (UnidentifiedImageError, OSError):
        return json_error("Could not open this image.")

    fmt = image.format or source_path.suffix.lstrip(".").upper()
    if fmt == "JPG":
        fmt = "JPEG"
    if fmt not in ALLOWED_FORMATS:
        fmt = "PNG"

    quality = 85

    try:
        if operation == "resize":
            width = int(data.get("width", 0))
            height_value = data.get("height")
            keep_ratio = bool(data.get("keep_ratio", True))
            if not 1 <= width <= 10000:
                return json_error("Width must be between 1 and 10000 pixels.")
            if keep_ratio:
                height = max(1, round(image.height * width / image.width))
            else:
                height = int(height_value or 0)
                if not 1 <= height <= 10000:
                    return json_error("Height must be between 1 and 10000 pixels.")
            image = image.resize((width, height), Image.Resampling.LANCZOS)
            message = f"Resized to {width} × {height} pixels."

        elif operation == "compress":
            quality = int(data.get("quality", 75))
            if not 10 <= quality <= 95:
                return json_error("Quality must be between 10 and 95.")
            fmt = "JPEG"
            message = f"Compressed as JPEG at {quality}% quality."

        elif operation == "crop":
            left = int(data.get("left", 0))
            top = int(data.get("top", 0))
            right = int(data.get("right", 0))
            bottom = int(data.get("bottom", 0))
            if not (0 <= left < right <= image.width and 0 <= top < bottom <= image.height):
                return json_error(f"Crop coordinates must fit within the image ({image.width} × {image.height}).")
            image = image.crop((left, top, right, bottom))
            message = f"Cropped to {image.width} × {image.height} pixels."

        elif operation == "rotate":
            degrees = int(data.get("degrees", 90))
            if degrees not in {90, 180, 270}:
                return json_error("Rotation must be 90, 180, or 270 degrees.")
            image = image.rotate(-degrees, expand=True)
            message = f"Rotated {degrees} degrees clockwise."

        elif operation == "flip":
            direction = data.get("direction")
            if direction == "horizontal":
                image = ImageOps.mirror(image)
                message = "Flipped horizontally."
            elif direction == "vertical":
                image = ImageOps.flip(image)
                message = "Flipped vertically."
            else:
                return json_error("Choose horizontal or vertical flip.")

        elif operation == "convert":
            fmt = str(data.get("format", "PNG")).upper()
            if fmt not in ALLOWED_FORMATS:
                return json_error("Choose JPG, PNG, or WEBP.")
            quality = int(data.get("quality", 85))
            message = f"Converted to {fmt}."

        elif operation == "adjust":
            brightness = float(data.get("brightness", 1))
            contrast = float(data.get("contrast", 1))
            if not (0 <= brightness <= 2 and 0 <= contrast <= 2):
                return json_error("Brightness and contrast must be between 0 and 2.")
            image = ImageEnhance.Brightness(image).enhance(brightness)
            image = ImageEnhance.Contrast(image).enhance(contrast)
            message = "Brightness and contrast adjusted."

        elif operation == "filter":
            effect = data.get("effect")
            if effect == "grayscale":
                image = ImageOps.grayscale(image)
                message = "Grayscale filter applied."
            elif effect == "blur":
                radius = float(data.get("radius", 2))
                if not 0 <= radius <= 20:
                    return json_error("Blur radius must be between 0 and 20.")
                image = image.filter(ImageFilter.GaussianBlur(radius))
                message = f"Blur filter applied (radius {radius})."
            elif effect == "sharpen":
                image = image.filter(ImageFilter.SHARPEN)
                message = "Sharpen filter applied."
            elif effect == "sepia":
                gray = ImageOps.grayscale(image).convert("RGB")
                pixels = gray.load()
                for y in range(gray.height):
                    for x in range(gray.width):
                        r, g, b = pixels[x, y]
                        pixels[x, y] = (
                            min(255, int(r * 1.07 + 20)),
                            min(255, int(g * 0.95 + 10)),
                            min(255, int(b * 0.82))
                        )
                image = gray
                message = "Sepia filter applied."
            else:
                return json_error("Choose grayscale, blur, sharpen, or sepia.")

        else:
            return json_error("Unknown image operation.")

        output_name, output_path = save_image(image, fmt=fmt, quality=quality)
        entry = {
            "filename": output_name,
            "operation": operation,
            "message": message,
            "width": image.width,
            "height": image.height,
            "format": fmt,
            "size": output_path.stat().st_size,
            "created": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        add_history(entry)

        return jsonify({
            **entry,
            "url": f"/media/processed/{output_name}"
        })

    except (ValueError, TypeError, OverflowError):
        return json_error("One or more values are invalid.")
    except Exception:
        app.logger.exception("Image processing failed")
        return json_error("Image processing failed. Try another image or setting.", 500)


@app.get("/api/history")
def get_history():
    try:
        history = json.loads(HISTORY_FILE.read_text(encoding="utf-8")) if HISTORY_FILE.exists() else []
    except (OSError, json.JSONDecodeError):
        history = []
    return jsonify(history)


@app.delete("/api/history")
def clear_history():
    try:
        HISTORY_FILE.write_text("[]", encoding="utf-8")
    except OSError:
        return json_error("Could not clear history.", 500)
    return jsonify({"message": "History cleared."})


@app.get("/media/<kind>/<filename>")
def media(kind, filename):
    if kind not in {"uploads", "processed"} or not safe_name(filename):
        return json_error("File not found.", 404)
    directory = UPLOAD_DIR if kind == "uploads" else PROCESSED_DIR
    return send_from_directory(directory, filename, as_attachment=False)


@app.errorhandler(413)
def too_large(_error):
    return json_error("File is too large. Maximum upload size is 15 MB.", 413)


if __name__ == "__main__":
    app.run(debug=True)
