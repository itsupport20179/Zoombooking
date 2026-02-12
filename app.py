from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import text
from functools import wraps
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'zoom_booking_premium_2026'

# ใช้ SQLite เพื่อให้รันบน Render ได้ (SQL Server มึงต้องตั้งค่าเยอะกว่านี้สัส!)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- Models ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True)
    password = db.Column(db.String(255))
    role = db.Column(db.String(10))

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

# --- สร้าง Database และ User (ย้ายออกมาไว้นอก __main__ เพื่อให้ Render จัดการได้) ---
with app.app_context():
    db.create_all()
    initial_users = [
        {'u': 'admin', 'p': 'admin1234', 'r': 'admin'},
        {'u': 'user1', 'p': 'user1234', 'r': 'user'},
        {'u': 'user2', 'p': 'user1234', 'r': 'user'},
        {'u': 'user3', 'p': 'user1234', 'r': 'user'}
    ]
    for u_info in initial_users:
        if not User.query.filter_by(username=u_info['u']).first():
            new_user = User(
                username=u_info['u'],
                password=generate_password_hash(u_info['p']),
                role=u_info['r']
            )
            db.session.add(new_user)
    db.session.commit()

# --- Decorator สำหรับตรวจสอบ Login ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- Routes ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and check_password_hash(user.password, request.form['password']):
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role
            return redirect(url_for('index'))
        flash('Username หรือ Password ไม่ถูกต้อง', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
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
    req_name = request.form.get('requester_name')
    dept = request.form.get('department')
    topic = request.form.get('name')
    room = request.form.get('room')
    date = request.form.get('date')
    start = request.form.get('start_time')
    end = request.form.get('end_time')

    if start < "08:30" or end > "17:30" or start >= end:
        flash('กรุณาจองในช่วงเวลา 08:30 - 17:30 น. เท่านั้น', 'danger')
        return redirect(url_for('index'))

    conflict = Booking.query.filter_by(date=date, room=room).filter(
        (Booking.start_time < end) & (Booking.end_time > start)
    ).first()
    
    if conflict:
        flash(f'ห้อง {room} ในช่วงเวลานี้มีการจองแล้ว', 'danger')
        return redirect(url_for('index'))

    try:
        new_booking = Booking(
            requester_name=req_name,
            department=dept,
            name=topic,
            room=room,
            date=date,
            start_time=start,
            end_time=end,
            username=session['username']
        )
        db.session.add(new_booking)
        db.session.commit()
        flash('บันทึกการจองสำเร็จ!', 'success')
    except Exception as e:
        db.session.rollback()
        flash('เกิดข้อผิดพลาดในการบันทึกข้อมูล', 'danger')

    return redirect(url_for('index'))

@app.route('/admin')
@login_required
def admin_panel():
    if session.get('role') != 'admin': 
        return "Access Denied", 403
    bookings = Booking.query.order_by(Booking.date.desc(), Booking.start_time.asc()).all()
    return render_template('admin.html', bookings=bookings)

@app.route('/delete/<int:id>')
@login_required
def delete_booking(id):
    if session.get('role') != 'admin':
        return "Unauthorized", 401
    booking = db.session.get(Booking, id)
    if booking: 
        try:
            db.session.delete(booking)
            db.session.commit()
            flash('ลบรายการจองสำเร็จเรียบร้อยแล้ว', 'success')
        except Exception as e:
            db.session.rollback()
            flash('เกิดข้อผิดพลาดในการลบข้อมูล', 'danger')
    else:
        flash('ไม่พบรายการจองที่ต้องการลบ', 'warning')
    return redirect(url_for('admin_panel'))

@app.route('/edit_booking/<int:id>', methods=['POST'])
@login_required
def edit_booking(id):
    if session.get('role') != 'admin':
        return "Unauthorized", 401

    booking = db.session.get(Booking, id)
    if not booking:
        flash('ไม่พบรายการที่ต้องการแก้ไข', 'warning')
        return redirect(url_for('admin_panel'))

    req_name = request.form.get('requester_name')
    dept = request.form.get('department')
    topic = request.form.get('name')
    room = request.form.get('room')
    date = request.form.get('date')
    start = request.form.get('start_time')
    end = request.form.get('end_time')

    conflict = Booking.query.filter_by(date=date, room=room).filter(
        (Booking.id != id) & (Booking.start_time < end) & (Booking.end_time > start)
    ).first()

    if conflict:
        flash(f'ไม่สามารถแก้ไขได้ เนื่องจากเวลาทับซ้อนกับการจองอื่นในห้อง {room}', 'danger')
        return redirect(url_for('admin_panel'))

    try:
        booking.requester_name = req_name
        booking.department = dept
        booking.name = topic
        booking.room = room
        booking.date = date
        booking.start_time = start
        booking.end_time = end
        
        db.session.commit()
        flash('อัปเดตข้อมูลการจองเรียบร้อยแล้ว!', 'success')
    except Exception as e:
        db.session.rollback()
        flash('เกิดข้อผิดพลาดในการอัปเดตข้อมูล', 'danger')

    return redirect(url_for('admin_panel'))

# --- แก้ไขตรงนี้เพื่อเปิดประตูสู่โลกภายนอกบน Render! ---
if __name__ == '__main__':
    # Render จะส่ง Port มาให้เราผ่าน os.environ
    port = int(os.environ.get("PORT", 5000))
    # ต้องเป็น host='0.0.0.0' เพื่อเปิดรับ connection จากภายนอกเครื่อง
    app.run(host='0.0.0.0', port=port)
