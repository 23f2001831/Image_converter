# image_converter_flask.py
import os
import io
import zipfile
import tempfile
from datetime import datetime
from PIL import Image, UnidentifiedImageError
from flask import (
    Flask, request, render_template_string, send_file, redirect, url_for, flash
)
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "replace-this-with-a-random-secret"  # for flash messages

# Allowed input extensions
ALLOWED_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".gif"}

# Template using Bootstrap CDN for a decent UI
INDEX_HTML = """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Batch Image Converter</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet"/>
  </head>
  <body class="bg-light">
    <div class="container py-5">
      <div class="card shadow-sm">
        <div class="card-body">
          <h3 class="card-title mb-3">Batch Image Converter</h3>
          <p class="text-muted">Select multiple images, choose output format and download a zip of converted images.</p>

          {% with messages = get_flashed_messages() %}
            {% if messages %}
              <div class="mb-3">
                {% for m in messages %}
                  <div class="alert alert-warning">{{ m }}</div>
                {% endfor %}
              </div>
            {% endif %}
          {% endwith %}

          <form method="POST" action="{{ url_for('convert') }}" enctype="multipart/form-data">
            <div class="mb-3">
              <label class="form-label">Choose images (multiple)</label>
              <input class="form-control" type="file" name="images" accept="image/*" multiple required>
              <div class="form-text">Supported: jpg, jpeg, png, webp, bmp, tiff, gif</div>
            </div>

            <div class="mb-3">
              <label class="form-label">Choose output format</label>
              <select class="form-select" name="format" required>
                <option value="webp">WEBP (smaller, modern)</option>
                <option value="jpg">JPG / JPEG (widely supported)</option>
                <option value="png">PNG (lossless)</option>
              </select>
            </div>

            <div class="mb-3">
              <label class="form-label">JPEG/WebP quality (1-100)</label>
              <input type="number" name="quality" class="form-control" value="90" min="1" max="100">
              <div class="form-text">Ignored for PNG (PNG is lossless)</div>
            </div>

            <button type="submit" class="btn btn-primary">Convert & Download ZIP</button>
            <a href="{{ url_for('index') }}" class="btn btn-link">Reset</a>
          </form>

          <hr/>
          <p class="text-muted small mb-0">Note: Files are uploaded to the local Flask server and converted there. The server returns a ZIP containing converted images.</p>
        </div>
      </div>
    </div>
  </body>
</html>
"""

def allowed_filename(filename: str) -> bool:
    _, ext = os.path.splitext(filename.lower())
    return ext in ALLOWED_EXTS

def convert_image_to(img_stream, target_format: str, quality: int) -> bytes:
    """
    Convert an image (file-like stream) to target_format and return bytes.
    target_format: 'webp', 'jpg' or 'png'
    """
    image = Image.open(img_stream)
    # For formats like JPEG that don't support alpha, convert RGBA->RGB
    if target_format in ("jpg", "jpeg") or target_format == "jpg":
        if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
            background = Image.new("RGB", image.size, (255, 255, 255))
            background.paste(image, mask=image.split()[-1])  # paste using alpha channel as mask
            image = background
        else:
            image = image.convert("RGB")
    # For PNG preserve transparency, for WEBP can preserve alpha.
    out_io = io.BytesIO()
    save_kwargs = {}
    if target_format in ("jpg", "jpeg"):
        save_kwargs["format"] = "JPEG"
        save_kwargs["quality"] = int(quality)
        save_kwargs["optimize"] = True
    elif target_format == "webp":
        save_kwargs["format"] = "WEBP"
        save_kwargs["quality"] = int(quality)
        # allow alpha in webp if present
    elif target_format == "png":
        save_kwargs["format"] = "PNG"
        # PNG is lossless; quality param ignored
    else:
        raise ValueError("Unsupported target format")

    image.save(out_io, **save_kwargs)
    out_io.seek(0)
    return out_io.read()

@app.route("/", methods=["GET"])
def index():
    return render_template_string(INDEX_HTML)

@app.route("/convert", methods=["POST"])
def convert():
    # Get files
    uploaded_files = request.files.getlist("images")
    target_format = request.form.get("format", "webp").lower()
    quality = request.form.get("quality", 90)
    try:
        quality = int(quality)
        if quality < 1 or quality > 100:
            quality = 90
    except Exception:
        quality = 90

    if not uploaded_files:
        flash("No files uploaded.")
        return redirect(url_for("index"))

    # create temporary directory to store converted files before zipping
    with tempfile.TemporaryDirectory(prefix="img_conv_") as tmpdir:
        converted_files = []
        errors = []
        for storage in uploaded_files:
            filename = secure_filename(storage.filename or "")
            if not filename:
                errors.append("A file with empty filename was skipped.")
                continue
            if not allowed_filename(filename):
                errors.append(f"Skipped unsupported file: {filename}")
                continue
            # determine base name and new ext
            base, _ = os.path.splitext(filename)
            # choose output extension
            out_ext = target_format
            if out_ext == "jpeg":
                out_ext = "jpg"
            out_name = f"{base}.{out_ext}"

            try:
                file_bytes = convert_image_to(storage.stream, out_ext, quality)
                out_path = os.path.join(tmpdir, out_name)
                with open(out_path, "wb") as f:
                    f.write(file_bytes)
                converted_files.append((out_name, out_path))
            except UnidentifiedImageError:
                errors.append(f"Cannot identify image file: {filename}")
            except Exception as e:
                errors.append(f"Error converting {filename}: {e}")

        if not converted_files:
            flash("No images were successfully converted. Errors: " + "; ".join(errors))
            return redirect(url_for("index"))

        # Create ZIP in-memory (or temporarily on disk) and send as response
        zip_io = io.BytesIO()
        with zipfile.ZipFile(zip_io, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            # Put files into zip with nice names
            for name, path in converted_files:
                zf.write(path, arcname=name)
            # Optionally include a small metadata file
            meta = f"Converted on {datetime.utcnow().isoformat()} UTC\nFormat: {target_format}\nFiles: {len(converted_files)}\n"
            if errors:
                meta += "Errors:\n" + "\n".join(errors) + "\n"
            zf.writestr("conversion_info.txt", meta)
        zip_io.seek(0)

        send_name = f"converted_images_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.zip"
        return send_file(
            zip_io,
            as_attachment=True,
            download_name=send_name,
            mimetype="application/zip"
        )

if __name__ == "__main__":
    # Get port from environment variable or default to 5000
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_ENV") == "development"
    app.run(debug=debug, host="0.0.0.0", port=port)
