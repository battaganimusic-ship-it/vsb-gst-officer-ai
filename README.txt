VSB GST Officer AI Website v0.4

Branding
- VSB monogram only
- GST Officer AI
- No personal name shown
- No Government logo

Current working modules
- Registration
- Username/email + password login
- Password hashing
- User-isolated cases
- Scrutiny case creation
- GSTIN + tax-period details
- Dynamic document checklist
- ZIP/PDF/XLS/XLSX/CSV/JSON/DOCX/TXT uploads
- Mandatory reason capture where a selected document is not uploaded
- Local SQLite for testing
- PostgreSQL-ready production database
- Docker + Gunicorn deployment files

Local Windows
1. Extract ZIP fully.
2. Run SETUP_LOCAL_WINDOWS.bat
3. Run START_LOCAL_WINDOWS.bat
4. Open http://127.0.0.1:8000

Production deployment
- Render: connect this folder/repository and use render.yaml
- VPS/Docker: docker build -t vsb-gst-ai . then docker run -p 8000:8000 vsb-gst-ai
- Set SECRET_KEY and DATABASE_URL in environment variables.
- Add OPENAI_API_KEY later when AI verification is connected.

Important
This is the deployable website foundation. The next engineering stage is the GST data mapper and autonomous verification engine.
