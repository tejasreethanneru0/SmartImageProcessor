# Smart Image Processor

A local image editing web application built with Python, Flask, Pillow, HTML, CSS and JavaScript. It does not require AWS or any cloud account.

## Features

- Upload JPG, JPEG, PNG and WEBP images (maximum 15 MB)
- Original and current-result previews
- Resize with optional aspect-ratio preservation
- JPEG compression with quality control
- Crop using pixel coordinates
- Rotate clockwise and flip horizontally/vertically
- Convert between JPG, PNG and WEBP
- Adjust brightness and contrast
- Grayscale, sepia, blur and sharpen filters
- Download processed images
- Processing history stored locally in `history.json`
- Responsive layout

## Requirements

- Python 3.10 or newer
- VS Code (recommended)

## Setup on Windows PowerShell

Open the project folder in VS Code, then open its terminal.

```powershell
python -m venv venv
```

Activate the environment:

```powershell
.\venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, run this in the same terminal:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Then activate again.

Install dependencies:

```powershell
pip install -r requirements.txt
```

Start the application:

```powershell
python app.py
```

Open this address in your browser:

```text
http://127.0.0.1:5000
```

Press `Ctrl+C` in the terminal to stop the server.

## Project structure

```text
SmartImageProcessor/
│
├── app.py
├── requirements.txt
├── README.md
├── history.json          # created when processing history is saved
├── uploads/              # created automatically
├── processed/            # created automatically
│
├── templates/
│   └── index.html
│
└── static/
    ├── css/
    │   └── styles.css
    └── js/
        └── script.js
```

## Important notes

- Each edit is applied to the current result, so operations can be chained.
- Use **Reset to original** to return the current preview to the original upload.
- Reset does not delete earlier processed files or history.
- Files are stored on your own computer in `uploads/` and `processed/`.
- This is a local learning project. Before deploying it publicly, add authentication, CSRF protection, per-user storage, rate limiting, cleanup policies and production server configuration.
- The development server is intended for local use only.
