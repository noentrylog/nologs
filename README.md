# OCR Web Application

A web application that uses Google Gemini AI to extract text from uploaded images and PDF files.

## Features

- Upload images (JPG, PNG, GIF, BMP, WEBP) for OCR text extraction
- Upload PDF files for text extraction (direct text + OCR for image-based PDFs)
- Modern web interface with Bootstrap styling
- Docker support with Debian base image

## Running the Application

### Using Docker (Recommended)

1. Build the Docker image:
```bash
docker build -t ocr-app .
```

2. Run the container:
```bash
docker run -p 5001:5001 ocr-app
```

### Running Locally

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the application:
```bash
python app.py
```

The application will be available at `http://localhost:5001`

## API Key

The application uses a pre-configured Google Gemini API key. For production use, consider using environment variables for the API key.

## Dependencies

- FastHTML: Web framework
- google-genai: Google Gemini AI integration
- Pillow: Image processing
- PyMuPDF: PDF processing
