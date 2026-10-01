from ai import analyze_resume
from flask import Flask, render_template, request, redirect, session
from db import Base, engine, SessionLocal
import models
import PyPDF2
import docx
import json
import secrets
import models                          # ← must come first
from db import Base, SessionLocal, engine



app = Flask(__name__)

app.secret_key = "CHANGE_THIS_TO_A_LONG_RANDOM_SECRET_KEY"


Base.metadata.create_all(bind=engine)


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():

    db = SessionLocal()

    try:
        user_exists = db.query(models.User).first()

        if user_exists:
            return redirect("/login_page.html")
        else:
            return redirect("/Sign_in_page.html")

    finally:
        db.close()


# =========================================================
# SIGN UP
# =========================================================
@app.route("/Sign_in_page.html", methods=["GET", "POST"])
def signup():

    db = SessionLocal()

    try:

        if request.method == "POST":

            name = request.form.get("name")
            email = request.form.get("email")
            password = request.form.get("password")

            if not name or not email or not password:
                return render_template(
                    "Sign_in_page.html",
                    error="All fields are required."
                )

            existing_user = (
                db.query(models.User)
                .filter_by(email=email)
                .first()
            )

            if existing_user:
                return render_template(
                    "Sign_in_page.html",
                    error="This email is already registered. Please login."
                )

            user = models.User(
                name=name,
                email=email,
                password=password
            )

            db.add(user)
            db.commit()

            return redirect("/login_page.html")

        return render_template("Sign_in_page.html")

    finally:
        db.close()


# =========================================================
# LOGIN
# =========================================================

@app.route("/login_page.html", methods=["GET", "POST"])
def login():

    db = SessionLocal()

    try:

        if request.method == "POST":

            email = request.form.get("email")
            password = request.form.get("password")

            user = (
                db.query(models.User)
                .filter_by(
                    email=email,
                    password=password
                )
                .first()
            )

            if user:

                session["User"] = user.email

                return redirect("/Dashboard.html")

            return render_template(
                "login_page.html",
                error="Invalid email or password."
            )

        return render_template("login_page.html")

    finally:
        db.close()

@app.route("/Dashboard.html", methods=["GET", "POST"])
def dashboard():
    if "User" not in session:
        return redirect("/login_page.html")

    result = None

    if request.method == "POST":
        user_goal = request.form.get("role")
        resume_text = request.form.get("resume")
        file = request.files.get("file")

        if file and file.filename != "":
            if file.filename.lower().endswith(".pdf"):
                try:
                    import PyPDF2
                    pdf_reader = PyPDF2.PdfReader(file)
                    text = ""
                    for page in pdf_reader.pages:
                        text += page.extract_text() or ""
                    resume_text = text
                except Exception as e:
                    result = {"error": f"PDF error: {str(e)}"}

            elif file.filename.lower().endswith(".docx"):
                try:
                    import docx
                    document = docx.Document(file)
                    text = ""
                    for paragraph in document.paragraphs:
                        text += paragraph.text + "\n"
                    resume_text = text
                except Exception as e:
                    result = {"error": f"DOCX error: {str(e)}"}
            else:
                result = {"error": "Only PDF and DOCX files are supported."}

        if result is None:
            if not resume_text or not resume_text.strip():
                result = {"error": "Please paste your resume or upload a PDF/DOCX file."}
            elif not user_goal or not user_goal.strip():
                result = {"error": "Please enter the job role you want to become."}
            else:
                # Send resume to Gemini
                result = analyze_resume(resume_text, user_goal)

                # Save to History ONLY if there is no error   ← THIS LINE MATTERS
                if not result.get("error"):
                    pass
                    #save_report(session["User"], resume_text, user_goal, result)
        # =================================================
        # VALIDATION
        # =================================================

        if result is None:

            if not resume_text or not resume_text.strip():

                result = {
                    "error": "Please paste your resume or upload a PDF/DOCX file."
                }

            elif not user_goal or not user_goal.strip():

                result = {
                    "error": "Please enter the job role you want to become."
                }

            else:

                # =================================================
                # SEND RESUME TO GEMINI
                # =================================================

                result = analyze_resume(
                    resume_text,
                    user_goal
                )

    return render_template(
        "Dashboard.html",
        result=result,
        user=session["User"]
    )



# =========================================================
# HISTORY
# =========================================================

@app.route("/History")
def history():

    if "User" not in session:
        return redirect("/login_page.html")

    db = SessionLocal()

    try:

        user = (
            db.query(models.User)
            .filter_by(email=session["User"])
            .first()
        )

        if not user:
            session.pop("User", None)
            return redirect("/login_page.html")

        reports = (
            db.query(models.Reports)
            .filter_by(user_id=user.id)
            .order_by(models.Reports.id.desc())
            .all()
        )

        # Convert JSON string stored in result column
        # into a Python dictionary for the template.

        for report in reports:

            if report.result:

                try:
                    report.result_data = json.loads(report.result)

                except json.JSONDecodeError:
                    report.result_data = {}

            else:

                report.result_data = {}

        return render_template(
            "History.html",
            reports=reports
        )

    finally:
        db.close()


# =========================================================
# FORGOT PASSWORD
# =========================================================

@app.route(
    "/Forgot_Password.html",
    methods=["GET", "POST"]
)
def forgot_password():

    if request.method == "POST":

        email = request.form.get("email")

        db = SessionLocal()

        try:

            user = (
                db.query(models.User)
                .filter_by(email=email)
                .first()
            )

            if not user:
                return "No account found with this email."

        finally:
            db.close()

        # Generate 6-digit OTP

        otp = str(secrets.randbelow(900000) + 100000)

        session["reset_email"] = email
        session["reset_otp"] = otp

        # Temporary testing
        print("OTP:", otp)

        return redirect("/verify_otp.html")

    return render_template("Forgot_password.html")


# =========================================================
# VERIFY OTP
# =========================================================

@app.route(
    "/verify_otp.html",
    methods=["GET", "POST"]
)
def verify_otp():

    if "reset_email" not in session:
        return redirect("/Forgot_Password.html")

    if request.method == "POST":

        entered_otp = request.form.get("otp")

        saved_otp = session.get("reset_otp")

        if entered_otp == saved_otp:

            session["otp_verified"] = True

            return redirect("/Reset_password.html")

        return "Invalid OTP"

    return render_template("verify_otp.html")


# =========================================================
# RESET PASSWORD
# =========================================================

@app.route(
    "/Reset_password.html",
    methods=["GET", "POST"]
)
def reset_password():

    if not session.get("otp_verified"):
        return redirect("/Forgot_Password.html")

    if request.method == "POST":

        password = request.form.get("password")
        confirm_password = request.form.get(
            "confirm_password"
        )

        if not password or not confirm_password:
            return "Both password fields are required."

        if password != confirm_password:
            return "Passwords do not match."

        email = session.get("reset_email")

        db = SessionLocal()

        try:

            user = (
                db.query(models.User)
                .filter_by(email=email)
                .first()
            )

            if not user:
                return "User not found."

            user.password = password

            db.commit()

        finally:
            db.close()

        # Clear password reset session data

        session.pop("reset_email", None)
        session.pop("reset_otp", None)
        session.pop("otp_verified", None)

        return redirect("/login_page.html")

    return render_template("Reset_password.html")


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.pop("User", None)

    return redirect("/login_page.html")
# =========================================================
# Dashboard
# =========================================================



    return render_template(
        "Dashboard.html",
        result=result,
        user=session["User"],
    )





# =========================================================
# RUN APPLICATION
# =========================================================

if __name__ == "__main__":
    app.run(debug=True)