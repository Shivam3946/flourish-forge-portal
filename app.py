import os
import json
import random
import smtplib
import urllib.request
from email.message import EmailMessage
from datetime import datetime, date, timedelta
from functools import wraps
from flask import Flask, render_template, redirect, url_for, request, flash, abort, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from models import (
    db, User, PasswordOTP, Attendance, TestScore,
    StudyMaterial, DoubtTicket, QuestionBank, Notice,
    OnlineExam, ExamMCQ, ExamAttempt
)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'flourish-forge-du-cs-secret-2026')
uri = os.environ.get('DATABASE_URL', 'sqlite:///flourish_forge.db')
if uri.startswith('postgres://'):
    uri = uri.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads')
app.config['FACULTY_FOLDER'] = os.path.join(app.root_path, 'static', 'faculty')

# Optional LLM / ChatGPT API config (set OPENAI_API_KEY in Render Environment if desired)
app.config['OPENAI_API_KEY'] = os.environ.get('OPENAI_API_KEY', '').strip()
app.config['OPENAI_MODEL'] = os.environ.get('OPENAI_MODEL', 'gpt-4o-mini').strip()

# Email SMTP configuration (set via Render Environment Variables)
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', '587'))
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', '')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', '')
app.config['MAIL_FROM'] = os.environ.get('MAIL_FROM') or os.environ.get('MAIL_USERNAME') or 'noreply@flourishforge.in'

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['FACULTY_FOLDER'], exist_ok=True)

CLASSES_7_TO_12 = ['Class 7', 'Class 8', 'Class 9', 'Class 10', 'Class 11', 'Class 12']
NCERT_OFFICIAL_LINKS = [
    {"class_name": "Class 8", "title": "NCERT Official Textbooks — Class 8", "url": "https://ncert.nic.in/textbook.php?hesc1=0-13"},
    {"class_name": "Class 9", "title": "NCERT Official Textbooks — Class 9", "url": "https://ncert.nic.in/textbook.php?iesc1=0-12"},
    {"class_name": "Class 10", "title": "NCERT Official Textbooks — Class 10", "url": "https://ncert.nic.in/textbook.php?jesc1=0-13"},
    {"class_name": "All Classes", "title": "NCERT Official E-Book Portal (All Classes)", "url": "https://ncert.nic.in/textbook.php"},
]

ALLOWED_EXTENSIONS = {
    'pdf', 'doc', 'docx', 'txt', 'ppt', 'pptx',
    'png', 'jpg', 'jpeg', 'gif', 'webp'
}
IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_image(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in IMAGE_EXTENSIONS

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def call_chatgpt_api(prompt_text):
    api_key = app.config['OPENAI_API_KEY']
    if not api_key:
        return None
    try:
        payload = json.dumps({
            "model": app.config['OPENAI_MODEL'],
            "messages": [
                {"role": "system", "content": "You are a CBSE academic question and test generator for Flourish Forge."},
                {"role": "user", "content": prompt_text}
            ],
            "temperature": 0.4
        }).encode("utf-8")
        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]
    except Exception:
        return None

def build_auto_mcq(target_class, subject, chapter, idx, difficulty='Medium'):
    prompt = (
        f"Create 1 CBSE {target_class} {subject} MCQ on chapter '{chapter}' ({difficulty}). "
        'Reply ONLY as JSON: {"q":"...","a":"...","b":"...","c":"...","d":"...","ans":"A"}'
    )
    llm_out = call_chatgpt_api(prompt)
    if llm_out:
        try:
            start = llm_out.find("{")
            end = llm_out.rfind("}") + 1
            if start != -1 and end > start:
                obj = json.loads(llm_out[start:end])
                ans_let = str(obj.get("ans", "A")).strip().upper()[:1]
                if ans_let not in ("A", "B", "C", "D"):
                    ans_let = "A"
                opt_map = {
                    "A": obj.get("a", "Option A"),
                    "B": obj.get("b", "Option B"),
                    "C": obj.get("c", "Option C"),
                    "D": obj.get("d", "Option D")
                }
                return QuestionBank(
                    target_class=target_class, subject=subject, chapter=chapter,
                    question_type='MCQ', difficulty=difficulty, marks=1,
                    question_text=f"[{chapter}] {obj.get('q', f'Auto MCQ #{idx} on {chapter}')}",
                    option_a=str(obj.get("a", "Option A")),
                    option_b=str(obj.get("b", "Option B")),
                    option_c=str(obj.get("c", "Option C")),
                    option_d=str(obj.get("d", "Option D")),
                    answer_key=f"({ans_let}) {opt_map[ans_let]}"
                )
        except Exception:
            pass

    templates_mcq = [
        (f"In the chapter '{chapter}' ({subject}, {target_class}), which statement is core to CBSE concepts? (Set {idx})",
         "Fundamental rule holds under standard conditions", "Exception applies in all cases without condition",
         "Unrelated to syllabus unit", "Always zero regardless of input", "A", "Fundamental rule holds under standard conditions"),
        (f"Which key concept from '{chapter}' is frequently tested in {target_class} {subject} assessments? (Set {idx})",
         "Direct formula / definition application", "Ignoring units and signs",
         "Random guessing without steps", "None of the above", "A", "Direct formula / definition application"),
        (f"For '{chapter}' in {target_class} {subject}, what should be checked first before solving a problem? (Set {idx})",
         "Given values, units, and syllabus conditions", "Skipping problem statement",
         "Using wrong chapter formula", "Rounding before calculation", "A", "Given values, units, and syllabus conditions"),
        (f"Which approach best helps score full marks on '{chapter}' questions in {target_class} {subject}? (Set {idx})",
         "Clear step-by-step reasoning and final answer", "Writing only an unverified number",
         "Omitting key terms", "Leaving steps incomplete", "A", "Clear step-by-step reasoning and final answer"),
    ]
    qt, oa, ob, oc, od, corr, ans_txt = templates_mcq[(idx - 1) % len(templates_mcq)]
    return QuestionBank(
        target_class=target_class, subject=subject, chapter=chapter,
        question_type='MCQ', difficulty=difficulty, marks=1,
        question_text=qt, option_a=oa, option_b=ob, option_c=oc, option_d=od,
        answer_key=f"({corr}) {ans_txt}"
    )

def build_auto_subjective(target_class, subject, chapter, idx, difficulty='Medium'):
    marks_map = {'Easy': 2, 'Medium': 3, 'HOTS': 5}
    m = marks_map.get(difficulty, 3)
    llm_out = call_chatgpt_api(
        f"Write 1 CBSE {target_class} {subject} {difficulty} subjective question ({m} marks) on chapter '{chapter}', "
        f"followed by 'ANSWER: ...' on a new line."
    )
    if llm_out and "ANSWER:" in llm_out:
        parts = llm_out.split("ANSWER:", 1)
        q_part = parts[0].strip()
        a_part = parts[1].strip()
        if q_part:
            return QuestionBank(
                target_class=target_class, subject=subject, chapter=chapter,
                question_type='Subjective', difficulty=difficulty, marks=m,
                question_text=f"[{chapter} - {difficulty}] {q_part}",
                answer_key=a_part
            )

    if difficulty == 'Easy':
        qt = f"[{chapter}] State two key definitions/properties from '{chapter}' in {target_class} {subject} with a simple example. (Q{idx})"
        ak = f"State accurate NCERT definition/property for '{chapter}' and provide one valid example."
    elif difficulty == 'Medium':
        qt = f"[{chapter}] Explain the main concept/method in '{chapter}' ({target_class} {subject}) step-by-step with an illustrative case. (Q{idx})"
        ak = f"Write structured steps, formula/principle from '{chapter}', and final verified result."
    else:
        qt = f"[{chapter} - HOTS] Analyse a higher-order application problem based on '{chapter}' in {target_class} {subject} and justify your steps. (Q{idx})"
        ak = f"Identify core condition in '{chapter}', apply logical/analytical steps, and conclude clearly."

    return QuestionBank(
        target_class=target_class, subject=subject, chapter=chapter,
        question_type='Subjective', difficulty=difficulty, marks=m,
        question_text=qt, answer_key=ak
    )

def pick_exact_questions(pool, requested_count, maker_fn):
    if requested_count <= 0:
        return []
    pool_copy = list(pool)
    random.shuffle(pool_copy)
    selected = pool_copy[:requested_count]
    auto_idx = 1
    while len(selected) < requested_count:
        selected.append(maker_fn(auto_idx))
        auto_idx += 1
    return selected[:requested_count]

def send_otp_email(to_email, otp_code):
    mail_user = app.config['MAIL_USERNAME']
    mail_pass = app.config['MAIL_PASSWORD']
    if not mail_user or not mail_pass:
        return False, "SMTP credentials not configured in environment variables."
    try:
        msg = EmailMessage()
        msg['Subject'] = 'Flourish Forge Portal — Password Reset OTP'
        msg['From'] = app.config['MAIL_FROM']
        msg['To'] = to_email
        msg.set_content(
            f"Hello,\n\n"
            f"Your One-Time Password (OTP) to reset your Flourish Forge Portal password is: {otp_code}\n"
            f"This OTP is valid for 10 minutes.\n\n"
            f"Regards,\nFlourish Forge (Director: Shivam Tiwari)"
        )
        with smtplib.SMTP(app.config['MAIL_SERVER'], app.config['MAIL_PORT'], timeout=15) as server:
            server.starttls()
            server.login(mail_user, mail_pass)
            server.send_message(msg)
        return True, "OTP sent to your registered email address."
    except Exception as e:
        return False, f"Email delivery failed: {str(e)}"

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated or current_user.role not in roles:
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator

with app.app_context():
    db.create_all()
    admin_email = os.environ.get('ADMIN_EMAIL', 'director@flourishforge.in').strip().lower()
    admin_password = os.environ.get('ADMIN_PASSWORD', 'flourishforge123')
    admin = User.query.filter_by(role='admin').first()
    if not admin:
        admin = User(name='Shivam Tiwari', email=admin_email, role='admin')
        admin.set_password(admin_password)
        db.session.add(admin)

    if QuestionBank.query.count() == 0:
        seed_qs = [
            QuestionBank(target_class='Class 10', subject='Mathematics', chapter='Quadratic Equations',
                         question_type='MCQ', difficulty='Easy', marks=1,
                         question_text='If 1/2 is a root of x^2 + kx - 5/4 = 0, then k equals:',
                         option_a='2', option_b='-2', option_c='1/4', option_d='1/2', answer_key='(A) 2'),
            QuestionBank(target_class='Class 10', subject='Mathematics', chapter='Polynomials',
                         question_type='MCQ', difficulty='Easy', marks=1,
                         question_text='The zeroes of x^2 + 99x + 127 are:',
                         option_a='Both positive', option_b='Both negative', option_c='One positive, one negative', option_d='Equal',
                         answer_key='(B) Both negative'),
            QuestionBank(target_class='Class 10', subject='Mathematics', chapter='Arithmetic Progressions',
                         question_type='MCQ', difficulty='Easy', marks=1,
                         question_text='10th term of AP: 5, 8, 11, 14, ... is:',
                         option_a='32', option_b='35', option_c='29', option_d='38',
                         answer_key='(A) 32'),
            QuestionBank(target_class='Class 10', subject='Mathematics', chapter='Real Numbers',
                         question_type='Subjective', difficulty='Medium', marks=3,
                         question_text='[CBSE PYQ] Prove that sqrt(2) is an irrational number.',
                         answer_key='Proof by contradiction assuming sqrt(2) = p/q in lowest terms.'),
            QuestionBank(target_class='Class 10', subject='Science', chapter='Chemical Reactions and Equations',
                         question_type='Subjective', difficulty='Easy', marks=2,
                         question_text='[CBSE PYQ] Why should a magnesium ribbon be cleaned before burning in air?',
                         answer_key='To remove surface oxide/carbonate layer so combustion proceeds cleanly.'),
            QuestionBank(target_class='Class 9', subject='Mathematics', chapter='Number Systems',
                         question_type='MCQ', difficulty='Easy', marks=1,
                         question_text='[PYQ] Express 0.666... in p/q form:',
                         option_a='6/10', option_b='2/3', option_c='1/3', option_d='6/99',
                         answer_key='(B) 2/3'),
            QuestionBank(target_class='Class 9', subject='Science', chapter='Matter in Our Surroundings',
                         question_type='MCQ', difficulty='Easy', marks=1,
                         question_text='[PYQ] Convert 300 K into Celsius scale:',
                         option_a='27 deg C', option_b='573 deg C', option_c='273 deg C', option_d='30 deg C',
                         answer_key='(A) 27 deg C'),
            QuestionBank(target_class='Class 8', subject='Mathematics', chapter='Linear Equations in One Variable',
                         question_type='Subjective', difficulty='Easy', marks=2,
                         question_text='[PYQ] Solve: (2x - 3) / (3x + 2) = -2/3.',
                         answer_key='x = 5/12'),
            QuestionBank(target_class='Class 8', subject='Science', chapter='Force and Pressure',
                         question_type='MCQ', difficulty='Easy', marks=1,
                         question_text='[PYQ] Pressure is defined as:',
                         option_a='Force x Area', option_b='Force / Area', option_c='Area / Force', option_d='Mass / Volume',
                         answer_key='(B) Force / Area'),
        ]
        db.session.add_all(seed_qs)

    if OnlineExam.query.count() == 0:
        demo_exam = OnlineExam(
            title='Class 10 Maths — Quick Practice Quiz (5 MCQs)',
            target_class='Class 10',
            subject='Mathematics',
            chapter='Quadratic Equations & AP',
            created_by='Flourish Forge'
        )
        db.session.add(demo_exam)
        db.session.flush()
        demo_mcqs = [
            ExamMCQ(exam_id=demo_exam.id, question_text='Discriminant D of ax^2 + bx + c = 0 is:',
                    option_a='b^2 - 4ac', option_b='b^2 + 4ac', option_c='4ac - b^2', option_d='2ab', correct_option='A', marks=1),
            ExamMCQ(exam_id=demo_exam.id, question_text='If D = 0 for a quadratic equation, roots are:',
                    option_a='Real and equal', option_b='Distinct real', option_c='No real roots', option_d='Imaginary', correct_option='A', marks=1),
            ExamMCQ(exam_id=demo_exam.id, question_text='Common difference of AP 2, 7, 12, 17, ... is:',
                    option_a='3', option_b='5', option_c='7', option_d='2', correct_option='B', marks=1),
            ExamMCQ(exam_id=demo_exam.id, question_text='Sum of first n natural numbers is:',
                    option_a='n(n+1)/2', option_b='n(n-1)/2', option_c='n^2', option_d='2n', correct_option='A', marks=1),
            ExamMCQ(exam_id=demo_exam.id, question_text='Roots of x^2 - 9 = 0 are:',
                    option_a='+3 and -3', option_b='9 and -9', option_c='0 and 9', option_d='1 and 9', correct_option='A', marks=1),
        ]
        db.session.add_all(demo_mcqs)

    db.session.commit()

@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for(f"{current_user.role}_dashboard"))
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for(f"{user.role}_dashboard"))
        flash('Invalid Email or Password. Please try again.', 'danger')
    return render_template('login.html')

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        action = request.form.get('action', 'send_otp')
        email = request.form.get('email', '').strip().lower()
        user = User.query.filter_by(email=email).first()

        if action == 'send_otp':
            if not user:
                flash('No account found with that email address.', 'warning')
                return render_template('forgot_password.html', email=email, otp_sent=False)

            otp_code = f"{random.randint(100000, 999999)}"
            otp_entry = PasswordOTP(
                email=email,
                otp_code=otp_code,
                expires_at=datetime.utcnow() + timedelta(minutes=10),
                used=False
            )
            db.session.add(otp_entry)
            db.session.commit()
            session['reset_email'] = email

            sent, status_msg = send_otp_email(email, otp_code)
            if sent:
                flash('A 6-digit OTP has been sent to your email. Valid for 10 minutes.', 'success')
            else:
                flash(
                    f"OTP generated for {email} (SMTP not configured yet: {status_msg}). "
                    f"Dev/Test OTP: {otp_code}",
                    'info'
                )
            return render_template('forgot_password.html', email=email, otp_sent=True)

        elif action == 'reset_password':
            otp_input = request.form.get('otp_code', '').strip()
            new_password = request.form.get('new_password', '')
            confirm_password = request.form.get('confirm_password', '')

            if not user:
                flash('Invalid email account.', 'danger')
                return render_template('forgot_password.html', email=email, otp_sent=True)

            if len(new_password) < 6:
                flash('New password must be at least 6 characters long.', 'warning')
                return render_template('forgot_password.html', email=email, otp_sent=True)

            if new_password != confirm_password:
                flash('New password and confirm password do not match.', 'warning')
                return render_template('forgot_password.html', email=email, otp_sent=True)

            otp_rec = PasswordOTP.query.filter_by(
                email=email, otp_code=otp_input, used=False
            ).order_by(PasswordOTP.id.desc()).first()

            if not otp_rec or not otp_rec.is_valid():
                flash('Invalid or expired OTP. Please request a new OTP.', 'danger')
                return render_template('forgot_password.html', email=email, otp_sent=True)

            otp_rec.used = True
            user.set_password(new_password)
            db.session.commit()
            session.pop('reset_email', None)
            flash('Password updated successfully! You can now sign in with your new password.', 'success')
            return redirect(url_for('login'))

    saved_email = session.get('reset_email', '')
    return render_template('forgot_password.html', email=saved_email, otp_sent=bool(saved_email))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# ---------------- ADMIN ROUTES ----------------
@app.route('/admin')
@login_required
@role_required('admin')
def admin_dashboard():
    teachers = User.query.filter_by(role='teacher').all()
    students = User.query.filter_by(role='student').all()
    notices = Notice.query.order_by(Notice.created_at.desc()).all()
    return render_template(
        'admin_dashboard.html',
        classes=CLASSES_7_TO_12,
        teachers=teachers,
        students=students,
        notices=notices,
        ncert_links=NCERT_OFFICIAL_LINKS
    )

@app.route('/admin/add_user', methods=['POST'])
@login_required
@role_required('admin')
def add_user():
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip().lower()
    password = request.form.get('password', '')
    role = request.form.get('role')
    student_class = request.form.get('student_class') if role == 'student' else None
    batch_timing = request.form.get('batch_timing') if role == 'student' else None
    subject_specialty = request.form.get('subject_specialty') if role == 'teacher' else None

    if User.query.filter_by(email=email).first():
        flash('Email already registered!', 'warning')
    else:
        new_user = User(
            name=name, email=email, role=role,
            student_class=student_class, batch_timing=batch_timing,
            subject_specialty=subject_specialty
        )
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        flash(f'{role.capitalize()} account created for {name}.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/reset_password', methods=['POST'])
@login_required
@role_required('admin')
def reset_password():
