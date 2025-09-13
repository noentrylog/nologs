from fasthtml.common import *
from google import genai
import base64
import io
from PIL import Image
import fitz  # PyMuPDF for PDF handling
import os
from starlette.requests import Request

# Set the port to 5001 as specified in the FastHTML documentation
port = 5001

# Initialize Gemini API
api_key = "AIzaSyB-ssyREcxmGX8KnV9JbxfEZLh6xhXC7-k"
os.environ["GOOGLE_API_KEY"] = api_key

# Initialize the Gemini client
client = genai.Client(api_key=api_key)

def extract_text_from_image(image_data):
    """Extract text from image using Gemini Vision API"""
    try:
        # Create the prompt for OCR
        prompt = "Extract all text from this image. Return only the text content, no additional formatting or explanations."
        
        # Use Gemini to extract text
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=[prompt, image_data]
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
                
                # Use Gemini for OCR
                ocr_text = extract_text_from_image(img_data)
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
    return Html(
        Head(
            Title("OCR Web Application"),
            Meta(charset="utf-8"),
            Meta(name="viewport", content="width=device-width, initial-scale=1"),
            Link(rel="stylesheet", href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css")
        ),
        Body(
            Div(
                Div(
                    H1("OCR Text Extraction", class_="text-center mb-4"),
                    P("Upload an image or PDF file to extract text using Google Gemini AI", class_="text-center text-muted mb-4"),
                    class_="container"
                ),
                Div(
                    Form(
                        Div(
                            Input(type="file", name="file", id="fileInput", class_="form-control", accept=".jpg,.jpeg,.png,.gif,.bmp,.webp,.pdf", required=True),
                            class_="mb-3"
                        ),
                        Div(
                            Button("Extract Text", type="submit", class_="btn btn-primary btn-lg"),
                            class_="text-center"
                        ),
                        method="post",
                        action="/upload",
                        enctype="multipart/form-data"
                    ),
                    class_="container"
                ),
                Div(
                    Div(id="result", class_="mt-4"),
                    class_="container"
                ),
                Script(src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"),
                Script("""
                    document.querySelector('form').addEventListener('submit', function(e) {
                        e.preventDefault();
                        const formData = new FormData(this);
                        const resultDiv = document.getElementById('result');
                        
                        resultDiv.innerHTML = '<div class="text-center"><div class="spinner-border" role="status"><span class="visually-hidden">Processing...</span></div><p class="mt-2">Processing your file...</p></div>';
                        
                        fetch('/upload', {
                            method: 'POST',
                            body: formData
                        })
                        .then(response => response.json())
                        .then(data => {
                            if (data.success) {
                                resultDiv.innerHTML = `
                                    <div class="alert alert-success">
                                        <h5>Extracted Text:</h5>
                                        <div class="bg-light p-3 rounded" style="max-height: 400px; overflow-y: auto;">
                                            <pre style="white-space: pre-wrap; font-family: inherit;">${data.text}</pre>
                                        </div>
                                    </div>
                                `;
                            } else {
                                resultDiv.innerHTML = `
                                    <div class="alert alert-danger">
                                        <h5>Error:</h5>
                                        <p>${data.error}</p>
                                    </div>
                                `;
                            }
                        })
                        .catch(error => {
                            resultDiv.innerHTML = `
                                <div class="alert alert-danger">
                                    <h5>Error:</h5>
                                    <p>An error occurred while processing the file.</p>
                                </div>
                            `;
                        });
                    });
                """)
            )
        )
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
