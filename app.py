import os
import random
from datetime import datetime, date
from functools import wraps
from flask import Flask, render_template, redirect, url_for, request, flash, abort
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from models import db, User, Attendance, TestScore, FeeRecord, StudyMaterial, DoubtTicket, QuestionBank, Notice

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'flourish-forge-du-cs-secret-2026')
uri = os.environ.get('DATABASE_URL', 'sqlite:///flourish_forge.db')
if uri.startswith('postgres://'):
    uri = uri.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads')

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

CLASSES_7_TO_12 = ['Class 7', 'Class 8', 'Class 9', 'Class 10', 'Class 11', 'Class 12']

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

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
    if not User.query.filter_by(email='director@flourishforge.in').first():
        admin = User(
            name='Shivam Tiwari',
            email='director@flourishforge.in',
            role='admin'
        )
        admin.set_password('flourishforge123')
        db.session.add(admin)

    if QuestionBank.query.count() == 0:
        sample_qs = [
            QuestionBank(target_class='Class 10', subject='Mathematics', chapter='Quadratic Equations',
                         question_type='MCQ', difficulty='Easy', marks=1,
                         question_text='If 1/2 is a root of the equation x^2 + kx - 5/4 = 0, then the value of k is:',
                         option_a='2', option_b='-2', option_c='1/4', option_d='1/2',
                         answer_key='(A) 2'),
            QuestionBank(target_class='Class 10', subject='Science', chapter='Light - Reflection and Refraction',
                         question_type='MCQ', difficulty='Easy', marks=1,
                         question_text='The focal length of a plane mirror is:',
                         option_a='Zero', option_b='Infinite', option_c='25 cm', option_d='-25 cm',
                         answer_key='(B) Infinite'),
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
            QuestionBank(target_class='Class 10', subject='Science', chapter='Electricity',
                         question_type='Subjective', difficulty='Medium', marks=3,
                         question_text='Three resistors of 5 ohm, 10 ohm, and 30 ohm are connected in parallel to a 12V battery. Calculate total resistance and total current.',
                         answer_key='R_eq = 3 ohm; I = 4 A'),
            QuestionBank(target_class='Class 8', subject='Mathematics', chapter='Linear Equations in One Variable',
                         question_type='MCQ', difficulty='Easy', marks=1,
                         question_text='What is the solution of 3x - 7 = 2x + 5?',
                         option_a='2', option_b='12', option_c='-12', option_d='5',
                         answer_key='(B) 12'),
            QuestionBank(target_class='Class 12', subject='Physics', chapter='Electrostatics',
                         question_type='Subjective', difficulty='Medium', marks=3,
                         question_text='Derive an expression for the electric field at a point on the axial line of an electric dipole.',
                         answer_key='E = (1 / 4*pi*eps_0) * (2p / r^3) for r >> a'),
        ]
        db.session.add_all(sample_qs)
    db.session.commit()

@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for(f"{current_user.role}_dashboard"))
    if request.method == 'POST':
        email = request.form.get('email').strip().lower()
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for(f"{user.role}_dashboard"))
        flash('Invalid Email or Password. Please try again.', 'danger')
    return render_template('login.html')

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
    name = request.form.get('name')
    email = request.form.get('email').strip().lower()
    password = request.form.get('password')
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
    flash(f'Password reset successfully for {user.name} ({user.email}).', 'success')
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
        today_str=date.today().isoformat()
    )

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
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        mat = StudyMaterial(
            title=request.form.get('title'),
            target_class=request.form.get('target_class'),
            subject=request.form.get('subject'),
            filename=filename,
            uploaded_by=current_user.name
        )
        db.session.add(mat)
        db.session.commit()
        flash('Worksheet/Notes uploaded successfully!', 'success')
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
        subject=request.form.get('subject').strip(),
        chapter=request.form.get('chapter').strip(),
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
        q.subject = request.form.get('subject').strip()
        q.chapter = request.form.get('chapter').strip()
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
    subject = request.form.get('subject').strip()
    exam_title = request.form.get('exam_title') or 'Chapter Assessment Test'
    duration = request.form.get('duration') or '1 Hour 30 Mins'
    mcq_n = int(request.form.get('mcq_count', 2))
    easy_n = int(request.form.get('easy_count', 2))
    med_n = int(request.form.get('medium_count', 2))
    hots_n = int(request.form.get('hots_count', 1))

    base_q = QuestionBank.query.filter(
        QuestionBank.target_class == target_class,
        QuestionBank.subject.ilike(f"%{subject}%")
    )
    mcq_pool = base_q.filter_by(question_type='MCQ').all()
    subj_q = base_q.filter_by(question_type='Subjective')
    easy_pool = subj_q.filter_by(difficulty='Easy').all()
    med_pool = subj_q.filter_by(difficulty='Medium').all()
    hots_pool = subj_q.filter_by(difficulty='HOTS').all()

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
    materials = StudyMaterial.query.filter_by(target_class=current_user.student_class).all()
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
        notices=notices
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
