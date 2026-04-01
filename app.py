import os
import uuid
from functools import wraps
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import text, and_, or_
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'zoom_booking_dev_fallback_key_2026')

# --- ส่วนเชื่อมต่อ Supabase ---
# กำหนด Zoom Account สำเร็จรูป
ZOOM_ACCOUNTS = {
    'Zoom Account 1': {
        'email': 'zoomclt@centrallabthai.com',
        'password': 'P@ssW0rd'
    },
    'Zoom Account 2': {
        'email': 'zoomit@centrallabthai.com', 
        'password': 'Itclt@152'
    }
}

uri = os.environ.get('DATABASE_URL', 'sqlite:///database.db')
if uri and uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- Models (ระบุชื่อตารางให้ตรงกับ SQL เป๊ะๆ) ---
class User(db.Model):
    __tablename__ = 'user'  # บังคับใช้ชื่อตารางว่า user (ไม่มี s)
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True)
    password = db.Column(db.String(255))
    role = db.Column(db.String(10)) 
    current_session_id = db.Column(db.String(100), nullable=True)

class Booking(db.Model):
    __tablename__ = 'booking' # บังคับใช้ชื่อตารางว่า booking (ไม่มี s)
    id = db.Column(db.Integer, primary_key=True)
    requester_name = db.Column(db.String(100))
    department = db.Column(db.String(100))
    name = db.Column(db.String(255))
    room = db.Column(db.String(20))
    date = db.Column(db.String(10))
    start_time = db.Column(db.String(5))
    end_time = db.Column(db.String(5))
    username = db.Column(db.String(50))
    status = db.Column(db.String(20), default='pending')  # pending, approved, completed
    zoom_account = db.Column(db.String(50), nullable=True)  # Zoom Account 1 or 2
    zoom_email = db.Column(db.String(100), nullable=True)
    zoom_password = db.Column(db.String(100), nullable=True)

with app.app_context():
    db.create_all()
    # เช็คว่ามี admin หรือยัง ถ้าไม่มีให้สร้างใหม่ด้วยรหัส itsupport
    admin_user = User.query.filter_by(username='admin').first()
    if not admin_user:
        print("Creating admin user...")
        new_admin = User(
            username='admin',
            password=generate_password_hash('itsupport'), # ใช้ฟังก์ชันของ Python โดยตรง
            role='admin'
        )
        db.session.add(new_admin)
        db.session.commit()
        print("Admin created successfully!")

# --- ส่วน Logic ด้านล่าง (Middleware, Routes) ห้ามแก้และใช้ของเดิมทั้งหมด ---
# --- หลังจากจุดนี้ไปคือ Logic เดิมที่คุณมี ห้ามแก้/ลบ ให้คงไว้เหมือนเดิม ---

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
    try:
        # แสดงเฉพาะการจองที่อนุมัติแล้วเท่านั้น
        bookings = Booking.query.filter_by(status='approved').all()
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
                'creator': b.username,
                'status': b.status,
                'zoom_account': b.zoom_account,
                'zoom_email': b.zoom_email,
                'zoom_password': b.zoom_password
            }
        } for b in bookings])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# API สำหรับ user ดูการจองของตัวเอง
@app.route('/api/my_bookings')
@login_required
def get_my_bookings():
    try:
        bookings = Booking.query.filter_by(username=session['username']).order_by(Booking.date.desc()).all()
        return jsonify([{
            'id': b.id,
            'name': b.name,
            'room': b.room,
            'date': b.date,
            'start_time': b.start_time,
            'end_time': b.end_time,
            'requester_name': b.requester_name,
            'department': b.department,
            'status': b.status,
            'zoom_account': b.zoom_account,
            'zoom_email': b.zoom_email,
            'zoom_password': b.zoom_password
        } for b in bookings])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/book', methods=['POST'])
@login_required
def book():
    req_name = request.form.get('requester_name', '').strip()
    dept = request.form.get('department', '').strip()
    topic = request.form.get('name', '').strip()
    room = request.form.get('room', '').strip()
    date = request.form.get('date', '').strip()
    start = request.form.get('start_time', '').strip()
    end = request.form.get('end_time', '').strip()

    # Validate required fields
    if not all([req_name, dept, topic, date, start, end]):
        flash('กรุณากรอกข้อมูลให้ครบถ้วน', 'danger')
        return redirect(url_for('index'))

    # ถ้าไม่มีการเลือก room ให้ใช้ค่าเริ่มต้น
    if not room:
        room = 'รออนุมัติ'

    if start >= end:
        flash('กรุณาเลือกเวลาให้ถูกต้อง (เวลาเริ่มต้องน้อยกว่าเวลาสิ้นสุด)', 'danger')
        return redirect(url_for('index'))
    
    # ตรวจสอบการจองซ้อนเฉพาะเมื่อไม่ใช่ "รออนุมัติ"
    if room != 'รออนุมัติ':
        conflict = Booking.query.filter_by(date=date, room=room).filter(
            and_(Booking.start_time < end, Booking.end_time > start)
        ).first()
        if conflict:
            flash(f'ห้อง {room} ในช่วงเวลานี้มีการจองแล้ว', 'danger')
            return redirect(url_for('index'))
    
    try:
        db.session.add(Booking(
            requester_name=req_name,
            department=dept,
            name=topic,
            room=room,
            date=date,
            start_time=start,
            end_time=end,
            username=session['username'],
            status='pending'  # สถานะเริ่มต้น = รออนุมัติ
        ))
        db.session.commit()
        flash('บันทึกการจองสำเร็จ! รอการอนุมัติจากผู้ดูแลระบบ', 'success')
    except Exception:
        db.session.rollback()
        flash('เกิดข้อผิดพลาดในการบันทึกข้อมูล', 'danger')
    return redirect(url_for('index'))

@app.route('/admin')
@admin_required
def admin_panel():
    bookings = Booking.query.order_by(Booking.date.desc(), Booking.start_time.asc()).all()
    # เรียงลำดับ admin ขึ้นก่อน แล้วตามด้วย user
    from sqlalchemy import case
    users = User.query.order_by(
        case(
            (User.role == 'admin', 0),
            (User.role == 'user', 1)
        ),
        User.username.asc()
    ).all()
    return render_template('admin.html', bookings=bookings, users=users)

@app.route('/add_user', methods=['POST'])
@admin_required
def add_user():
    u = request.form.get('username', '').strip()
    p = request.form.get('password', '').strip()

    if not u or not p:
        flash('กรุณากรอก Username และ Password ให้ครบ', 'danger')
        return redirect(url_for('admin_panel', tab='user'))
    
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
    
    new_username = request.form.get('username', '').strip()
    new_password = request.form.get('password', '').strip()

    if not new_username:
        flash('กรุณากรอก Username', 'danger')
        return redirect(url_for('admin_panel', tab='user'))
    
    if new_username != user.username:
        if User.query.filter_by(username=new_username).first():
            flash('ชื่อผู้ใช้นี้มีผู้ใช้งานแล้ว', 'danger')
            return redirect(url_for('admin_panel', tab='user'))
        user.username = new_username
    
    if new_password:
        user.password = generate_password_hash(new_password)
        user.current_session_id = str(uuid.uuid4())  # Force re-login
        
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
    else:
        flash('ไม่พบผู้ใช้งานที่ต้องการลบ', 'danger')
    return redirect(url_for('admin_panel', tab='user'))

@app.route('/delete/<int:id>')
@admin_required
def delete_booking(id):
    booking = db.session.get(Booking, id)
    if booking:
        target_tab = booking.room
        db.session.delete(booking)
        db.session.commit()
        flash('ลบรายการจองสำเร็จ', 'success')
    else:
        target_tab = 'all'
        flash('ไม่พบรายการจองที่ต้องการลบ', 'danger')
    return redirect(url_for('admin_panel', tab=target_tab))

# Route สำหรับอนุมัติและส่ง Account Zoom
@app.route('/approve_zoom/<int:id>', methods=['POST'])
@admin_required
def approve_zoom(id):
    booking = db.session.get(Booking, id)
    if not booking:
        flash('ไม่พบรายการจอง', 'danger')
        return redirect(url_for('admin_panel'))
    
    zoom_account = request.form.get('zoom_account', '').strip()
    
    if not zoom_account or zoom_account not in ZOOM_ACCOUNTS:
        flash('กรุณาเลือก Zoom Account', 'danger')
        return redirect(url_for('admin_panel'))
    
    # อัพเดต booking พร้อม credentials
    booking.status = 'approved'
    booking.room = zoom_account  # อัพเดต room เป็น Zoom Account ที่เลือก
    booking.zoom_account = zoom_account
    booking.zoom_email = ZOOM_ACCOUNTS[zoom_account]['email']
    booking.zoom_password = ZOOM_ACCOUNTS[zoom_account]['password']
    
    db.session.commit()
    flash(f'อนุมัติและส่ง {zoom_account} สำเร็จ!', 'success')
    return redirect(url_for('admin_panel'))

@app.route('/edit_booking/<int:id>', methods=['POST'])
@admin_required
def edit_booking(id):
    booking = db.session.get(Booking, id)
    if not booking:
        flash('ไม่พบรายการจองที่ต้องการแก้ไข', 'danger')
        return redirect(url_for('admin_panel'))
    
    req_name = request.form.get('requester_name', '').strip()
    dept = request.form.get('department', '').strip()
    topic = request.form.get('name', '').strip()
    room = request.form.get('room', '').strip()
    date = request.form.get('date', '').strip()
    start = request.form.get('start_time', '').strip()
    end = request.form.get('end_time', '').strip()

    # Validate required fields
    if not all([req_name, dept, topic, room, date, start, end]):
        flash('กรุณากรอกข้อมูลให้ครบถ้วน', 'danger')
        return redirect(url_for('admin_panel', tab=booking.room))

    if start >= end:
        flash('กรุณาเลือกเวลาให้ถูกต้อง (เวลาเริ่มต้องน้อยกว่าเวลาสิ้นสุด)', 'danger')
        return redirect(url_for('admin_panel', tab=room))
    
    # ตรวจสอบการทับซ้อน (ยกเว้น ID ของตัวเอง)
    conflict = Booking.query.filter_by(date=date, room=room).filter(
        and_(Booking.id != id, Booking.start_time < end, Booking.end_time > start)
    ).first()
    
    if conflict:
        flash('ไม่สามารถแก้ไขได้ เนื่องจากช่วงเวลาทับซ้อนกับการจองอื่น', 'danger')
        return redirect(url_for('admin_panel', tab=room))
    else:
        booking.requester_name = req_name
        booking.department = dept
        booking.name = topic
        booking.date = date
        booking.start_time = start
        booking.end_time = end
        
        # ถ้า room (Zoom Account) เปลี่ยน ให้อัพเดต zoom credentials ด้วย
        if booking.room != room:
            if room in ZOOM_ACCOUNTS:
                booking.room = room
                booking.zoom_account = room
                booking.zoom_email = ZOOM_ACCOUNTS[room]['email']
                booking.zoom_password = ZOOM_ACCOUNTS[room]['password']
            else:
                # ถ้าเปลี่ยนเป็น room ที่ไม่ใช่ Zoom Account ให้ clear zoom credentials
                booking.room = room
                booking.zoom_account = None
                booking.zoom_email = None
                booking.zoom_password = None
        else:
            booking.room = room
        
        db.session.commit()
        flash('แก้ไขข้อมูลเรียบร้อยแล้ว', 'success')
    return redirect(url_for('admin_panel', tab=room))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
