# OCR + Arithmetic Web Application

A web application that uses Google Gemini AI to extract text from uploaded images and PDF files, and then computes arithmetic totals from the OCR text using strict rules (permutations, group rules, and headline doublers). It also integrates with LINE Messaging API.

## Features

- Upload images (JPG, PNG, GIF, BMP, WEBP) for OCR text extraction
- Upload PDF files for text extraction (direct text + OCR for image-based PDFs)
- Modern web interface with Bootstrap styling
- Computes line-by-line totals from OCR text and shows a detailed report
- Copy and download buttons for both the OCR text and the calculation report
- Docker support with Debian base image

## Quick Test

Try the following text (make it into an image or send as text to the LINE bot):

```
บนล่าง
390 × 50
{761, 619, 639} = 20
293 = 200
123 × 10 = 4
```

The page displays both the extracted text and a step-by-step calculation with section subtotals and the grand total. For top-bottom headlines (e.g., "บนล่าง", "บล"), the app applies both multiplier-doubling (before) for `ABC × Y` lines and result-doubling (after) for all lines, plus the special case for two-digit flat values.

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

### LINE Webhook

Set your LINE Messaging API webhook URL to `https://your-domain/webhook` and ensure your `LINE_CHANNEL_ACCESS_TOKEN` is valid. When users send an image, the server downloads it, runs OCR, applies the arithmetic rules, and replies with the computed results. Long reports are split across multiple messages.

## API Key & Tokens

The application uses a pre-configured Google Gemini API key. You can override via environment variables:

```
export GOOGLE_API_KEY=your_gemini_key
export LINE_CHANNEL_ACCESS_TOKEN=your_line_token
```

For production, always use environment variables and do not hardcode secrets.

## Dependencies

- FastHTML: Web framework
- google-genai: Google Gemini AI integration
- Pillow: Image processing
- PyMuPDF: PDF processing
