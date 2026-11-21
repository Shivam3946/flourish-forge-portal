import os
import random
import smtplib
from email.message import EmailMessage
from datetime import datetime, date, timedelta
from functools import wraps
from flask import Flask, render_template, redirect, url_for, request, flash, abort, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from models import (
    db, User, PasswordOTP, Attendance, TestScore,
    FeeRecord, StudyMaterial, DoubtTicket, QuestionBank, Notice
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

# Email SMTP configuration (set via Render Environment Variables)
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', '587'))
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', '')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', '')
app.config['MAIL_FROM'] = os.environ.get('MAIL_FROM') or os.environ.get('MAIL_USERNAME') or 'noreply@flourishforge.in'

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['FACULTY_FOLDER'], exist_ok=True)

CLASSES_7_TO_12 = ['Class 7', 'Class 8', 'Class 9', 'Class 10', 'Class 11', 'Class 12']
ALLOWED_EXTENSIONS = {
    'pdf', 'doc', 'docx', 'txt', 'ppt', 'pptx',
    'png', 'jpg', 'jpeg', 'gif', 'webp'
}
IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_image(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in IMAGE_EXTENSIONS

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

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
        admin = User(
            name='Shivam Tiwari',
            email=admin_email,
            role='admin'
        )
        admin.set_password(admin_password)
        db.session.add(admin)

    if QuestionBank.query.count() == 0:
        sample_qs = [
            QuestionBank(target_class='Class 10', subject='Mathematics', chapter='Quadratic Equations',
                         question_type='MCQ', difficulty='Easy', marks=1,
                         question_text='If 1/2 is a root of the equation x^2 + kx - 5/4 = 0, then the value of k is:',
                         option_a='2', option_b='-2', option_c='1/4', option_d='1/2', answer_key='(A) 2'),
            QuestionBank(target_class='Class 10', subject='Mathematics', chapter='Quadratic Equations',
                         question_type='MCQ', difficulty='Easy', marks=1,
                         question_text='Which of the following is a quadratic equation?',
                         option_a='x^2 + 2x + 1 = (4 - x)^2 + 3', option_b='-2x^2 = (5 - x)(2x - 2/5)',
                         option_c='(k + 1)x^2 + (3/2)x = 7, where k = -1', option_d='x^3 - x^2 = (x - 1)^3',
                         answer_key='(D) x^3 - x^2 = (x - 1)^3'),
            QuestionBank(target_class='Class 10', subject='Mathematics', chapter='Polynomials',
                         question_type='MCQ', difficulty='Easy', marks=1,
                         question_text='The zeroes of the quadratic polynomial x^2 + 99x + 127 are:',
                         option_a='Both positive', option_b='Both negative',
                         option_c='One positive and one negative', option_d='Both equal',
                         answer_key='(B) Both negative'),
            QuestionBank(target_class='Class 10', subject='Mathematics', chapter='Pair of Linear Equations',
                         question_type='MCQ', difficulty='Medium', marks=1,
                         question_text='If the lines given by 3x + 2ky = 2 and 2x + 5y + 1 = 0 are parallel, then value of k is:',
                         option_a='-5/4', option_b='2/5', option_c='15/4', option_d='3/2',
                         answer_key='(C) 15/4'),
            QuestionBank(target_class='Class 10', subject='Mathematics', chapter='Arithmetic Progressions',
                         question_type='MCQ', difficulty='Easy', marks=1,
                         question_text='The 10th term of the AP: 5, 8, 11, 14, ... is:',
                         option_a='32', option_b='35', option_c='29', option_d='38',
                         answer_key='(A) 32'),
            QuestionBank(target_class='Class 10', subject='Mathematics', chapter='Triangles',
                         question_type='MCQ', difficulty='Easy', marks=1,
                         question_text='In triangle ABC, DE || BC. If AD = 1.5 cm, BD = 3 cm, AE = 1 cm, then EC is:',
                         option_a='1 cm', option_b='2 cm', option_c='3 cm', option_d='1.5 cm',
                         answer_key='(B) 2 cm'),
            QuestionBank(target_class='Class 10', subject='Mathematics', chapter='Coordinate Geometry',
                         question_type='MCQ', difficulty='Easy', marks=1,
                         question_text='The distance of the point P(-6, 8) from the origin is:',
                         option_a='8', option_b='2*sqrt(7)', option_c='10', option_d='6',
                         answer_key='(C) 10'),
            QuestionBank(target_class='Class 10', subject='Mathematics', chapter='Trigonometry',
                         question_type='MCQ', difficulty='Easy', marks=1,
                         question_text='If sin A = 3/5, then cos A is equal to:',
                         option_a='4/5', option_b='5/4', option_c='3/4', option_d='5/3',
                         answer_key='(A) 4/5'),
            QuestionBank(target_class='Class 10', subject='Mathematics', chapter='Circles',
                         question_type='MCQ', difficulty='Medium', marks=1,
                         question_text='From a point Q, the length of the tangent to a circle is 24 cm and distance of Q from centre is 25 cm. Radius is:',
                         option_a='7 cm', option_b='12 cm', option_c='15 cm', option_d='24.5 cm',
                         answer_key='(A) 7 cm'),
            QuestionBank(target_class='Class 10', subject='Mathematics', chapter='Surface Areas and Volumes',
                         question_type='MCQ', difficulty='Medium', marks=1,
                         question_text='If two cubes each of volume 64 cm^3 are joined end to end, surface area of resulting cuboid is:',
                         option_a='160 cm^2', option_b='192 cm^2', option_c='256 cm^2', option_d='128 cm^2',
                         answer_key='(A) 160 cm^2'),
            QuestionBank(target_class='Class 10', subject='Mathematics', chapter='Quadratic Equations',
                         question_type='Subjective', difficulty='Easy', marks=2,
                         question_text='Find the roots of the quadratic equation 2x^2 - 5x + 3 = 0 by factorisation.',
                         answer_key='x = 1, x = 3/2'),
            QuestionBank(target_class='Class 10', subject='Mathematics', chapter='Quadratic Equations',
                         question_type='Subjective', difficulty='Medium', marks=3,
                         question_text='Find the value of k for which the quadratic equation kx(x - 2) + 6 = 0 has two equal real roots.',
                         answer_key='k = 6'),
            QuestionBank(target_class='Class 10', subject='Mathematics', chapter='Trigonometry',
                         question_type='Subjective', difficulty='HOTS', marks=4,
                         question_text='Prove that (sin A + cosec A)^2 + (cos A + sec A)^2 = 7 + tan^2 A + cot^2 A.',
                         answer_key='LHS = sin^2 A + cosec^2 A + 2 + cos^2 A + sec^2 A + 2 = 5 + (1+cot^2 A) + (1+tan^2 A) = RHS'),
        ]
        db.session.add_all(sample_qs)

    if QuestionBank.query.count() <= 13:
        extra_qs = [
            # CLASS 10 PYQs & IMPORTANT QUESTIONS (Maths & Science)
            QuestionBank(target_class='Class 10', subject='Mathematics', chapter='Real Numbers [PYQ 2012-2025]',
                         question_type='Subjective', difficulty='Medium', marks=3,
                         question_text='[CBSE PYQ] Prove that sqrt(2) is an irrational number.',
                         answer_key='Proof by contradiction: assume sqrt(2) = p/q coprime, 2q^2 = p^2 => contradiction.'),
            QuestionBank(target_class='Class 10', subject='Mathematics', chapter='Real Numbers [Important]',
                         question_type='MCQ', difficulty='Easy', marks=1,
                         question_text='[Important] The HCF and LCM of two numbers are 9 and 360. If one number is 45, the other number is:',
                         option_a='72', option_b='81', option_c='90', option_d='108',
                         answer_key='(A) 72'),
            QuestionBank(target_class='Class 10', subject='Mathematics', chapter='Polynomials [PYQ 2014-2024]',
                         question_type='Subjective', difficulty='Medium', marks=2,
                         question_text='[CBSE PYQ] Find a quadratic polynomial whose zeroes are 5 + sqrt(2) and 5 - sqrt(2).',
                         answer_key='x^2 - 10x + 23'),
            QuestionBank(target_class='Class 10', subject='Mathematics', chapter='Arithmetic Progressions [PYQ 2011-2025]',
                         question_type='Subjective', difficulty='Medium', marks=3,
                         question_text='[CBSE PYQ] How many two-digit numbers are divisible by 3?',
                         answer_key='30 (AP: 12, 15, ..., 99; a=12, d=3, a_n=99 => n=30)'),
            QuestionBank(target_class='Class 10', subject='Mathematics', chapter='Coordinate Geometry [PYQ 2013-2025]',
                         question_type='Subjective', difficulty='Medium', marks=3,
                         question_text='[CBSE PYQ] Find the ratio in which the line segment joining A(1, -5) and B(-4, 5) is divided by the x-axis.',
                         answer_key='1 : 1'),
            QuestionBank(target_class='Class 10', subject='Mathematics', chapter='Circles [PYQ 2015-2025]',
                         question_type='Subjective', difficulty='HOTS', marks=4,
                         question_text='[CBSE PYQ] Prove that the lengths of tangents drawn from an external point to a circle are equal.',
                         answer_key='Using RHS congruence on right triangles OPA and OPB, PA = PB.'),
            QuestionBank(target_class='Class 10', subject='Science', chapter='Chemical Reactions and Equations [PYQ 2012-2025]',
                         question_type='Subjective', difficulty='Easy', marks=2,
                         question_text='[CBSE PYQ] Why should a magnesium ribbon be cleaned before burning in air?',
                         answer_key='To remove the protective layer of basic magnesium carbonate/oxide so magnesium burns smoothly.'),
            QuestionBank(target_class='Class 10', subject='Science', chapter='Acids, Bases and Salts [PYQ 2014-2024]',
                         question_type='MCQ', difficulty='Easy', marks=1,
                         question_text='[CBSE PYQ] Which of the following is used for disinfecting drinking water?',
                         option_a='Baking soda', option_b='Washing soda', option_c='Bleaching powder', option_d='Gypsum',
                         answer_key='(C) Bleaching powder'),
            QuestionBank(target_class='Class 10', subject='Science', chapter='Carbon and its Compounds [PYQ 2013-2025]',
                         question_type='Subjective', difficulty='HOTS', marks=4,
                         question_text='[CBSE PYQ] What is homologous series? Explain with an example of alkanes and state two characteristics.',
                         answer_key='Series of compounds with same functional group differing by -CH2- (14u); e.g. CH4, C2H6, C3H8.'),
            QuestionBank(target_class='Class 10', subject='Science', chapter='Life Processes [PYQ 2015-2025]',
                         question_type='Subjective', difficulty='Medium', marks=3,
                         question_text='[CBSE PYQ] Differentiate between aerobic and anaerobic respiration with one example each.',
                         answer_key='Aerobic: uses O2, complete breakdown, high ATP (mitochondria); Anaerobic: no O2, lactic acid/ethanol.'),
            QuestionBank(target_class='Class 10', subject='Science', chapter='Magnetic Effects of Electric Current [PYQ 2012-2025]',
                         question_type='MCQ', difficulty='Medium', marks=1,
                         question_text='[CBSE PYQ] The device used for producing electric current is called a:',
                         option_a='Ammeter', option_b='Galvanometer', option_c='Electric generator', option_d='Motor',
                         answer_key='(C) Electric generator'),

            # CLASS 9 PYQs & IMPORTANT QUESTIONS
            QuestionBank(target_class='Class 9', subject='Mathematics', chapter='Number Systems [PYQ / Important]',
                         question_type='Subjective', difficulty='Medium', marks=2,
                         question_text='[PYQ / Important] Rationalise the denominator of 1 / (sqrt(7) - sqrt(6)).',
                         answer_key='sqrt(7) + sqrt(6)'),
            QuestionBank(target_class='Class 9', subject='Mathematics', chapter='Number Systems [Important]',
                         question_type='MCQ', difficulty='Easy', marks=1,
                         question_text='[Important] Express 0.666... (0.6 bar) in the p/q form:',
                         option_a='6/10', option_b='2/3', option_c='1/3', option_d='6/99',
                         answer_key='(B) 2/3'),
            QuestionBank(target_class='Class 9', subject='Mathematics', chapter='Polynomials [PYQ / Important]',
                         question_type='Subjective', difficulty='Medium', marks=3,
                         question_text='[PYQ / Important] Factorise: 27x^3 + y^3 + z^3 - 9xyz using algebraic identities.',
                         answer_key='(3x + y + z)(9x^2 + y^2 + z^2 - 3xy - yz - 3xz)'),
            QuestionBank(target_class='Class 9', subject='Mathematics', chapter='Lines and Angles [PYQ / Important]',
                         question_type='Subjective', difficulty='HOTS', marks=4,
                         question_text='[PYQ / Important] Prove that the sum of the three angles of a triangle is 180 degrees.',
                         answer_key='Draw line parallel to base through opposite vertex; alternate interior angles sum to 180 deg.'),
            QuestionBank(target_class='Class 9', subject='Science', chapter='Matter in Our Surroundings [PYQ / Important]',
                         question_type='MCQ', difficulty='Easy', marks=1,
                         question_text='[PYQ / Important] Convert 300 K into Celsius scale:',
                         option_a='27 deg C', option_b='573 deg C', option_c='273 deg C', option_d='30 deg C',
                         answer_key='(A) 27 deg C (300 - 273 = 27)'),
            QuestionBank(target_class='Class 9', subject='Science', chapter='Force and Laws of Motion [PYQ / Important]',
                         question_type='Subjective', difficulty='Medium', marks=3,
                         question_text="[PYQ / Important] State Newton's second law of motion and derive F = ma.",
                         answer_key='Rate of change of momentum is proportional to applied force in direction of force; F = k*m*a => F = ma.'),
            QuestionBank(target_class='Class 9', subject='Science', chapter='The Fundamental Unit of Life [Important]',
                         question_type='Subjective', difficulty='Easy', marks=2,
                         question_text='[Important] Why is the mitochondria known as the powerhouse of the cell?',
                         answer_key='Generates ATP (energy currency of the cell) through cellular respiration.'),

            # CLASS 8 PYQs & IMPORTANT QUESTIONS
            QuestionBank(target_class='Class 8', subject='Mathematics', chapter='Linear Equations in One Variable [PYQ / Important]',
                         question_type='Subjective', difficulty='Easy', marks=2,
                         question_text='[PYQ / Important] Solve: (2x - 3) / (3x + 2) = -2/3.',
                         answer_key='6x - 9 = -6x - 4 => 12x = 5 => x = 5/12'),
            QuestionBank(target_class='Class 8', subject='Mathematics', chapter='Squares and Square Roots [PYQ / Important]',
                         question_type='MCQ', difficulty='Easy', marks=1,
                         question_text='[PYQ / Important] What is the ones digit of the square of 272?',
                         option_a='2', option_b='4', option_c='6', option_d='8',
                         answer_key='(B) 4 (2^2 = 4)'),
            QuestionBank(target_class='Class 8', subject='Mathematics', chapter='Mensuration [Important]',
                         question_type='Subjective', difficulty='Medium', marks=3,
                         question_text='[Important] Find the total surface area of a cylinder of radius 7 cm and height 10 cm.',
                         answer_key='TSA = 2*pi*r*(r + h) = 2*(22/7)*7*(7 + 10) = 44 * 17 = 748 cm^2'),
            QuestionBank(target_class='Class 8', subject='Science', chapter='Force and Pressure [PYQ / Important]',
                         question_type='MCQ', difficulty='Easy', marks=1,
                         question_text='[PYQ / Important] Pressure is defined as:',
                         option_a='Force x Area', option_b='Force / Area', option_c='Area / Force', option_d='Mass / Volume',
                         answer_key='(B) Force / Area'),
            QuestionBank(target_class='Class 8', subject='Science', chapter='Chemical Effects of Electric Current [PYQ / Important]',
                         question_type='Subjective', difficulty='Medium', marks=2,
                         question_text='[PYQ / Important] What is electroplating? Give one practical use.',
                         answer_key='Deposition of a desired metal layer on another material using electricity; e.g., chromium on taps/cycle parts.'),
        ]
        for eq in extra_qs:
            exists = QuestionBank.query.filter_by(
                target_class=eq.target_class,
                subject=eq.subject,
                question_text=eq.question_text
            ).first()
            if not exists:
                db.session.add(eq)

    latest_ncert_seed = [
        StudyMaterial(title='Latest CBSE NCERT — Class 10 Mathematics (Rationalised Syllabus)', target_class='Class 10',
                      subject='Mathematics', filename='NCERT_Latest_Class_10_Mathematics.txt', uploaded_by='Flourish Forge'),
        StudyMaterial(title='Latest CBSE NCERT — Class 10 Science (Rationalised Syllabus)', target_class='Class 10',
                      subject='Science', filename='NCERT_Latest_Class_10_Science.txt', uploaded_by='Flourish Forge'),
        StudyMaterial(title='Latest CBSE NCERT — Class 9 Mathematics (Rationalised Syllabus)', target_class='Class 9',
                      subject='Mathematics', filename='NCERT_Latest_Class_9_Mathematics.txt', uploaded_by='Flourish Forge'),
        StudyMaterial(title='Latest CBSE NCERT — Class 9 Science (Rationalised Syllabus)', target_class='Class 9',
                      subject='Science', filename='NCERT_Latest_Class_9_Science.txt', uploaded_by='Flourish Forge'),
        StudyMaterial(title='Latest CBSE NCERT — Class 8 Mathematics (Latest CBSE Syllabus)', target_class='Class 8',
                      subject='Mathematics', filename='NCERT_Latest_Class_8_Mathematics.txt', uploaded_by='Flourish Forge'),
        StudyMaterial(title='Latest CBSE NCERT — Class 8 Science (Latest CBSE Syllabus)', target_class='Class 8',
                      subject='Science', filename='NCERT_Latest_Class_8_Science_Curiosity.txt', uploaded_by='Flourish Forge'),
    ]
    for item in latest_ncert_seed:
        if not StudyMaterial.query.filter_by(filename=item.filename).first():
            db.session.add(item)
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

# ---------------- ADMIN (DIRECTOR) ROUTES ----------------
@app.route('/admin')
@login_required
@role_required('admin')
def admin_dashboard():
    teachers = User.query.filter_by(role='teacher').all()
    students = User.query.filter_by(role='student').all()
    fees = FeeRecord.query.order_by(FeeRecord.id.desc()).all()
    notices = Notice.query.order_by(Notice.created_at.desc()).all()
    total_collected = sum(f.amount for f in fees if f.status == 'Paid')
    total_pending = sum(f.amount for f in fees if f.status == 'Pending')
    return render_template(
        'admin_dashboard.html',
        classes=CLASSES_7_TO_12,
        teachers=teachers,
        students=students,
        fees=fees,
        notices=notices,
        total_collected=total_collected,
        total_pending=total_pending
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
            name=name,
            email=email,
            role=role,
            student_class=student_class,
            batch_timing=batch_timing,
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
    user_id = int(request.form.get('user_id'))
    new_pass = request.form.get('new_password')
    user = User.query.get_or_404(user_id)
    user.set_password(new_pass)
    db.session.commit()
    flash(f'Password reset successfully for {user.name}.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/add_notice', methods=['POST'])
@login_required
@role_required('admin')
def add_notice():
    notice = Notice(
        title=request.form.get('title'),
        message=request.form.get('message'),
        target_class=request.form.get('target_class', 'All Classes')
    )
    db.session.add(notice)
    db.session.commit()
    flash('Announcement published to portal!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/add_fee', methods=['POST'])
@login_required
@role_required('admin')
def add_fee():
    next_num = FeeRecord.query.count() + 101
    receipt_no = f"FF-{datetime.utcnow().strftime('%Y%m')}-{next_num}"
    fee = FeeRecord(
        receipt_no=receipt_no,
        student_id=int(request.form.get('student_id')),
        month=request.form.get('month'),
        amount=int(request.form.get('amount')),
        payment_mode=request.form.get('payment_mode', 'UPI'),
        status=request.form.get('status')
    )
    db.session.add(fee)
    db.session.commit()
    flash(f'Monthly fee recorded (Receipt: {receipt_no}).', 'success')
    return redirect(url_for('fee_receipt', fee_id=fee.id))

@app.route('/admin/receipt/<int:fee_id>')
@login_required
@role_required('admin')
def fee_receipt(fee_id):
    fee = FeeRecord.query.get_or_404(fee_id)
    return render_template('fee_receipt.html', fee=fee)

# ---------------- TEACHER ROUTES ----------------
@app.route('/teacher')
@login_required
@role_required('teacher', 'admin')
def teacher_dashboard():
    students = User.query.filter_by(role='student').all()
    faculty_list = User.query.filter(User.role.in_(['teacher', 'admin'])).order_by(
        User.experience_years.desc().nullslast(), User.id.asc()
    ).all()
    materials = StudyMaterial.query.order_by(StudyMaterial.uploaded_at.desc()).all()
    doubts = DoubtTicket.query.order_by(DoubtTicket.created_at.desc()).all()

    filter_cls = request.args.get('filter_class', '')
    filter_sub = request.args.get('filter_subject', '').strip()
    q_query = QuestionBank.query
    if filter_cls:
        q_query = q_query.filter_by(target_class=filter_cls)
    if filter_sub:
        q_query = q_query.filter(QuestionBank.subject.ilike(f"%{filter_sub}%"))
    questions = q_query.order_by(QuestionBank.id.desc()).all()

    flagged_students = []
    for s in students:
        recent = Attendance.query.filter_by(student_id=s.id).order_by(Attendance.att_date.desc()).limit(2).all()
        if len(recent) >= 2 and all(r.status == 'Absent' for r in recent):
            flagged_students.append(s)

    return render_template(
        'teacher_dashboard.html',
        classes=CLASSES_7_TO_12,
        students=students,
        materials=materials,
        doubts=doubts,
        questions=questions,
        filter_cls=filter_cls,
        filter_sub=filter_sub,
        flagged_students=flagged_students,
        faculty_list=faculty_list,
        today_str=date.today().isoformat()
    )

@app.route('/teacher/update_profile', methods=['POST'])
@login_required
@role_required('teacher', 'admin')
def update_teacher_profile():
    name = request.form.get('name', '').strip()
    subject_specialty = request.form.get('subject_specialty', '').strip()
    qualification = request.form.get('qualification', '').strip()
    exp_raw = request.form.get('experience_years', '').strip()
    bio = request.form.get('bio', '').strip()

    if name:
        current_user.name = name
    if subject_specialty:
        current_user.subject_specialty = subject_specialty
    if qualification:
        current_user.qualification = qualification
    if exp_raw != '':
        try:
            current_user.experience_years = max(0, int(exp_raw))
        except ValueError:
            pass
    if bio:
        current_user.bio = bio

    photo = request.files.get('profile_photo')
    if photo and photo.filename:
        if not allowed_image(photo.filename):
            flash('Please upload a valid photo (PNG, JPG, JPEG, GIF, WEBP).', 'warning')
            return redirect(url_for('teacher_dashboard'))
        safe_photo = secure_filename(photo.filename)
        unique_photo = f"faculty_{current_user.id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{safe_photo}"
        photo.save(os.path.join(app.config['FACULTY_FOLDER'], unique_photo))
        current_user.profile_photo = unique_photo

    db.session.commit()
    flash('Faculty profile, education, experience & photo updated on dashboard!', 'success')
    return redirect(url_for('teacher_dashboard'))

@app.route('/teacher/mark_attendance', methods=['POST'])
@login_required
@role_required('teacher', 'admin')
def mark_attendance():
    att_date_str = request.form.get('att_date') or date.today().isoformat()
    att_date_obj = datetime.strptime(att_date_str, '%Y-%m-%d').date()
    students = User.query.filter_by(role='student').all()
    count = 0
    for s in students:
        status = request.form.get(f'status_{s.id}')
        if status in ('Present', 'Absent'):
            existing = Attendance.query.filter_by(student_id=s.id, att_date=att_date_obj).first()
            if existing:
                existing.status = status
                existing.marked_by = current_user.name
            else:
                db.session.add(Attendance(
                    student_id=s.id,
                    att_date=att_date_obj,
                    status=status,
                    marked_by=current_user.name
                ))
            count += 1
    db.session.commit()
    flash(f'Attendance saved for {count} students on {att_date_str}.', 'success')
    return redirect(url_for('teacher_dashboard'))

@app.route('/teacher/add_score', methods=['POST'])
@login_required
@role_required('teacher', 'admin')
def add_score():
    marks_obtained = float(request.form.get('marks_obtained'))
    max_marks = float(request.form.get('max_marks'))
    score = TestScore(
        student_id=int(request.form.get('student_id')),
        subject=request.form.get('subject'),
        chapter=request.form.get('chapter'),
        marks_obtained=marks_obtained,
        max_marks=max_marks,
        remarks=request.form.get('remarks')
    )
    db.session.add(score)
    db.session.commit()
    pct = (marks_obtained / max_marks) * 100 if max_marks > 0 else 0
    if pct < 50:
        flash(f'Score published ({pct:.1f}%). Low score alert (<50%) flagged for remedial follow-up!', 'warning')
    else:
        flash('Test marks published!', 'success')
    return redirect(url_for('teacher_dashboard'))

@app.route('/teacher/upload_material', methods=['POST'])
@login_required
@role_required('teacher', 'admin')
def upload_material():
    file = request.files.get('file')
    if file and file.filename:
        if not allowed_file(file.filename):
            flash('Unsupported file type. Allowed: PDF, DOC/DOCX, PPT/PPTX, TXT, PNG, JPG, JPEG, WEBP.', 'warning')
            return redirect(url_for('teacher_dashboard'))
        safe_name = secure_filename(file.filename)
        unique_name = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{safe_name}"
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_name))
        mat = StudyMaterial(
            title=request.form.get('title'),
            target_class=request.form.get('target_class'),
            subject=request.form.get('subject'),
            filename=unique_name,
            uploaded_by=current_user.name
        )
        db.session.add(mat)
        db.session.commit()
        flash('Study material / photo uploaded successfully!', 'success')
    else:
        flash('Please select a file or photo to upload.', 'warning')
    return redirect(url_for('teacher_dashboard'))

@app.route('/teacher/resolve_doubt/<int:doubt_id>', methods=['POST'])
@login_required
@role_required('teacher', 'admin')
def resolve_doubt(doubt_id):
    doubt = DoubtTicket.query.get_or_404(doubt_id)
    doubt.answer = request.form.get('answer')
    doubt.status = 'Resolved'
    db.session.commit()
    flash('Doubt resolved and sent to student!', 'success')
    return redirect(url_for('teacher_dashboard'))

@app.route('/teacher/add_question', methods=['POST'])
@login_required
@role_required('teacher', 'admin')
def add_question():
    q_type = request.form.get('question_type', 'Subjective')
    q = QuestionBank(
        target_class=request.form.get('target_class'),
        subject=request.form.get('subject', '').strip(),
        chapter=request.form.get('chapter', '').strip(),
        question_type=q_type,
        difficulty=request.form.get('difficulty'),
        marks=int(request.form.get('marks', 1 if q_type == 'MCQ' else 2)),
        question_text=request.form.get('question_text'),
        option_a=request.form.get('option_a') if q_type == 'MCQ' else None,
        option_b=request.form.get('option_b') if q_type == 'MCQ' else None,
        option_c=request.form.get('option_c') if q_type == 'MCQ' else None,
        option_d=request.form.get('option_d') if q_type == 'MCQ' else None,
        answer_key=request.form.get('answer_key')
    )
    db.session.add(q)
    db.session.commit()
    flash(f'{q_type} question added to Flourish Forge Question Bank!', 'success')
    return redirect(url_for('teacher_dashboard'))

@app.route('/teacher/edit_question/<int:q_id>', methods=['GET', 'POST'])
@login_required
@role_required('teacher', 'admin')
def edit_question(q_id):
    q = QuestionBank.query.get_or_404(q_id)
    if request.method == 'POST':
        q.target_class = request.form.get('target_class')
        q.subject = request.form.get('subject', '').strip()
        q.chapter = request.form.get('chapter', '').strip()
        q.question_type = request.form.get('question_type', 'Subjective')
        q.difficulty = request.form.get('difficulty')
        q.marks = int(request.form.get('marks', 1))
        q.question_text = request.form.get('question_text')
        if q.question_type == 'MCQ':
            q.option_a = request.form.get('option_a')
            q.option_b = request.form.get('option_b')
            q.option_c = request.form.get('option_c')
            q.option_d = request.form.get('option_d')
        else:
            q.option_a = q.option_b = q.option_c = q.option_d = None
        q.answer_key = request.form.get('answer_key')
        db.session.commit()
        flash('Question updated successfully!', 'success')
        return redirect(url_for('teacher_dashboard'))
    return render_template('edit_question.html', q=q, classes=CLASSES_7_TO_12)

@app.route('/teacher/delete_question/<int:q_id>', methods=['POST'])
@login_required
@role_required('teacher', 'admin')
def delete_question(q_id):
    q = QuestionBank.query.get_or_404(q_id)
    db.session.delete(q)
    db.session.commit()
    flash('Question removed from Question Bank.', 'info')
    return redirect(url_for('teacher_dashboard'))

@app.route('/teacher/generate_paper', methods=['POST'])
@login_required
@role_required('teacher', 'admin')
def generate_paper():
    target_class = request.form.get('target_class')
    subject = request.form.get('subject', '').strip()
    exam_title = request.form.get('exam_title') or 'Chapter Assessment Test'
    duration = request.form.get('duration') or '1 Hour 30 Mins'
    mcq_n = max(0, int(request.form.get('mcq_count', 0)))
    easy_n = max(0, int(request.form.get('easy_count', 0)))
    med_n = max(0, int(request.form.get('medium_count', 0)))
    hots_n = max(0, int(request.form.get('hots_count', 0)))

    base_q = QuestionBank.query.filter(
        QuestionBank.target_class == target_class,
        QuestionBank.subject.ilike(f"%{subject}%")
    )
    mcq_pool = base_q.filter_by(question_type='MCQ').all()
    subj_q = base_q.filter_by(question_type='Subjective')
    easy_pool = subj_q.filter_by(difficulty='Easy').all()
    med_pool = subj_q.filter_by(difficulty='Medium').all()
    hots_pool = subj_q.filter_by(difficulty='HOTS').all()

    if mcq_n > len(mcq_pool):
        flash(
            f"You requested {mcq_n} MCQs, but only {len(mcq_pool)} MCQ(s) exist in Question Bank for {target_class} ({subject}). "
            f"All {len(mcq_pool)} available MCQs were included; add more MCQs in Question Bank to reach {mcq_n}.",
            'warning'
        )

    selected_mcqs = random.sample(mcq_pool, min(mcq_n, len(mcq_pool)))
    selected_subj = (
        random.sample(easy_pool, min(easy_n, len(easy_pool))) +
        random.sample(med_pool, min(med_n, len(med_pool))) +
        random.sample(hots_pool, min(hots_n, len(hots_pool)))
    )
    all_selected = selected_mcqs + selected_subj
    total_marks = sum(q.marks for q in all_selected)
    return render_template(
        'generated_paper.html',
        target_class=target_class,
        subject=subject,
        exam_title=exam_title,
        duration=duration,
        mcqs=selected_mcqs,
        subjectives=selected_subj,
        all_questions=all_selected,
        total_marks=total_marks,
        today=date.today().strftime('%d-%b-%Y')
    )

# ---------------- STUDENT ROUTES ----------------
@app.route('/student')
@login_required
@role_required('student')
def student_dashboard():
    scores = TestScore.query.filter_by(student_id=current_user.id).all()
    faculty_list = User.query.filter(User.role.in_(['teacher', 'admin'])).order_by(
        User.experience_years.desc().nullslast(), User.id.asc()
    ).all()
    materials = StudyMaterial.query.filter_by(target_class=current_user.student_class).order_by(StudyMaterial.uploaded_at.desc()).all()
    fees = FeeRecord.query.filter_by(student_id=current_user.id).all()
    doubts = DoubtTicket.query.filter_by(student_id=current_user.id).all()
    att_records = Attendance.query.filter_by(student_id=current_user.id).order_by(Attendance.att_date.desc()).all()
    notices = Notice.query.filter(
        (Notice.target_class == 'All Classes') | (Notice.target_class == current_user.student_class)
    ).order_by(Notice.created_at.desc()).all()

    total_days = len(att_records)
    present_days = sum(1 for a in att_records if a.status == 'Present')
    att_pct = round((present_days / total_days) * 100, 1) if total_days > 0 else 100.0

    batch_avgs = []
    for s in scores:
        peer_scores = TestScore.query.join(User).filter(
            User.student_class == current_user.student_class,
            TestScore.subject == s.subject,
            TestScore.chapter == s.chapter
        ).all()
        if peer_scores:
            avg_val = sum((p.marks_obtained / p.max_marks) * 100 for p in peer_scores) / len(peer_scores)
            batch_avgs.append(round(avg_val, 1))
        else:
            batch_avgs.append(0)

    return render_template(
        'student_dashboard.html',
        scores=scores,
        batch_avgs=batch_avgs,
        materials=materials,
        fees=fees,
        doubts=doubts,
        att_records=att_records,
        att_pct=att_pct,
        notices=notices,
        faculty_list=faculty_list
    )

@app.route('/student/ask_doubt', methods=['POST'])
@login_required
@role_required('student')
def ask_doubt():
    doubt = DoubtTicket(
        student_id=current_user.id,
        subject=request.form.get('subject'),
        question=request.form.get('question')
    )
    db.session.add(doubt)
    db.session.commit()
    flash('Doubt submitted to faculty!', 'success')
    return redirect(url_for('student_dashboard'))

if __name__ == '__main__':
    app.run(debug=True)
