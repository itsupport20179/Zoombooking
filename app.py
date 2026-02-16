from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import text
from functools import wraps
import os
import uuid 

app = Flask(__name__)
app.config['SECRET_KEY'] = 'zoom_booking_premium_2026'

# ใช้ SQLite
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- Models ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True)
    password = db.Column(db.String(255))
    role = db.Column(db.String(10)) # 'admin' or 'user'
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
    # สร้าง Admin ตัวแรกถ้ายังไม่มี
    if not User.query.filter_by(username='admin').first():
        db.session.add(User(username='admin', password=generate_password_hash('itsupport'), role='admin'))
    db.session.commit()

# --- Middleware ---
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

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        user = db.session.get(User, session['user_id'])
        if not user or user.role != 'admin':
            flash('เฉพาะผู้ดูแลระบบเท่านั้นที่สามารถเข้าถึงหน้านี้ได้', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# --- Routes ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and check_password_hash(user.password, request.form['password']):
            new_session_id = str(uuid.uuid4())
            user.current_session_id = new_session_id
            db.session.commit()
            
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role
            session['session_id'] = new_session_id 
            return redirect(url_for('index'))
        flash('ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง', 'danger')
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
    return jsonify([{
        'id': b.id, 
        'title': f"[{b.room}] {b.name}", 
        'start': f"{b.date}T{b.start_time}", 
        'end': f"{b.date}T{b.end_time}", 
        'extendedProps': {
            'room': b.room, 
            'requester': b.requester_name, 
            'dept': b.department, 
            'topic': b.name, 
            'creator': b.username
        }
    } for b in bookings])

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
@admin_required
def admin_panel():
    bookings = Booking.query.order_by(Booking.date.desc(), Booking.start_time.asc()).all()
    users = User.query.all() 
    return render_template('admin.html', bookings=bookings, users=users)

@app.route('/add_user', methods=['POST'])
@admin_required
def add_user():
    u = request.form.get('username')
    p = request.form.get('password')
    
    if User.query.filter_by(username=u).first():
        flash('ชื่อผู้ใช้นี้มีอยู่ในระบบแล้ว', 'danger')
        return redirect(url_for('admin_panel', tab='user'))
    else:
        new_user = User(username=u, password=generate_password_hash(p), role='user')
        db.session.add(new_user)
        db.session.commit()
        flash(f'เพิ่มผู้ใช้งาน {u} สำเร็จ!', 'success')
    return redirect(url_for('admin_panel', tab='user'))

@app.route('/edit_user/<int:id>', methods=['POST'])
@admin_required
def edit_user(id):
    user = db.session.get(User, id)
    if not user:
        flash('ไม่พบผู้ใช้งาน', 'danger')
        return redirect(url_for('admin_panel', tab='user'))
    
    new_username = request.form.get('username')
    new_password = request.form.get('password')
    
    if new_username != user.username:
        if User.query.filter_by(username=new_username).first():
            flash('ชื่อผู้ใช้นี้มีผู้ใช้งานแล้ว', 'danger')
            return redirect(url_for('admin_panel', tab='user'))
        user.username = new_username
    
    if new_password:
        user.password = generate_password_hash(new_password)
        user.current_session_id = str(uuid.uuid4()) 
        
    db.session.commit()
    flash(f'แก้ไขข้อมูล {user.username} เรียบร้อยแล้ว', 'success')
    return redirect(url_for('admin_panel', tab='user'))

@app.route('/delete_user/<int:id>')
@admin_required
def delete_user(id):
    user = db.session.get(User, id)
    if user:
        if user.username == session['username']:
            flash('ไม่สามารถลบชื่อผู้ใช้ที่กำลังใช้งานอยู่ได้', 'danger')
        else:
            db.session.delete(user)
            db.session.commit()
            flash('ลบผู้ใช้งานเรียบร้อยแล้ว', 'success')
    return redirect(url_for('admin_panel', tab='user'))

@app.route('/delete/<int:id>')
@admin_required
def delete_booking(id):
    booking = db.session.get(Booking, id)
    target_tab = booking.room if booking else 'all'
    if booking: 
        db.session.delete(booking)
        db.session.commit()
        flash('ลบรายการจองสำเร็จ', 'success')
    return redirect(url_for('admin_panel', tab=target_tab))

@app.route('/edit_booking/<int:id>', methods=['POST'])
@admin_required
def edit_booking(id):
    booking = db.session.get(Booking, id)
    if not booking: return redirect(url_for('admin_panel'))
    
    req_name = request.form.get('requester_name')
    dept = request.form.get('department')
    topic = request.form.get('name')
    room = request.form.get('room')
    date = request.form.get('date')
    start = request.form.get('start_time')
    end = request.form.get('end_time')
    
    # ตรวจสอบการทับซ้อน (ยกเว้น ID ของตัวเอง)
    conflict = Booking.query.filter_by(date=date, room=room).filter((Booking.id != id) & (Booking.start_time < end) & (Booking.end_time > start)).first()
    
    if conflict: 
        flash('ไม่สามารถแก้ไขได้ เนื่องจากช่วงเวลาทับซ้อนกับการจองอื่น', 'danger')
        # ส่งกลับไปยังห้องที่มีปัญหา
        return redirect(url_for('admin_panel', tab=room))
    else:
        booking.requester_name = req_name
        booking.department = dept
        booking.name = topic
        booking.room = room
        booking.date = date
        booking.start_time = start
        booking.end_time = end
        db.session.commit()
        flash('แก้ไขข้อมูลเรียบร้อยแล้ว', 'success')
    return redirect(url_for('admin_panel', tab=room))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
