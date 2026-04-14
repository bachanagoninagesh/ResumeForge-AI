# Resume Tailor - Professional ATS PDF Generator

This project takes your base resume plus one or more job links and creates tailored one-page PDF resumes in a consistent ATS-safe format.

## What changed in this version
- Matches the uploaded sample resume format much more closely.
- Keeps the same section order for every generated resume.
- Preserves project / initiative subheadings inside experience when supported.
- Uses a tighter one-page PDF renderer with consistent formatting.
- Keeps email failures from crashing the whole run.

## Input files
Put these in `data/input/`:
- `Resume.doc`, `resume.docx`, `resume.pdf`, or another supported resume file
- `job_links.txt`
- `profile.json`

## .env
Create `.env` from `.env.example` and fill at least:

```env
ANTHROPIC_API_KEY=your_key_here
ANTHROPIC_MODEL=claude-sonnet-4-6
REQUEST_TIMEOUT_SECONDS=25
```

Optional email delivery:

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_email@gmail.com
SMTP_PASSWORD=your_gmail_app_password
SMTP_USE_STARTTLS=true
EMAIL_FROM=your_email@gmail.com
DEFAULT_EMAIL_TO=your_email@gmail.com
```

## Run
```powershell
python .\main.py
```

Or:
```powershell
python -m src.main
```

## Output
Generated PDFs are saved in `data/output/`.

## Supported resume formats
- `.pdf`
- `.docx`
- `.doc`
- `.txt`
- `.md`
- `.rtf`
