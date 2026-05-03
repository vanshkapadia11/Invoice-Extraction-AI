# 📝 Invoice AI Parser

An end-to-end intelligent document processing system that uses a fine-tuned **Donut (Document Understanding Transformer)** model to extract structured data from invoices without traditional OCR.

## ✨ Features

- **OCR-Free Extraction:** Uses a Transformer-based visual encoder and text decoder to "read" document images directly.
- **Structured Data:** Converts unstructured invoice images into clean JSON and stores them in a **SQLite** database.
- **Automated Logging:** Tracks all extraction attempts and errors in a local log file.
- **Scalable Storage:** Setup for Git LFS and external hosting for large model weights.

## 🛠️ Tech Stack

- **Language:** Python 3.x
- **Deep Learning:** Hugging Face Transformers (Donut Model)
- **Database:** SQLite
- **Storage:** Git LFS / Google Drive (for model weights)

## 🚀 Getting Started

### 1. Prerequisites

- Python 3.8+
- [Git LFS](https://git-lfs.com/) installed on your machine.

### 2. Installation

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/invoice-ai-parser.git
cd invoice-ai-parser

# Install dependencies
pip install -r requirements.txt
```

### 3. Model Weights

The fine-tuned model folder (`donut-finetuned/`) is **not** included in this repository due to its large size.

1. Download the model folder from your **Google Drive backup**.
2. Place the `donut-finetuned/` folder in the root directory of this project.

Link : https://drive.google.com/drive/folders/1QT_Op9w2QmXJKWT59KgNxQCAHJi42STf?usp=drive_link

## 📖 Usage

To process an invoice, run:

```bash
python app.py
```

The extracted data will be displayed in the console and saved to `invoice.db`.

## 📁 Project Structure

- `app.py` - Main application entry point.
- `generate_invoice.py` - Script for creating/testing invoice data.
- `invoice.db` - Local database for extracted data (ignored by Git).
- `.env` - Environment variables and secrets (ignored by Git).
