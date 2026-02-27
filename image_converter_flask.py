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
import pypdfium2 as pdfium
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

app = Flask(__name__)
app.secret_key = "replace-this-with-a-random-secret"  # for flash messages

# Allowed input extensions
ALLOWED_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".gif", ".pdf"}

def validate_pdf_input(pdf_bytes: bytes) -> bool:
    """Check if input bytes look like a valid PDF."""
    return pdf_bytes[:5].startswith(b'%PDF-')

# Modern Template with separate Image and PDF sections
INDEX_HTML = """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Image & PDF Converter</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet"/>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" />
    <style>
      body {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        min-height: 100vh;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
      }
      .main-container {
        max-width: 1200px;
        margin: 0 auto;
        padding: 3rem 1rem;
      }
      .header {
        text-align: center;
        color: white;
        margin-bottom: 3rem;
      }
      .header h1 {
        font-size: 2.5rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
      }
      .header p {
        font-size: 1.1rem;
        opacity: 0.9;
      }
      .section-card {
        background: white;
        border-radius: 20px;
        padding: 2rem;
        margin-bottom: 2rem;
        box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        transition: transform 0.3s ease;
      }
      .section-card:hover {
        transform: translateY(-5px);
      }
      .section-header {
        display: flex;
        align-items: center;
        margin-bottom: 1.5rem;
        padding-bottom: 1rem;
        border-bottom: 2px solid #f0f0f0;
      }
      .section-icon {
        width: 50px;
        height: 50px;
        border-radius: 12px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.5rem;
        margin-right: 1rem;
        color: white;
      }
      .image-icon {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      }
      .pdf-icon {
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
      }
      .section-title {
        margin: 0;
        font-size: 1.5rem;
        font-weight: 600;
        color: #333;
      }
      .slider-container {
        background: #f8f9fa;
        padding: 1.5rem;
        border-radius: 12px;
        margin-top: 1rem;
      }
      .slider-label {
        font-weight: 600;
        color: #495057;
        margin-bottom: 1rem;
        display: flex;
        align-items: center;
        justify-content: space-between;
      }
      .size-badge {
        font-size: 1rem;
        padding: 0.5rem 1rem;
        border-radius: 20px;
      }
      .form-control, .form-select {
        border-radius: 10px;
        border: 2px solid #e9ecef;
        padding: 0.75rem;
      }
      .form-control:focus, .form-select:focus {
        border-color: #667eea;
        box-shadow: 0 0 0 0.2rem rgba(102, 126, 234, 0.25);
      }
      .btn-convert {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border: none;
        border-radius: 10px;
        padding: 1rem 2rem;
        font-weight: 600;
        color: white;
        width: 100%;
        font-size: 1.1rem;
        transition: all 0.3s ease;
      }
      .btn-convert:hover {
        transform: translateY(-2px);
        box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
        background: linear-gradient(135deg, #764ba2 0%, #667eea 100%);
      }
      .form-range {
        height: 8px;
      }
      .form-range::-webkit-slider-thumb {
        width: 20px;
        height: 20px;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      }
      .form-range::-moz-range-thumb {
        width: 20px;
        height: 20px;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      }
      .alert {
        border-radius: 10px;
        border: none;
      }
    </style>
  </head>
  <body>
    <div class="main-container">
      <div class="header">
        <h1><i class="fas fa-magic"></i> Image & PDF Converter</h1>
        <p>Compress and convert your images and PDFs with ease</p>
      </div>

      {% with messages = get_flashed_messages() %}
        {% if messages %}
          {% for m in messages %}
            <div class="alert alert-warning alert-dismissible fade show" role="alert">
              <i class="fas fa-exclamation-triangle"></i> {{ m }}
              <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
          {% endfor %}
        {% endif %}
      {% endwith %}

      <form method="POST" action="{{ url_for('convert') }}" enctype="multipart/form-data">
        
        <!-- IMAGE SECTION -->
        <div class="section-card">
          <div class="section-header">
            <div class="section-icon image-icon">
              <i class="fas fa-image"></i>
            </div>
            <div>
              <h2 class="section-title">Image Converter</h2>
              <small class="text-muted">Convert and compress images</small>
            </div>
          </div>

          <div class="mb-4">
            <label class="form-label"><i class="fas fa-file-upload"></i> Select Images</label>
            <input class="form-control" type="file" name="images" accept="image/*" multiple>
            <div class="form-text"><i class="fas fa-info-circle"></i> Supported: JPG, JPEG, PNG, WEBP, BMP, TIFF, GIF</div>
          </div>

          <div class="row mb-4">
            <div class="col-md-6">
              <label class="form-label"><i class="fas fa-exchange-alt"></i> Output Format</label>
              <select class="form-select" name="img_format">
                <option value="">Keep Original</option>
                <option value="webp">WEBP (Modern & Small)</option>
                <option value="jpg" selected>JPG (Universal)</option>
                <option value="png">PNG (Lossless)</option>
              </select>
            </div>
            <div class="col-md-6">
              <label class="form-label"><i class="fas fa-sliders-h"></i> Quality (1-100)</label>
              <input type="number" name="img_quality" class="form-control" value="85" min="1" max="100">
            </div>
          </div>

          <div class="slider-container">
            <div class="slider-label">
              <span><i class="fas fa-compress-arrows-alt"></i> Target Total Size</span>
              <span id="imgSizeValue" class="badge size-badge bg-secondary">No Limit</span>
            </div>
            <input type="range" class="form-range" name="img_target_size" id="imgTargetSize" min="0" max="5000" value="0" step="50">
            <div class="d-flex justify-content-between mt-2">
              <small class="text-muted">No Limit</small>
              <small class="text-muted">5000 KB</small>
            </div>
            <small class="text-muted d-block mt-2" style="color: #6c757d; font-style: italic;">
              <i class="fas fa-info-circle"></i> Applies to the combined size of ALL selected images
            </small>
          </div>
        </div>

        <!-- PDF SECTION -->
        <div class="section-card">
          <div class="section-header">
            <div class="section-icon pdf-icon">
              <i class="fas fa-file-pdf"></i>
            </div>
            <div>
              <h2 class="section-title">PDF Compressor</h2>
              <small class="text-muted">Reduce PDF file size</small>
            </div>
          </div>

          <div class="mb-4">
            <label class="form-label"><i class="fas fa-file-upload"></i> Select PDFs</label>
            <input class="form-control" type="file" name="pdfs" accept=".pdf" multiple>
            <div class="form-text"><i class="fas fa-info-circle"></i> Upload one or more PDF files to compress</div>
          </div>

          <div class="slider-container">
            <div class="slider-label">
              <span><i class="fas fa-compress-arrows-alt"></i> Target Total Size</span>
              <span id="pdfSizeValue" class="badge size-badge bg-secondary">No Limit</span>
            </div>
            <input type="range" class="form-range" name="pdf_target_size" id="pdfTargetSize" min="0" max="10000" value="0" step="100">
            <div class="d-flex justify-content-between mt-2">
              <small class="text-muted">No Limit</small>
              <small class="text-muted">10000 KB</small>
            </div>
            <small class="text-muted d-block mt-2" style="color: #6c757d; font-style: italic;">
              <i class="fas fa-info-circle"></i> PDFs are re-rendered and recompressed. Combined target for ALL selected PDFs.
            </small>
          </div>
        </div>

        <!-- SUBMIT BUTTON -->
        <button type="submit" class="btn btn-convert">
          <i class="fas fa-rocket"></i> Convert & Download ZIP
        </button>
      </form>

      <div class="text-center mt-4">
        <small class="text-white"><i class="fas fa-shield-alt"></i> Files are processed locally and securely</small>
      </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
    <script>
      // Image slider
      const imgSlider = document.getElementById('imgTargetSize');
      const imgSizeValue = document.getElementById('imgSizeValue');
      imgSlider.addEventListener('input', function() {
        if (this.value == 0) {
          imgSizeValue.textContent = 'No Limit';
          imgSizeValue.className = 'badge size-badge bg-secondary';
        } else {
          imgSizeValue.textContent = this.value + ' KB';
          imgSizeValue.className = 'badge size-badge bg-primary';
        }
      });

      // PDF slider
      const pdfSlider = document.getElementById('pdfTargetSize');
      const pdfSizeValue = document.getElementById('pdfSizeValue');
      pdfSlider.addEventListener('input', function() {
        if (this.value == 0) {
          pdfSizeValue.textContent = 'No Limit';
          pdfSizeValue.className = 'badge size-badge bg-secondary';
        } else {
          pdfSizeValue.textContent = this.value + ' KB';
          pdfSizeValue.className = 'badge size-badge bg-danger';
        }
      });
    </script>
  </body>
</html>
"""

def allowed_filename(filename: str) -> bool:
    _, ext = os.path.splitext(filename.lower())
    return ext in ALLOWED_EXTS

def compress_to_target_size(image, target_format: str, target_size_kb: int, initial_quality: int = 90) -> bytes:
    """
    Compress an image to meet target file size in KB.
    """
    target_bytes = target_size_kb * 1024
    quality = initial_quality
    
    # For formats like JPEG that don't support alpha, convert RGBA->RGB
    if target_format in ("jpg", "jpeg"):
        if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
            background = Image.new("RGB", image.size, (255, 255, 255))
            background.paste(image, mask=image.split()[-1])
            image = background
        else:
            image = image.convert("RGB")
    
    # Try to compress to target size
    for attempt in range(15):  # Max 15 attempts for better compression
        out_io = io.BytesIO()
        save_kwargs = {}
        
        if target_format in ("jpg", "jpeg"):
            save_kwargs["format"] = "JPEG"
            save_kwargs["quality"] = max(5, quality)  # Minimum quality of 5
            save_kwargs["optimize"] = True
        elif target_format == "webp":
            save_kwargs["format"] = "WEBP"
            save_kwargs["quality"] = max(5, quality)
        elif target_format == "png":
            save_kwargs["format"] = "PNG"
            save_kwargs["optimize"] = True
        
        image.save(out_io, **save_kwargs)
        current_size = out_io.tell()
        
        if current_size <= target_bytes or quality <= 5:
            out_io.seek(0)
            return out_io.read()
        
        # Reduce quality for next attempt (more aggressive)
        quality -= 7
    
    out_io.seek(0)
    return out_io.read()

def convert_image_to(img_stream, target_format: str, quality: int, target_size_kb: int = 0) -> bytes:
    """
    Convert an image (file-like stream) to target_format and return bytes.
    target_format: 'webp', 'jpg' or 'png'
    target_size_kb: If > 0, compress to this size in KB
    """
    img_stream.seek(0)
    image = Image.open(img_stream)
    
    # If target size specified, use compression algorithm
    if target_size_kb > 10:
        return compress_to_target_size(image, target_format, target_size_kb, quality)
    
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

def compress_pdf(pdf_bytes: bytes, target_size_kb: int = 0, quality: int = 80) -> bytes:
    """
    Compress a PDF by rasterizing each page to an image, compressing it,
    and rebuilding a new PDF from the compressed images.
    
    This is how real PDF compressors (iLovePDF, SmallPDF, etc.) work for
    image-heavy / scanned PDFs.
    
    Args:
        pdf_bytes: Raw bytes of the source PDF.
        target_size_kb: If > 0, try to get total size under this (KB).
        quality: JPEG quality to use (1-95). Lower = smaller file.
    Returns:
        Compressed PDF bytes.
    """
    # Determine the rendering DPI. Higher DPI = better quality but bigger.
    # Default 150 DPI is a good balance; drop to 100 or 72 for extreme compression.
    dpi = 150
    
    # If we have a very aggressive target, start with lower DPI and quality
    if target_size_kb > 0:
        # Rough heuristic: open the PDF to count pages
        src_pdf = pdfium.PdfDocument(pdf_bytes)
        n_pages = len(src_pdf)
        per_page_kb = target_size_kb / max(n_pages, 1)
        
        # Adjust DPI and quality based on per-page budget
        if per_page_kb < 30:
            dpi, quality = 72, 15
        elif per_page_kb < 60:
            dpi, quality = 72, 25
        elif per_page_kb < 100:
            dpi, quality = 100, 30
        elif per_page_kb < 200:
            dpi, quality = 100, 45
        elif per_page_kb < 400:
            dpi, quality = 120, 55
        elif per_page_kb < 600:
            dpi, quality = 150, 65
        else:
            dpi, quality = 150, 75
        src_pdf.close()
    
    compressed = _render_pdf_to_compressed_pdf(pdf_bytes, dpi, quality)
    
    # If we have a target and we're still over, do a second pass with lower settings
    if target_size_kb > 0 and len(compressed) > target_size_kb * 1024:
        for fallback_dpi, fallback_q in [(100, 35), (72, 25), (72, 15), (72, 10)]:
            compressed = _render_pdf_to_compressed_pdf(pdf_bytes, fallback_dpi, fallback_q)
            if len(compressed) <= target_size_kb * 1024:
                break
    
    return compressed


def _render_pdf_to_compressed_pdf(pdf_bytes: bytes, dpi: int = 150, quality: int = 75) -> bytes:
    """
    Core routine: render every page of *pdf_bytes* at *dpi*, compress each
    page image as JPEG at *quality*, and assemble a new PDF with ReportLab.
    """
    src_pdf = pdfium.PdfDocument(pdf_bytes)
    page_images = []
    
    try:
        for page_index in range(len(src_pdf)):
            page = src_pdf[page_index]
            
            # Get the page size in points (1 point = 1/72 inch)
            width_pt = page.get_width()
            height_pt = page.get_height()
            
            # Render to bitmap
            scale = dpi / 72.0
            bitmap = page.render(scale=scale, rotation=0)
            pil_image = bitmap.to_pil()
            
            # Convert to RGB if needed (drop alpha)
            if pil_image.mode != "RGB":
                background = Image.new("RGB", pil_image.size, (255, 255, 255))
                if pil_image.mode == "RGBA":
                    background.paste(pil_image, mask=pil_image.split()[-1])
                else:
                    background.paste(pil_image)
                pil_image = background
            
            # Compress to JPEG in memory
            img_io = io.BytesIO()
            pil_image.save(img_io, format="JPEG", quality=quality, optimize=True)
            img_io.seek(0)
            
            page_images.append((img_io, width_pt, height_pt))
    finally:
        src_pdf.close()
    
    # Build a new PDF with ReportLab
    pdf_io = io.BytesIO()
    c = canvas.Canvas(pdf_io)
    
    for img_io, w_pt, h_pt in page_images:
        c.setPageSize((w_pt, h_pt))
        c.drawImage(ImageReader(img_io), 0, 0, width=w_pt, height=h_pt)
        c.showPage()
    
    c.save()
    pdf_io.seek(0)
    return pdf_io.getvalue()

@app.route("/", methods=["GET"])
def index():
    return render_template_string(INDEX_HTML)

@app.route("/convert", methods=["POST"])
def convert():
    # Get files from both sections
    image_files = request.files.getlist("images")
    pdf_files = request.files.getlist("pdfs")
    
    # Get image parameters
    img_format = request.form.get("img_format", "").lower()
    img_quality = request.form.get("img_quality", 85)
    img_target_size = request.form.get("img_target_size", 0)
    
    # Get PDF parameters
    pdf_target_size = request.form.get("pdf_target_size", 0)
    
    # Parse image quality
    try:
        img_quality = int(img_quality)
        if img_quality < 1 or img_quality > 100:
            img_quality = 85
    except Exception:
        img_quality = 85
    
    # Parse image target size
    try:
        img_target_size = int(img_target_size)
        if img_target_size < 50:
            img_target_size = 0  # Disable target size
    except Exception:
        img_target_size = 0
    
    # Parse PDF target size
    try:
        pdf_target_size = int(pdf_target_size)
        if pdf_target_size < 100:
            pdf_target_size = 0  # Disable target size
    except Exception:
        pdf_target_size = 0

    # Check if any files were uploaded
    if not image_files and not pdf_files:
        flash("No files uploaded. Please select at least one image or PDF.")
        return redirect(url_for("index"))
    
    # Check if all uploaded files are empty
    has_valid_files = False
    for f in image_files:
        if f and f.filename:
            has_valid_files = True
            break
    if not has_valid_files:
        for f in pdf_files:
            if f and f.filename:
                has_valid_files = True
                break
    
    if not has_valid_files:
        flash("No valid files uploaded.")
        return redirect(url_for("index"))

    # create temporary directory to store converted files before zipping
    with tempfile.TemporaryDirectory(prefix="converter_") as tmpdir:
        converted_files = []
        errors = []
        
        # PROCESS IMAGES with total size tracking
        total_image_size = 0
        img_target_bytes = img_target_size * 1024 if img_target_size > 50 else 0
        image_quality_reduction = 0  # Track cumulative quality reduction
        
        for storage in image_files:
            if not storage or not storage.filename:
                continue
                
            filename = secure_filename(storage.filename)
            if not filename:
                continue
            
            base, ext = os.path.splitext(filename)
            
            # Check if it's a valid image extension
            if ext.lower() not in {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".gif"}:
                errors.append(f"Skipped invalid image: {filename}")
                continue
            
            # Determine output format
            if img_format and img_format in ["webp", "jpg", "png"]:
                out_ext = img_format
            else:
                out_ext = ext.lstrip('.').lower()
                if out_ext == "jpeg":
                    out_ext = "jpg"
            
            out_name = f"{base}.{out_ext}"

            try:
                storage.stream.seek(0)
                
                # Adjust quality based on cumulative size
                adjusted_quality = max(5, img_quality - image_quality_reduction)
                
                # If we have a target size, calculate per-file budget
                if img_target_bytes > 0:
                    # Estimate number of remaining images
                    remaining_images = sum(1 for f in image_files if f and f.filename and 
                                         os.path.splitext(f.filename)[1].lower() in 
                                         {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".gif"})
                    per_file_budget = (img_target_bytes - total_image_size) / max(remaining_images, 1)
                    
                    # Load image and compress to budget
                    storage.stream.seek(0)
                    img = Image.open(storage.stream)
                    # Load image data before closing stream
                    img.load()
                    file_bytes = compress_to_target_size(img, out_ext, 
                                                        max(50, int(per_file_budget / 1024)), adjusted_quality)
                else:
                    file_bytes = convert_image_to(storage.stream, out_ext, adjusted_quality, 0)
                
                file_size = len(file_bytes)
                
                # Check if adding this file exceeds total target
                if img_target_bytes > 0 and (total_image_size + file_size) > img_target_bytes:
                    # Apply more aggressive compression
                    image_quality_reduction += 15
                    adjusted_quality = max(5, img_quality - image_quality_reduction)
                    storage.stream.seek(0)
                    file_bytes = convert_image_to(storage.stream, out_ext, adjusted_quality, 0)
                    file_size = len(file_bytes)
                
                total_image_size += file_size
                out_path = os.path.join(tmpdir, out_name)
                with open(out_path, "wb") as f:
                    f.write(file_bytes)
                converted_files.append((out_name, out_path))
                
            except UnidentifiedImageError:
                errors.append(f"Cannot identify image file: {filename}")
            except Exception as e:
                errors.append(f"Error converting {filename}: {str(e)}")
        
        # PROCESS PDFs with total size tracking and real compression
        total_pdf_size = 0
        pdf_target_bytes = pdf_target_size * 1024 if pdf_target_size > 100 else 0
        
        # First pass: read all PDFs into memory so we can count them
        pdf_items = []
        for storage in pdf_files:
            if not storage or not storage.filename:
                continue
            filename = secure_filename(storage.filename)
            if not filename:
                continue
            base, ext = os.path.splitext(filename)
            if ext.lower() != ".pdf":
                errors.append(f"Skipped non-PDF file: {filename}")
                continue
            storage.stream.seek(0)
            pdf_items.append((filename, base, storage.stream.read()))
        
        n_pdfs = len(pdf_items)
        
        for filename, base, raw_bytes in pdf_items:
            out_name = f"{base}_compressed.pdf"
            
            try:
                original_kb = len(raw_bytes) / 1024
                
                if pdf_target_bytes > 0:
                    remaining_budget_bytes = pdf_target_bytes - total_pdf_size
                    remaining_pdfs = n_pdfs - len([f for f in converted_files if f[0].endswith('_compressed.pdf')])
                    per_file_budget_kb = max(20, (remaining_budget_bytes / 1024) / max(remaining_pdfs, 1))
                    
                    file_bytes = compress_pdf(raw_bytes, int(per_file_budget_kb))
                else:
                    # No target — light compression at quality 80
                    file_bytes = compress_pdf(raw_bytes, 0, 80)
                
                file_size = len(file_bytes)
                compressed_kb = file_size / 1024
                total_pdf_size += file_size
                
                out_path = os.path.join(tmpdir, out_name)
                with open(out_path, "wb") as f:
                    f.write(file_bytes)
                converted_files.append((out_name, out_path))
                
                # Log compression ratio
                ratio = (1 - compressed_kb / original_kb) * 100 if original_kb > 0 else 0
                errors.append(f"PDF {filename}: {original_kb:.0f}KB → {compressed_kb:.0f}KB ({ratio:.0f}% reduction)")
                
            except Exception as e:
                errors.append(f"Error compressing PDF {filename}: {str(e)}")

        if not converted_files:
            error_msg = "No files were successfully processed."
            if errors:
                error_msg += " Errors: " + "; ".join(errors)
            flash(error_msg)
            return redirect(url_for("index"))

        # Create ZIP in-memory and send as response
        zip_io = io.BytesIO()
        with zipfile.ZipFile(zip_io, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            # Put files into zip
            for name, path in converted_files:
                zf.write(path, arcname=name)
            
            # Add metadata file
            meta_lines = [
                f"Processed on {datetime.utcnow().isoformat()} UTC",
                f"Total files processed: {len(converted_files)}",
                f"Total images size: {total_image_size/1024:.2f} KB" if total_image_size > 0 else "Total images size: 0 KB",
                f"Total PDFs size: {total_pdf_size/1024:.2f} KB" if total_pdf_size > 0 else "Total PDFs size: 0 KB",
                f"Image format: {img_format or 'Original'}",
                f"Image quality: {img_quality}",
                f"Image target size: {img_target_size} KB (combined)" if img_target_size > 0 else "Image target size: No limit",
                f"PDF target size: {pdf_target_size} KB (combined)" if pdf_target_size > 0 else "PDF target size: No limit",
            ]
            
            if errors:
                meta_lines.append("\nNotes/Errors encountered:")
                meta_lines.extend(errors)
            
            zf.writestr("conversion_info.txt", "\n".join(meta_lines))
        
        zip_io.seek(0)

        send_name = f"converted_files_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.zip"
        response = send_file(
            zip_io,
            as_attachment=True,
            download_name=send_name,
            mimetype="application/zip"
        )
        
        # Add headers for better compatibility
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        
        return response

if __name__ == "__main__":
    # Get port from environment variable or default to 5000
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_ENV") == "development"
    app.run(debug=debug, host="0.0.0.0", port=port)
