from fasthtml.common import *
from google import genai
import base64
import io
from PIL import Image
import fitz  # PyMuPDF for PDF handling
import os
from starlette.requests import Request
from starlette.datastructures import UploadFile
import httpx
import json
import re
from typing import Optional, Tuple

# Set the port to 5001 as specified in the FastHTML documentation
port = 5001

# Initialize Gemini API (allow override by environment while keeping current default)
api_key = os.getenv("GOOGLE_API_KEY", "AIzaSyAAfy_NT9EmLjzUn1s053Y8zzSTzF6LZ6c")
os.environ["GOOGLE_API_KEY"] = api_key

# Initialize the Gemini client
client = genai.Client(api_key=api_key)

# LINE Bot configuration (allow override by environment while keeping current default)
LINE_CHANNEL_ACCESS_TOKEN = os.getenv(
    "LINE_CHANNEL_ACCESS_TOKEN",
    "XVccgZwoUfD88aXBfeEGNf0Mq0kHii4a/aQP3XTXjwDm2hksTnH1hyelE/DdJdg+tU15+hAnAl13bYpjcdv0Sz2jZYQBmYQofw4ldp2reZ1WoUimsGm4VpnFgPUqMgMF49Us722E0XDIbB/I5lvIxQdB04t89/1O/w1cDnyilFU="
)
LINE_REPLY_URL = "https://api.line.me/v2/bot/message/reply"
LINE_CONTENT_URL = "https://api-data.line.me/v2/bot/message/{messageId}/content"


def _detect_mime_from_bytes(image_bytes: bytes) -> str:
    """Best-effort MIME detection from image bytes using PIL; defaults to image/jpeg."""
    try:
        with Image.open(io.BytesIO(image_bytes)) as im:
            fmt = (im.format or "").upper()
        mapping = {
            "JPEG": "image/jpeg",
            "JPG": "image/jpeg",
            "PNG": "image/png",
            "GIF": "image/gif",
            "BMP": "image/bmp",
            "WEBP": "image/webp",
            "TIFF": "image/tiff",
            "ICO": "image/x-icon",
            "HEIC": "image/heic",
            "HEIF": "image/heif",
        }
        return mapping.get(fmt, "image/jpeg")
    except Exception:
        return "image/jpeg"

def extract_text_from_image(image_data, mime_type: Optional[str] = None):
    """Extract text from image using Gemini Vision API.

    image_data can be raw bytes or base64 string. If bytes and mime_type
    is not provided, attempt to detect it.
    """
    try:
        # Create the prompt for OCR
        prompt = "Extract all text from this image. Return only the text content, no additional formatting or explanations."
        
        # Convert image data to base64 for proper API format and determine MIME
        if isinstance(image_data, bytes):
            image_base64 = base64.b64encode(image_data).decode('utf-8')
            mime = mime_type or _detect_mime_from_bytes(image_data)
        else:
            image_base64 = image_data
            mime = mime_type or "image/jpeg"
        
        # Use Gemini to extract text with proper content format
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=[
                {
                    "role": "user",
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mime_type": mime,
                                "data": image_base64
                            }
                        }
                    ]
                }
            ]
        )
        
        return response.text
    except Exception as e:
        return f"Error extracting text from image: {str(e)}"

def extract_text_from_pdf(pdf_data):
    """Extract text from PDF using PyMuPDF and then use Gemini for OCR on images"""
    try:
        # Open PDF with PyMuPDF
        pdf_document = fitz.open(stream=pdf_data, filetype="pdf")
        extracted_text = ""
        
        for page_num in range(pdf_document.page_count):
            page = pdf_document[page_num]
            
            # First try to extract text directly
            page_text = page.get_text()
            if page_text.strip():
                extracted_text += f"\n--- Page {page_num + 1} ---\n{page_text}\n"
            else:
                # If no text found, convert page to image and use OCR
                pix = page.get_pixmap()
                img_data = pix.tobytes("png")
                
                # Convert to base64 for Gemini
                img_base64 = base64.b64encode(img_data).decode('utf-8')
                
                # Use Gemini for OCR (explicit PNG)
                ocr_text = extract_text_from_image(img_base64, mime_type="image/png")
                extracted_text += f"\n--- Page {page_num + 1} (OCR) ---\n{ocr_text}\n"
        
        pdf_document.close()
        return extracted_text
        
    except Exception as e:
        return f"Error processing PDF: {str(e)}"

def process_uploaded_file(file_data, filename):
    """Process uploaded file based on its type"""
    file_extension = filename.lower().split('.')[-1]
    
    if file_extension in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp']:
        # Process as image
        return extract_text_from_image(file_data)
    elif file_extension == 'pdf':
        # Process as PDF
        return extract_text_from_pdf(file_data)
    else:
        return f"Unsupported file type: {file_extension}. Please upload an image (jpg, png, gif, bmp, webp) or PDF file."


# ========================= Arithmetic Interpretation Engine ========================= #

FULL_TOP_BOTTOM_HEADLINES = {
    "บนล่าง", "บล", "บ/ล", "บน+ล่าง", "บ+ล", "บ-ล", "บน-ล่าง", "ล่างบน"
}
SINGLE_HEADLINES = {"บน", "ล่าง"}


def _normalize(s: str) -> str:
    return s.strip()


def _is_headline(line: str) -> Tuple[bool, str]:
    t = _normalize(line)
    if t in FULL_TOP_BOTTOM_HEADLINES:
        return True, t
    if t in SINGLE_HEADLINES:
        return True, t
    return False, ""


def _perm_count(num_str: str) -> Tuple[int, str]:
    # Only 3 or 4 digit numbers are supported by explicit rules
    digits = list(num_str)
    n = len(digits)
    if n not in (3, 4):
        return 0, f"Unsupported digit length: {n}. Only 3 or 4 allowed by rules."
    from collections import Counter
    c = Counter(digits)
    freqs = sorted(c.values(), reverse=True)
    if n == 3:
        if freqs == [3]:
            return 1, "3-digit: all same → 1 perm"
        if freqs == [2, 1]:
            return 3, "3-digit: two same → 3 perms"
        if freqs == [1, 1, 1]:
            return 6, "3-digit: all different → 6 perms"
        return 0, "Unsupported 3-digit pattern"
    # n == 4
    if freqs == [4]:
        return 1, "4-digit: all same → 1 perm"
    if freqs == [2, 2]:
        return 6, "4-digit: two pairs → 6 perms"
    if freqs == [2, 1, 1]:
        return 12, "4-digit: one pair repeated → 12 perms"
    if freqs == [1, 1, 1, 1]:
        return 24, "4-digit: all different → 24 perms"
    return 0, "Unsupported 4-digit pattern"


def _parse_number(s: str) -> int | None:
    try:
        return int(s)
    except Exception:
        return None


def _is_full_top_bottom(headline: str) -> bool:
    return _normalize(headline) in FULL_TOP_BOTTOM_HEADLINES


from typing import Union


def _format_currency(x: Union[int, float]) -> str:
    # Simple formatting; keep as integer if possible
    if isinstance(x, float) and not x.is_integer():
        return f"{x}"
    try:
        xi = int(x)
        return str(xi)
    except Exception:
        return str(x)


def compute_from_text(text: str) -> dict:
    """Parse OCR text and compute totals strictly per rules.
    Returns a structure with sections, lines, subtotals, and a grand total.
    """
    lines = [l.strip() for l in text.splitlines()]
    sections = []
    current = {
        "headline": "No headline",
        "lines": [],
        "subtotal": 0
    }

    def push_section():
        nonlocal current
        if current["lines"]:
            # finalize subtotal
            current["subtotal"] = sum(li["final"] for li in current["lines"])
            sections.append(current)
        current = {"headline": "No headline", "lines": [], "subtotal": 0}

    for raw in lines:
        if not raw:
            continue
        is_head, head = _is_headline(raw)
        if is_head:
            # close previous section
            push_section()
            current["headline"] = head
            continue

        # Determine headline effects
        full_tb = _is_full_top_bottom(current["headline"])  # both effects
        # single headlines have no doubling

        detail = {
            "raw": raw,
            "rules": [],
            "final": 0
        }

        # Detect groups
        if raw.startswith("{") and "}" in raw and "=" in raw:
            try:
                inside = raw[raw.find("{")+1:raw.find("}")]
                items = [i.strip() for i in inside.split(",") if i.strip()]
                rhs = raw[raw.find("}")+1:].strip()
                assert rhs.startswith("="), "Group must have ="
                rhs = rhs[1:].strip()
                # Case B: = X × Y
                if "×" in rhs:
                    # parse X × Y
                    parts = [p.strip() for p in rhs.split("×")]
                    if len(parts) != 2:
                        raise ValueError("Invalid group multiplier format")
                    X = _parse_number(parts[0])
                    Y = _parse_number(parts[1])
                    if X is None or Y is None:
                        raise ValueError("Invalid numbers in group multiplier")
                    total = 0
                    item_details = []
                    for it in items:
                        # Each item computed individually per Format A logic
                        perm, perm_note = _perm_count(it)
                        if perm == 0:
                            raise ValueError(perm_note)
                        val = perm * Y + X
                        item_details.append({
                            "item": it,
                            "perm": perm,
                            "note": perm_note,
                            "calc": f"({perm} × {Y}) + {X} = {val}"
                        })
                        total += val
                    # Headline result doubler applies AFTER calculation
                    doubled = False
                    if full_tb:
                        total *= 2
                        doubled = True
                    detail["rules"].append("Group with = X × Y → compute each item individually and sum")
                    if doubled:
                        detail["rules"].append("Headline Result Doubler applied (×2 after)")
                    detail["final"] = total
                    detail["group_items"] = item_details
                    current["lines"].append(detail)
                    continue
                else:
                    # Case A or C style of groups without ×: treat as value per item
                    V = _parse_number(rhs)
                    if V is None:
                        raise ValueError("Invalid group explicit value")
                    group_total = V * len(items)
                    doubled = False
                    if full_tb:
                        # Result doubler AFTER calculation
                        group_total *= 2
                        doubled = True
                    detail["rules"].append("Group with explicit per-item value → value × count")
                    if doubled:
                        detail["rules"].append("Headline Result Doubler applied (×2 after)")
                    detail["final"] = group_total
                    detail["group_value"] = V
                    detail["group_count"] = len(items)
                    current["lines"].append(detail)
                    continue
            except Exception as e:
                detail["rules"].append(f"Error parsing group: {e}")
                detail["final"] = 0
                current["lines"].append(detail)
                continue

        # Non-group: determine format
        # Identify order of symbols
        has_eq = "=" in raw
        has_mul = "×" in raw

        # Helper to clean tokens
        def tok(s: str) -> str:
            return s.strip()

        if has_eq and has_mul:
            # Decide between A (ABC = X × Y) vs C (ABC × Y = B)
            idx_mul = raw.find("×")
            idx_eq = raw.find("=")
            if idx_mul > idx_eq:
                # Format A: left number, right has X × Y
                try:
                    left, rhs = raw.split("=")
                    left = tok(left)
                    rhs = tok(rhs)
                    abc = re.sub(r"\D", "", left)
                    if not abc:
                        raise ValueError("No number on left side")
                    Xs, Ys = [tok(p) for p in rhs.split("×")]
                    X = _parse_number(Xs)
                    Y = _parse_number(Ys)
                    if X is None or Y is None:
                        raise ValueError("Invalid X or Y")
                    # Permutations used here
                    perm, perm_note = _perm_count(abc)
                    if perm == 0:
                        raise ValueError(perm_note)
                    # No multiplier doubler for Format A (rule: only ABC × Y)
                    val = perm * Y + X
                    # Headline result doubler AFTER
                    doubled = False
                    if full_tb:
                        val *= 2
                        doubled = True
                    detail["rules"].append("Format A: ABC = X × Y → (perms × Y) + X")
                    detail["rules"].append(perm_note)
                    if doubled:
                        detail["rules"].append("Headline Result Doubler applied (×2 after)")
                    detail["final"] = val
                except Exception as e:
                    detail["rules"].append(f"Error Format A: {e}")
                    detail["final"] = 0
                current["lines"].append(detail)
                continue
            else:
                # Format C: ABC × Y = B (ignore permutations; compute Y × B); apply multipliers later
                try:
                    left, Bs = raw.split("=")
                    left = tok(left)
                    Bs = tok(Bs)
                    # parse left as something like 'ABC × Y'
                    parts = [tok(p) for p in left.split("×")]
                    if len(parts) != 2:
                        raise ValueError("Invalid left side for chained format")
                    abc = re.sub(r"\D", "", parts[0])
                    Ys = parts[1]
                    Y = _parse_number(Ys)
                    B = _parse_number(Bs)
                    if Y is None or B is None:
                        raise ValueError("Invalid Y or B numbers")
                    # Ignore permutations
                    val = Y * B
                    # For chained format, multiplier doubling (Effect 1) does NOT apply.
                    # Apply result doubler AFTER if full TB
                    doubled = False
                    if full_tb:
                        val *= 2
                        doubled = True
                    detail["rules"].append("Format C: ABC × Y = B → ignore permutations; compute Y × B")
                    if doubled:
                        detail["rules"].append("Headline Result Doubler applied (×2 after)")
                    detail["final"] = val
                except Exception as e:
                    detail["rules"].append(f"Error Format C: {e}")
                    detail["final"] = 0
                current["lines"].append(detail)
                continue

        if has_mul and not has_eq:
            # Format B: ABC × Y
            try:
                left, Ys = [tok(p) for p in raw.split("×")]
                abc = re.sub(r"\D", "", left)
                if not abc:
                    raise ValueError("No number before ×")
                Y = _parse_number(Ys)
                if Y is None:
                    raise ValueError("Invalid Y")
                # Apply Multiplier Doubler BEFORE if full TB
                if full_tb:
                    Y = Y * 2
                    detail["rules"].append("Headline Multiplier Doubler applied (Y × 2 before)")
                perm, perm_note = _perm_count(abc)
                if perm == 0:
                    raise ValueError(perm_note)
                val = perm * Y
                # Apply Result Doubler AFTER if full TB
                if full_tb:
                    val *= 2
                    detail["rules"].append("Headline Result Doubler applied (×2 after)")
                detail["rules"].append("Format B: ABC × Y → perms × Y")
                detail["rules"].append(perm_note)
                detail["final"] = val
            except Exception as e:
                detail["rules"].append(f"Error Format B: {e}")
                detail["final"] = 0
            current["lines"].append(detail)
            continue

        if has_eq and not has_mul:
            # Flat value: ABC = V
            try:
                left, Vs = [tok(p) for p in raw.split("=")]
                abc = re.sub(r"\D", "", left)
                V = _parse_number(Vs)
                if V is None:
                    raise ValueError("Invalid value after =")
                val = V
                special_applied = False
                # Special: two-digit flat values under full TB → V × 2 (only once)
                if full_tb and abc and len(abc) == 2:
                    val = V * 2
                    special_applied = True
                    detail["rules"].append("Special: two-digit flat value under บนล่าง/บล → V × 2")
                # Otherwise, apply result doubler AFTER if full TB
                elif full_tb:
                    val *= 2
                    detail["rules"].append("Headline Result Doubler applied (×2 after)")
                detail["rules"].append("Flat value: take V as-is (rules may modify)")
                detail["final"] = val
            except Exception as e:
                detail["rules"].append(f"Error Flat value: {e}")
                detail["final"] = 0
            current["lines"].append(detail)
            continue

        # Unrecognized line
        detail["rules"].append("Unrecognized format; skipped")
        detail["final"] = 0
        current["lines"].append(detail)

    # push last section
    push_section()

    grand_total = sum(sec["subtotal"] for sec in sections)

    # Build a human-readable report
    report_lines = []
    for sec in sections:
        report_lines.append(f"Section: {sec['headline']}")
        for li in sec["lines"]:
            report_lines.append(f"- Line: {li['raw']}")
            for r in li["rules"]:
                report_lines.append(f"  • {r}")
            report_lines.append(f"  = {li['final']}")
        report_lines.append(f"Subtotal: {sec['subtotal']}")
        report_lines.append("")
    report_lines.append(f"GRAND TOTAL: {grand_total}")

    return {
        "sections": sections,
        "grand_total": grand_total,
        "report": "\n".join(report_lines)
    }

async def download_line_image_content(message_id: str):
    """Download image content from LINE API"""
    try:
        print(f"Downloading image content for message ID: {message_id}")
        
        headers = {
            'Authorization': f'Bearer {LINE_CHANNEL_ACCESS_TOKEN}'
        }
        
        url = LINE_CONTENT_URL.format(messageId=message_id)
        print(f"LINE Content API Request: {url}")
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            
            print(f"LINE Content API Response Status: {response.status_code}")
            print(f"Content-Type: {response.headers.get('content-type', 'unknown')}")
            print(f"Content-Length: {len(response.content)} bytes")
            
            return {"success": True, "content": response.content}
            
    except Exception as e:
        print(f"Error downloading image content: {str(e)}")
        return {"success": False, "error": str(e)}

async def reply_to_line_message(reply_token: str, messages: list):
    """Send a reply message to LINE"""
    try:
        print(f"Sending reply with messages: {messages}")
        
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {LINE_CHANNEL_ACCESS_TOKEN}'
        }
        
        data = {
            "replyToken": reply_token,
            "messages": messages
        }
        
        print("LINE API Request:")
        print(f"  URL: {LINE_REPLY_URL}")
        # Avoid logging secret token
        safe_headers = {**headers, 'Authorization': 'Bearer ***redacted***'}
        print(f"  Headers: {safe_headers}")
        print(f"  Payload: {json.dumps(data, indent=2)}")
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                LINE_REPLY_URL,
                headers=headers,
                json=data
            )
            response.raise_for_status()
            
            print(f"LINE API Response:")
            print(f"  Status Code: {response.status_code}")
            print(f"  Response Headers: {dict(response.headers)}")
            print(f"  Response Body: {response.text}")
            
            return {"success": True, "status": response.status_code}
            
    except Exception as e:
        print(f"Error sending reply: {str(e)}")
        return {"success": False, "error": str(e)}

# FastHTML routes
app, rt = fast_app()

@rt("/")
def index():
    return Titled("OCR Text Extraction",
        Container(
            # Header Section
            Div(
                Div(
                    H1("🔍 OCR Text Extraction", cls="text-center mb-3"),
                    P("Transform your images and PDFs into editable text using advanced AI technology", 
                      cls="text-center text-muted mb-4 lead"),
                    class_="text-center"
                ),
                cls="mb-5"
            ),
            
            # Main Upload Card
            Card(
                Div(
                    H3("📁 Upload Your File", cls="mb-3"),
                    P("Supported formats: JPG, PNG, GIF, BMP, WEBP, PDF", cls="text-muted mb-4"),
                    
                    Form(
                        Div(
                            Label("Choose File", for_="fileInput", cls="form-label fw-bold"),
                            Input(
                                type="file", 
                                name="file", 
                                id="fileInput", 
                                cls="form-control form-control-lg", 
                                accept=".jpg,.jpeg,.png,.gif,.bmp,.webp,.pdf", 
                                required=True
                            ),
                            cls="mb-4"
                        ),
                        Div(
                            Button("🚀 Extract Text", type="submit", cls="btn btn-primary btn-lg w-100"),
                            cls="text-center"
                        ),
                        method="post",
                        action="/upload",
                        enctype="multipart/form-data",
                        cls="needs-validation"
                    ),
                    cls="p-4"
                ),
                cls="shadow-lg border-0 mb-4"
            ),
            
            # Results Section
            Div(
                Div(id="result"),
                cls="mt-4"
            ),
            
            # Features Section
            Div(
                H3("✨ Features", cls="text-center mb-4"),
                Div(
                    Div(
                        Div(
                            H4("🖼️ Image OCR", cls="h5"),
                            P("Extract text from photos, screenshots, and scanned documents"),
                            cls="text-center p-3"
                        ),
                        cls="col-md-4 mb-3"
                    ),
                    Div(
                        Div(
                            H4("📄 PDF Processing", cls="h5"),
                            P("Handle both text-based and image-based PDF files"),
                            cls="text-center p-3"
                        ),
                        cls="col-md-4 mb-3"
                    ),
                    Div(
                        Div(
                            H4("🤖 AI-Powered", cls="h5"),
                            P("Powered by Google Gemini AI for accurate text recognition"),
                            cls="text-center p-3"
                        ),
                        cls="col-md-4 mb-3"
                    ),
                    cls="row"
                ),
                cls="mt-5"
            ),
            
            # Footer
            Div(
                Hr(),
                P("Built with FastHTML and Google Gemini AI", cls="text-center text-muted small"),
                cls="mt-5"
            )
        ),
        # Custom CSS for better styling
        Style("""
            body {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            }
            .container {
                background: rgba(255, 255, 255, 0.95);
                border-radius: 15px;
                box-shadow: 0 20px 40px rgba(0,0,0,0.1);
                margin-top: 2rem;
                margin-bottom: 2rem;
                padding: 2rem;
            }
            .card {
                border-radius: 12px;
                transition: transform 0.3s ease;
            }
            .card:hover {
                transform: translateY(-5px);
            }
            .btn-primary {
                background: linear-gradient(45deg, #667eea, #764ba2);
                border: none;
                border-radius: 8px;
                padding: 12px 30px;
                font-weight: 600;
                transition: all 0.3s ease;
            }
            .btn-primary:hover {
                transform: translateY(-2px);
                box-shadow: 0 10px 20px rgba(102, 126, 234, 0.4);
            }
            .form-control {
                border-radius: 8px;
                border: 2px solid #e9ecef;
                padding: 12px 15px;
                transition: all 0.3s ease;
            }
            .form-control:focus {
                border-color: #667eea;
                box-shadow: 0 0 0 0.2rem rgba(102, 126, 234, 0.25);
            }
            .alert {
                border-radius: 10px;
                border: none;
                box-shadow: 0 5px 15px rgba(0,0,0,0.1);
            }
            .spinner-border {
                width: 3rem;
                height: 3rem;
                border-width: 0.3em;
            }
            .feature-card {
                background: #f8f9fa;
                border-radius: 10px;
                transition: all 0.3s ease;
                border: 1px solid #e9ecef;
            }
            .feature-card:hover {
                background: #e9ecef;
                transform: translateY(-3px);
            }
            h1 {
                background: linear-gradient(45deg, #667eea, #764ba2);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                background-clip: text;
                font-weight: 700;
            }
            .lead {
                font-size: 1.1rem;
                font-weight: 400;
            }
            .result-text {
                background: #f8f9fa;
                border: 1px solid #e9ecef;
                border-radius: 8px;
                padding: 20px;
                max-height: 500px;
                overflow-y: auto;
                font-family: 'Courier New', monospace;
                line-height: 1.6;
                white-space: pre-wrap;
                word-wrap: break-word;
            }
            .file-info {
                background: #e3f2fd;
                border-left: 4px solid #2196f3;
                padding: 15px;
                margin-bottom: 20px;
                border-radius: 0 8px 8px 0;
            }
        """),
        # Enhanced JavaScript
        Script("""
            document.querySelector('form').addEventListener('submit', function(e) {
                e.preventDefault();
                const formData = new FormData(this);
                const resultDiv = document.getElementById('result');
                const fileInput = document.getElementById('fileInput');
                const submitBtn = document.querySelector('button[type="submit"]');
                
                // Show loading state
                submitBtn.disabled = true;
                submitBtn.innerHTML = '⏳ Processing...';
                
                resultDiv.innerHTML = `
                    <div class="text-center">
                        <div class="spinner-border text-primary" role="status">
                            <span class="visually-hidden">Processing...</span>
                        </div>
                        <p class="mt-3 text-muted">Analyzing your file with AI...</p>
                    </div>
                `;
                
                fetch('/upload', {
                    method: 'POST',
                    body: formData
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        const fileName = fileInput.files[0]?.name || 'Unknown file';
                        resultDiv.innerHTML = `
                            <div class="alert alert-success">
                                <div class="file-info">
                                    <h5 class="mb-2">✅ Text Extraction Complete</h5>
                                    <p class="mb-0"><strong>File:</strong> ${fileName}</p>
                                </div>
                                <h5 class="mb-3">📝 Extracted Text:</h5>
                                <div id="ocr-text" class="result-text">${data.text}</div>
                                ${data.calc ? `
                                <h5 class="mt-4 mb-2">📒 Calculation (per rules):</h5>
                                <div id="calc-report" class="result-text">${data.calc.replaceAll('\\n','<br/>')}</div>
                                <div class="mt-2"><strong>Grand Total:</strong> ${data.grand_total}</div>
                                ` : ''}
                                <div class="mt-3">
                                    <button class="btn btn-outline-primary btn-sm" onclick="copyFrom('#ocr-text')">📋 Copy Text</button>
                                    <button class="btn btn-outline-secondary btn-sm ms-2" onclick="downloadFrom('#ocr-text','extracted_text.txt')">💾 Download</button>
                                    ${data.calc ? `
                                    <button class=\"btn btn-outline-primary btn-sm ms-3\" onclick=\"copyFrom('#calc-report')\">📋 Copy Report</button>
                                    <button class=\"btn btn-outline-secondary btn-sm ms-2\" onclick=\"downloadFrom('#calc-report','calculation_report.txt')\">💾 Download Report</button>
                                    ` : ''}
                                </div>
                            </div>
                        `;
                    } else {
                        resultDiv.innerHTML = `
                            <div class="alert alert-danger">
                                <h5>❌ Error</h5>
                                <p>${data.error}</p>
                            </div>
                        `;
                    }
                })
                .catch(error => {
                    resultDiv.innerHTML = `
                        <div class="alert alert-danger">
                            <h5>❌ Error</h5>
                            <p>An error occurred while processing the file. Please try again.</p>
                        </div>
                    `;
                })
                .finally(() => {
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = '🚀 Extract Text';
                });
            });
            
            function copyFrom(selector) {
                const el = document.querySelector(selector);
                if (!el) return;
                const text = el.textContent;
                navigator.clipboard.writeText(text).then(() => {
                    const btn = event.target;
                    const originalText = btn.innerHTML;
                    btn.innerHTML = '✅ Copied!';
                    btn.classList.add('btn-success');
                    btn.classList.remove('btn-outline-primary');
                    setTimeout(() => {
                        btn.innerHTML = originalText;
                        btn.classList.remove('btn-success');
                        btn.classList.add('btn-outline-primary');
                    }, 2000);
                });
            }

            function downloadFrom(selector, filename) {
                const el = document.querySelector(selector);
                if (!el) return;
                const text = el.textContent;
                const blob = new Blob([text], { type: 'text/plain' });
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = filename || 'download.txt';
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                window.URL.revokeObjectURL(url);
            }
        """)
    )

@rt("/upload", methods=["POST"])
async def upload_file(req: Request):
    try:
        # Get the uploaded file
        form = await req.form()
        file = form.get('file')
        if not file:
            return {"success": False, "error": "No file uploaded"}
        
        # Read file data
        file_data = await file.read()
        filename = file.filename
        
        if not filename:
            return {"success": False, "error": "No filename provided"}
        
        # Process the file → OCR text
        extracted_text = process_uploaded_file(file_data, filename)
        
        # If OCR succeeded (string), attempt arithmetic computation
        calc = None
        if isinstance(extracted_text, str) and not extracted_text.startswith("Error"):
            calc = compute_from_text(extracted_text)
        
        return {
            "success": True,
            "text": extracted_text,
            "calc": calc["report"] if calc else None,
            "grand_total": calc["grand_total"] if calc else None
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}

@rt("/webhook", methods=["POST"])
async def webhook(req: Request):
    """Handle LINE webhook POST requests"""
    try:
        # Get the request body
        body = await req.json()
        print(f"Received webhook payload: {json.dumps(body, indent=2)}")
        
        # Extract reply token from the webhook data
        events = body.get('events', [])
        if not events:
            print("No events found in webhook")
            return {"success": False, "error": "No events found in webhook"}
        
        event = events[0]
        reply_token = event.get('replyToken')
        if not reply_token:
            print("No reply token found")
            return {"success": False, "error": "No reply token found"}
        
        print(f"Extracted replyToken: {reply_token}")
        
        # Check if it's a message event
        if event.get('type') != 'message':
            print(f"Event type is not message: {event.get('type')}")
            return {"success": True, "message": "Non-message event ignored"}
        
        message = event.get('message', {})
        message_type = message.get('type')
        print(f"Event type: {event.get('type')}")
        print(f"Message type: {message_type}")
        
        # Handle different message types
        if message_type == 'image':
            print("Processing image message...")
            message_id = message.get('id')
            if not message_id:
                print("No message ID found for image")
                return {"success": False, "error": "No message ID found for image"}
            
            # Download image content
            download_result = await download_line_image_content(message_id)
            if not download_result["success"]:
                print(f"Failed to download image: {download_result['error']}")
                messages = [
                    {
                        "type": "text",
                        "text": "Sorry, I couldn't download the image. Please try again."
                    }
                ]
            else:
                print("Image downloaded successfully, processing with OCR...")
                # Process image with OCR
                image_content = download_result["content"]
                ocr_result = extract_text_from_image(image_content)
                
                print(f"OCR Result: {ocr_result}")
                
                if "Error" in ocr_result:
                    messages = [
                        {
                            "type": "text",
                            "text": f"OCR processing failed: {ocr_result}"
                        }
                    ]
                else:
                    # Attempt arithmetic computation on OCR text
                    calc = compute_from_text(ocr_result)
                    report = calc.get("report", "")
                    # LINE message length limit ~5000 chars; split if large
                    chunks = []
                    if report:
                        # include heading and total
                        full_report = f"Result (OCR)\n{report}"
                        while full_report:
                            chunk = full_report[:4800]
                            chunks.append(chunk)
                            full_report = full_report[4800:]
                    else:
                        chunks.append("No calculable content found. Returning OCR text only.")
                    messages = [
                        {
                            "type": "text",
                            "text": "🔍 Computation based on your image:"
                        },
                    ] + [{"type": "text", "text": c} for c in chunks]
                    ]
        
        elif message_type == 'text':
            print("Processing text message...")
            text_content = message.get('text', '')
            print(f"Text content: {text_content}")
            
            # Try to parse and compute directly if text lines appear to match rules
            calc = compute_from_text(text_content)
            report = calc.get("report", "") if calc else ""
            if report:
                messages = [
                    {"type": "text", "text": "🧮 Computation:"},
                    {"type": "text", "text": report[:4800]}
                ]
            else:
                messages = [
                    {"type": "text", "text": "Send an image or lines to compute."}
                ]
        
        else:
            print(f"Unsupported message type: {message_type}")
            messages = [
                {
                    "type": "text",
                    "text": f"I received a {message_type} message, but I can only process text and images."
                }
            ]
        
        # Send reply message to LINE
        result = await reply_to_line_message(reply_token, messages)
        
        if result["success"]:
            print("Reply sent successfully!")
            return {"success": True, "message": "Reply sent successfully"}
        else:
            print(f"Failed to send reply: {result['error']}")
            return {"success": False, "error": result["error"]}
            
    except Exception as e:
        print(f"Webhook processing error: {str(e)}")
        return {"success": False, "error": f"Webhook processing error: {str(e)}"}

# Run the application
if __name__ == "__main__":
    serve(port=port)
