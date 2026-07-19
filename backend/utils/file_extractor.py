import io
import PyPDF2
import docx

# ── Extract text from uploaded file (PDF or Word) ────────────────────────────
def extract_text_from_file(file) -> dict:
    """
    Input  : file object from request.files
    Output : {"success": True,  "text": "..."}
           | {"success": False, "error": "..."}
    """
    try:
        filename = file.filename.lower()

        # ── PDF ──────────────────────────────────────────────────────────────
        if filename.endswith(".pdf"):
            reader = PyPDF2.PdfReader(io.BytesIO(file.read()))
            text   = "\n".join(
                page.extract_text() or "" for page in reader.pages
            ).strip()

            if not text:
                return {"success": False, "error": "PDF appears to be scanned or empty"}

            return {"success": True, "text": text}

        # ── Word (.docx) ──────────────────────────────────────────────────────
        elif filename.endswith(".docx"):
            doc  = docx.Document(io.BytesIO(file.read()))
            text = "\n".join(
                para.text for para in doc.paragraphs if para.text.strip()
            ).strip()

            if not text:
                return {"success": False, "error": "Word document appears to be empty"}

            return {"success": True, "text": text}

        # ── Unsupported ───────────────────────────────────────────────────────
        else:
            return {
                "success": False,
                "error"  : f"Unsupported file type '{filename}'. Only PDF and .docx allowed."
            }

    except Exception as e:
        return {"success": False, "error": f"File extraction failed: {str(e)}"}