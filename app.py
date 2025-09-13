from fasthtml.common import *
from google import genai
import base64
import io
from PIL import Image
import fitz  # PyMuPDF for PDF handling
import os
from starlette.requests import Request
from starlette.datastructures import UploadFile

# Set the port to 5001 as specified in the FastHTML documentation
port = 5001

# Initialize Gemini API
api_key = "AIzaSyDK-0QygkeObRJJI83zllIJo8Ca3J4Vwm4"
os.environ["GOOGLE_API_KEY"] = api_key

# Initialize the Gemini client
client = genai.Client(api_key=api_key)

def extract_text_from_image(image_data):
    """Extract text from image using Gemini Vision API"""
    try:
        # Create the prompt for OCR
        prompt = "Extract all text from this image. Return only the text content, no additional formatting or explanations."
        
        # Convert image data to base64 for proper API format
        if isinstance(image_data, bytes):
            image_base64 = base64.b64encode(image_data).decode('utf-8')
        else:
            image_base64 = image_data
        
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
                                "mime_type": "image/jpeg",
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
                
                # Use Gemini for OCR
                ocr_text = extract_text_from_image(img_base64)
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
                                <div class="result-text">${data.text}</div>
                                <div class="mt-3">
                                    <button class="btn btn-outline-primary btn-sm" onclick="copyToClipboard()">
                                        📋 Copy Text
                                    </button>
                                    <button class="btn btn-outline-secondary btn-sm ms-2" onclick="downloadText()">
                                        💾 Download
                                    </button>
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
            
            function copyToClipboard() {
                const text = document.querySelector('.result-text').textContent;
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
            
            function downloadText() {
                const text = document.querySelector('.result-text').textContent;
                const blob = new Blob([text], { type: 'text/plain' });
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'extracted_text.txt';
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
        
        # Process the file
        extracted_text = process_uploaded_file(file_data, filename)
        
        return {"success": True, "text": extracted_text}
        
    except Exception as e:
        return {"success": False, "error": str(e)}

# Run the application
if __name__ == "__main__":
    serve(port=port)
