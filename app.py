
import os, uuid, zipfile, json
from pathlib import Path
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_sqlalchemy import SQLAlchemy

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

INSTANCE_DIR = BASE_DIR / "instance"
INSTANCE_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "change-me-in-production")

database_url = os.getenv("DATABASE_URL")
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = database_url or f"sqlite:///{INSTANCE_DIR/'gst_ai.db'}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024 * 1024  # 1 GB per request

db = SQLAlchemy(app)

ALLOWED_EXTENSIONS = {"zip","pdf","xlsx","xls","csv","json","docx","txt"}

DOCUMENTS = [
    ("gstr1", "GSTR-1 / GSTR-1A", "Monthly outward-supply data / JSON / Excel / ZIP"),
    ("gstr3b", "GSTR-3B", "Monthly summary returns / PDF / JSON / ZIP"),
    ("gstr2a", "GSTR-2A", "Month-wise inward-supply statement"),
    ("gstr2b", "GSTR-2B", "Month-wise static ITC statement"),
    ("gstr9", "GSTR-9", "Annual return, where applicable"),
    ("gstr9c", "GSTR-9C", "Annual reconciliation statement, where applicable"),
    ("table8a", "GSTR-9 Table 8A", "Document-wise annual ITC data, where applicable"),
    ("purchase", "Purchase Register", "Invoice-wise inward supplies"),
    ("sales", "Sales Register", "Invoice-wise outward supplies"),
    ("trial", "Trial Balance / General Ledger", "Relevant tax-period accounts"),
    ("financials", "Audited Financial Statements", "P&L, Balance Sheet, notes and schedules"),
    ("income_tax", "Income-tax / Tax Audit", "ITR turnover / Form 3CD / tax audit data"),
    ("bank", "Bank Statements", "All relevant bank accounts"),
    ("tds", "GST TDS / TCS", "GSTR-7 / GSTR-8 / related statements"),
    ("eway", "E-Way Bill Data", "Outward and inward detailed EWB data / ZIP"),
    ("fixed_assets", "Fixed Asset Register", "Capital goods and asset additions"),
    ("insurance", "Insurance Ledgers", "Motor / stock / fire / health / other policies"),
    ("telecom", "Internet / Telecom", "Common services expenditure"),
    ("vehicle", "Vehicle / Travel / Hotel", "Vehicles, accommodation, restaurant and travel"),
    ("rcm", "RCM Expense Ledgers", "Legal, GTA, director, security, imports and other notified expenses"),
    ("agreements", "Agreements / Other Evidence", "Contracts, invoices, reconciliations, submissions"),
]

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(200), unique=True, nullable=False)
    mobile = db.Column(db.String(30))
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(300), nullable=False)
    role = db.Column(db.String(50), default="Officer")

class Case(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    case_code = db.Column(db.String(50), unique=True, nullable=False)
    gstin = db.Column(db.String(20), nullable=False)
    legal_name = db.Column(db.String(200), nullable=False)
    period_from = db.Column(db.String(20), nullable=False)
    period_to = db.Column(db.String(20), nullable=False)
    turnover = db.Column(db.Float)
    status = db.Column(db.String(50), default="Documents Pending")

class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, nullable=False)
    doc_key = db.Column(db.String(80), nullable=False)
    doc_label = db.Column(db.String(200), nullable=False)
    filename = db.Column(db.String(500))
    missing_reason = db.Column(db.Text)

with app.app_context():
    db.create_all()

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Please login to continue.", "warning")
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

def allowed_file(filename):
    return "." in filename and filename.rsplit(".",1)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/")
def landing():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return render_template("landing.html")

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        full_name = request.form.get("full_name","").strip()
        email = request.form.get("email","").strip().lower()
        mobile = request.form.get("mobile","").strip()
        username = request.form.get("username","").strip()
        password = request.form.get("password","")
        confirm = request.form.get("confirm_password","")

        if not all([full_name,email,username,password,confirm]):
            flash("Please fill all required fields.", "danger")
            return render_template("register.html")
        if password != confirm:
            flash("Passwords do not match.", "danger")
            return render_template("register.html")
        if len(password) < 8:
            flash("Password must be at least 8 characters.", "danger")
            return render_template("register.html")
        if User.query.filter((User.username==username) | (User.email==email)).first():
            flash("Username or email already registered.", "danger")
            return render_template("register.html")

        user = User(
            full_name=full_name,
            email=email,
            mobile=mobile,
            username=username,
            password_hash=generate_password_hash(password),
        )
        db.session.add(user)
        db.session.commit()
        flash("Registration successful. Please login.", "success")
        return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        identifier = request.form.get("identifier","").strip()
        password = request.form.get("password","")
        user = User.query.filter((User.username==identifier) | (User.email==identifier.lower())).first()
        if user and check_password_hash(user.password_hash, password):
            session.clear()
            session["user_id"] = user.id
            session["full_name"] = user.full_name
            return redirect(url_for("dashboard"))
        flash("Invalid username/email or password.", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/dashboard")
@login_required
def dashboard():
    cases = Case.query.filter_by(user_id=session["user_id"]).order_by(Case.id.desc()).all()
    return render_template("dashboard.html", cases=cases)

@app.route("/new-case", methods=["GET","POST"])
@login_required
def new_case():
    if request.method == "POST":
        case = Case(
            user_id=session["user_id"],
            case_code="SCR-" + str(uuid.uuid4())[:8].upper(),
            gstin=request.form["gstin"].strip().upper(),
            legal_name=request.form["legal_name"].strip(),
            period_from=request.form["period_from"],
            period_to=request.form["period_to"],
            turnover=float(request.form["turnover"]) if request.form.get("turnover") else None,
        )
        db.session.add(case)
        db.session.commit()
        return redirect(url_for("upload_documents", case_id=case.id))
    return render_template("new_case.html")

@app.route("/case/<int:case_id>/upload", methods=["GET","POST"])
@login_required
def upload_documents(case_id):
    case = Case.query.filter_by(id=case_id, user_id=session["user_id"]).first_or_404()

    if request.method == "POST":
        Document.query.filter_by(case_id=case.id).delete()
        case_dir = UPLOAD_DIR / str(session["user_id"]) / case.case_code
        case_dir.mkdir(parents=True, exist_ok=True)

        for key,label,desc in DOCUMENTS:
            f = request.files.get(key)
            reason = request.form.get(f"{key}_reason","").strip()
            checked = request.form.get(f"{key}_checked") == "on"
            filename = None

            if f and f.filename:
                if not allowed_file(f.filename):
                    flash(f"Unsupported file type for {label}.", "danger")
                    return redirect(url_for("upload_documents", case_id=case.id))
                filename = secure_filename(f.filename)
                target = case_dir / filename
                f.save(target)

                if filename.lower().endswith(".zip"):
                    extract_dir = case_dir / (Path(filename).stem + "_extracted")
                    extract_dir.mkdir(exist_ok=True)
                    try:
                        with zipfile.ZipFile(target,"r") as z:
                            z.extractall(extract_dir)
                    except zipfile.BadZipFile:
                        flash(f"{filename} is not a valid ZIP file.", "danger")

            elif checked and not reason:
                flash(f"Reason required for {label} if marked available but not uploaded.", "danger")
                return redirect(url_for("upload_documents", case_id=case.id))

            db.session.add(Document(
                case_id=case.id,
                doc_key=key,
                doc_label=label,
                filename=filename,
                missing_reason=reason
            ))

        case.status = "Ready for Analysis"
        db.session.commit()
        flash("Documents saved successfully.", "success")
        return redirect(url_for("case_summary", case_id=case.id))

    return render_template("upload.html", case=case, documents=DOCUMENTS)

@app.route("/case/<int:case_id>")
@login_required
def case_summary(case_id):
    case = Case.query.filter_by(id=case_id, user_id=session["user_id"]).first_or_404()
    docs = Document.query.filter_by(case_id=case.id).all()
    return render_template("case_summary.html", case=case, docs=docs)
@app.route("/case/<int:case_id>/analysis")
@login_required
def analysis(case_id):
    case = Case.query.filter_by(
        id=case_id,
        user_id=session["user_id"]
    ).first_or_404()

    docs = Document.query.filter_by(case_id=case.id).all()

    return render_template(
        "analysis.html",
        case=case,
        docs=docs
    )
@app.route("/health")
def health():
    return jsonify({"status":"ok","product":"VSB GST Officer AI"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT","8000")), debug=os.getenv("FLASK_DEBUG")=="1")
