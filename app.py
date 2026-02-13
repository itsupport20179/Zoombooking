from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import text
from functools import wraps
import os
import uuid 

app = Flask(__name__)
app.config['SECRET_KEY'] = 'zoom_booking_premium_2026'

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- Models ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True)
    password = db.Column(db.String(255))
    role = db.Column(db.String(10))
    current_session_id = db.Column(db.String(100), nullable=True)

class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    requester_name = db.Column(db.NVARCHAR(100))
    department = db.Column(db.NVARCHAR(100))
    name = db.Column(db.NVARCHAR(255))
    room = db.Column(db.String(20))
    date = db.Column(db.String(10))
    start_time = db.Column(db.String(5))
    end_time = db.Column(db.String(5))
    username = db.Column(db.String(50))

with app.app_context():
    db.create_all()
    # สร้าง Admin ตัวแรกถ้ายังไม่มี เพื่อให้เข้าระบบไปจัดการคนอื่นได้
    if not User.query.filter_by(username='admin').first():
        db.session.add(User(username='admin', password=generate_password_hash('admin1234'), role='admin'))
    db.session.commit()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        user = db.session.get(User, session['user_id'])
        if not user or user.current_session_id != session.get('session_id'):
            session.clear()
            flash('เซสชันของคุณหมดอายุ หรือมีการเข้าสู่ระบบจากที่อื่น', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- Routes ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and check_password_hash(user.password, request.form['password']):
            if user.current_session_id is not None:
                flash('บัญชีนี้กำลังมีการใช้งานอยู่', 'danger')
                return redirect(url_for('login'))
            new_session_id = str(uuid.uuid4())
            user.current_session_id = new_session_id
            db.session.commit()
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role
            session['session_id'] = new_session_id 
            return redirect(url_for('index'))
        flash('Username หรือ Password ไม่ถูกต้อง', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    if 'user_id' in session:
        user = db.session.get(User, session['user_id'])
        if user:
            user.current_session_id = None
            db.session.commit()
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    return render_template('index.html', role=session['role'], username=session['username'])

@app.route('/api/bookings')
@login_required
def get_bookings():
    bookings = Booking.query.all()
    return jsonify([{'id': b.id, 'title': f"[{b.room}] {b.name}", 'start': f"{b.date}T{b.start_time}", 'end': f"{b.date}T{b.end_time}", 'extendedProps': {'room': b.room, 'requester': b.requester_name, 'dept': b.department, 'topic': b.name, 'creator': b.username}} for b in bookings])

@app.route('/book', methods=['POST'])
@login_required
def book():
    req_name, dept, topic, room, date, start, end = request.form.get('requester_name'), request.form.get('department'), request.form.get('name'), request.form.get('room'), request.form.get('date'), request.form.get('start_time'), request.form.get('end_time')
    if start < "08:30" or end > "17:30" or start >= end:
        flash('กรุณาจองในช่วงเวลา 08:30 - 17:30 น. เท่านั้น', 'danger')
        return redirect(url_for('index'))
    conflict = Booking.query.filter_by(date=date, room=room).filter((Booking.start_time < end) & (Booking.end_time > start)).first()
    if conflict:
        flash(f'ห้อง {room} ในช่วงเวลานี้มีการจองแล้ว', 'danger')
        return redirect(url_for('index'))
    try:
        db.session.add(Booking(requester_name=req_name, department=dept, name=topic, room=room, date=date, start_time=start, end_time=end, username=session['username']))
        db.session.commit()
        flash('บันทึกการจองสำเร็จ!', 'success')
    except Exception:
        db.session.rollback()
        flash('เกิดข้อผิดพลาดในการบันทึกข้อมูล', 'danger')
    return redirect(url_for('index'))

@app.route('/admin')
@login_required
def admin_panel():
    if session.get('role') != 'admin': return "Access Denied", 403
    bookings = Booking.query.order_by(Booking.date.desc(), Booking.start_time.asc()).all()
    return render_template('admin.html', bookings=bookings)

# --- ส่วนที่กูเพิ่มให้: จัดการ User (CRUD) ---

@app.route('/admin/users')
@login_required
def manage_users():
    if session.get('role') != 'admin': return "Access Denied", 403
    return render_template('manage_users.html', users=User.query.all())

@app.route('/admin/users/add', methods=['POST'])
@login_required
def add_user():
    if session.get('role') != 'admin': return "Unauthorized", 401
    u, p, r = request.form.get('username'), request.form.get('password'), request.form.get('role')
    if User.query.filter_by(username=u).first(): flash('ชื่อผู้ใช้นี้มีอยู่แล้ว', 'danger')
    else:
        db.session.add(User(username=u, password=generate_password_hash(p), role=r))
        db.session.commit(); flash('เพิ่มผู้ใช้สำเร็จ!', 'success')
    return redirect(url_for('manage_users'))

@app.route('/admin/users/edit/<int:id>', methods=['POST'])
@login_required
def edit_user(id):
    if session.get('role') != 'admin': return "Unauthorized", 401
    user = db.session.get(User, id)
    if user:
        p = request.form.get('password')
        if p: user.password = generate_password_hash(p)
        user.role = request.form.get('role'); db.session.commit()
        flash('แก้ไขผู้ใช้สำเร็จ!', 'success')
    return redirect(url_for('manage_users'))

@app.route('/admin/users/delete/<int:id>')
@login_required
def delete_user(id):
    if session.get('role') != 'admin': return "Unauthorized", 401
    user = db.session.get(User, id)
    if user and user.username != session['username']:
        db.session.delete(user); db.session.commit(); flash('ลบผู้ใช้สำเร็จ!', 'success')
    else: flash('ไม่สามารถลบตัวเองได้', 'danger')
    return redirect(url_for('manage_users'))

# --- ฟังก์ชันลบและแก้ไข Booking (ของเดิมมึง) ---

@app.route('/delete/<int:id>')
@login_required
def delete_booking(id):
    if session.get('role') != 'admin': return "Unauthorized", 401
    booking = db.session.get(Booking, id)
    if booking: 
        db.session.delete(booking); db.session.commit(); flash('ลบรายการจองสำเร็จ', 'success')
    return redirect(url_for('admin_panel'))

@app.route('/edit_booking/<int:id>', methods=['POST'])
@login_required
def edit_booking(id):
    if session.get('role') != 'admin': return "Unauthorized", 401
    booking = db.session.get(Booking, id)
    if not booking: return redirect(url_for('admin_panel'))
    req_name, dept, topic, room, date, start, end = request.form.get('requester_name'), request.form.get('department'), request.form.get('name'), request.form.get('room'), request.form.get('date'), request.form.get('start_time'), request.form.get('end_time')
    conflict = Booking.query.filter_by(date=date, room=room).filter((Booking.id != id) & (Booking.start_time < end) & (Booking.end_time > start)).first()
    if conflict: flash('ไม่สามารถแก้ไขได้ เนื่องจากเวลาทับซ้อน', 'danger')
    else:
        booking.requester_name, booking.department, booking.name, booking.room, booking.date, booking.start_time, booking.end_time = req_name, dept, topic, room, date, start, end
        db.session.commit(); flash('แก้ไขข้อมูลสำเร็จ!', 'success')
    return redirect(url_for('admin_panel'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
