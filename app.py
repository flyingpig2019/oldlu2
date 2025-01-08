from flask import Flask, render_template, request, redirect, url_for, session, send_file, flash
from datetime import datetime, timedelta
import sqlite3
import os
import subprocess
import logging
from dotenv import load_dotenv
from functools import wraps
from calendar import monthcalendar
from github_utils import pull_db_from_github, push_db_updates, upload_to_github, download_from_github, force_upload_to_github
import xlsxwriter
import io
import time

app = Flask(__name__)

# 确保在正确的目录加载.env文件
basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))

# 设置更安全的密钥
app.secret_key = os.urandom(24)

# 在文件开头添加星期转换字典
WEEKDAYS = {
    'Monday': '星期一',
    'Tuesday': '星期二',
    'Wednesday': '星期三',
    'Thursday': '星期四',
    'Friday': '星期五',
    'Saturday': '星期六',
    'Sunday': '星期日'
}

# 配置日志输出到终端
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[logging.StreamHandler()]
)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # 直接比较（仅用于测试）
        if username == 'oldlu214' and password == 'Fanghua530':
            session['logged_in'] = True
            return redirect(url_for('landing'))
        else:
            return render_template('login.html', error='用户名或密码错误')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/landing')
@login_required
def landing():
    try:
        # 获取最近的血压记录
        db = get_db()
        try:
            last_bp = db.execute('''
                SELECT morning_high, morning_low, afternoon_high, afternoon_low 
                FROM bloodpressure_records 
                ORDER BY date DESC LIMIT 1
            ''').fetchone()

            last_bp2 = db.execute('''
                SELECT morning_high, morning_low, afternoon_high, afternoon_low 
                FROM bloodpressure2_records 
                ORDER BY date DESC LIMIT 1
            ''').fetchone()

            last_bp3 = db.execute('''
                SELECT morning_high, morning_low, afternoon_high, afternoon_low 
                FROM bloodpressure3_records 
                ORDER BY date DESC LIMIT 1
            ''').fetchone()

            db.close()
            
            return render_template('landing.html', 
                current_date=datetime.now().strftime('%Y-%m-%d'),
                last_bp=last_bp or {'morning_high': '', 'morning_low': '', 
                                  'afternoon_high': '', 'afternoon_low': ''},
                last_bp2=last_bp2 or {'morning_high': '', 'morning_low': '', 
                                    'afternoon_high': '', 'afternoon_low': ''},
                last_bp3=last_bp3 or {'morning_high': '', 'morning_low': '', 
                                    'afternoon_high': '', 'afternoon_low': ''})

        except Exception as e:
            db.close()
            print(f"查询数据库时出错: {str(e)}")
            # 返回空记录
            return render_template('landing.html',
                current_date=datetime.now().strftime('%Y-%m-%d'),
                last_bp={'morning_high': '', 'morning_low': '', 
                        'afternoon_high': '', 'afternoon_low': ''},
                last_bp2={'morning_high': '', 'morning_low': '', 
                         'afternoon_high': '', 'afternoon_low': ''},
                last_bp3={'morning_high': '', 'morning_low': '', 
                         'afternoon_high': '', 'afternoon_low': ''})

    except Exception as e:
        print(f"访问页面时出错: {str(e)}")
        # 返回空记录
        return render_template('landing.html',
            current_date=datetime.now().strftime('%Y-%m-%d'),
            last_bp={'morning_high': '', 'morning_low': '', 
                    'afternoon_high': '', 'afternoon_low': ''},
            last_bp2={'morning_high': '', 'morning_low': '', 
                     'afternoon_high': '', 'afternoon_low': ''},
            last_bp3={'morning_high': '', 'morning_low': '', 
                     'afternoon_high': '', 'afternoon_low': ''})

@app.route('/upload_database')
@login_required
def upload_database():
    # 确保所有数据库连接都已关闭
    db = get_db()
    db.close()
    
    success, message = upload_to_github()
    if not success:
        flash(message, 'error')
    else:
        flash(message, 'success')
    
    return redirect(url_for('landing'))

@app.route('/download_database')
@login_required
def download_database():
    # 确保所有数据库连接都已关闭
    db = get_db()
    db.close()
    
    success, message = download_from_github()
    if not success:
        flash(message, 'error')
    else:
        flash(message, 'success')
    
    return redirect(url_for('landing'))

def get_db():
    """连接数据库，确保数据库文件有效"""
    db_path = 'monitor.db'
    try:
        # 如果数据库文件不存在或损坏，创建新的
        try:
            conn = sqlite3.connect(db_path, timeout=20, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            # 测试数据库
            conn.execute("SELECT 1")
            return conn
        except:
            # 关闭任何可能的连接
            try:
                conn.close()
            except:
                pass

            # 删除损坏的数据库文件
            try:
                if os.path.exists(db_path):
                    os.remove(db_path)
            except:
                pass

            # 创建新的数据库
            init_db()
            conn = sqlite3.connect(db_path, timeout=20, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            return conn

    except Exception as e:
        print(f"连接数据库时出错: {str(e)}")
        # 如果还是失败，尝试最后一次初始化
        try:
            init_db()
            conn = sqlite3.connect(db_path, timeout=20, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            return conn
        except:
            raise

def init_db():
    """初始化新的数据库"""
    try:
        conn = sqlite3.connect('monitor.db')
        c = conn.cursor()
        
        # 创建所需的表
        c.execute('''CREATE TABLE IF NOT EXISTS medicine_records
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      date TEXT NOT NULL,
                      day_of_week TEXT NOT NULL,
                      medicine_taken BOOLEAN NOT NULL,
                      notes TEXT)''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS checkin_records
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      date TEXT NOT NULL,
                      day_of_week TEXT NOT NULL,
                      checkin BOOLEAN NOT NULL,
                      checkout BOOLEAN NOT NULL,
                      notes TEXT,
                      income DECIMAL(10,2))''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS bloodpressure_records
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      date TEXT NOT NULL,
                      day_of_week TEXT NOT NULL,
                      morning_high INTEGER,
                      morning_low INTEGER,
                      afternoon_high INTEGER,
                      afternoon_low INTEGER,
                      notes TEXT,
                      today_average TEXT,
                      risk TEXT)''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS bloodpressure2_records
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      date TEXT NOT NULL,
                      day_of_week TEXT NOT NULL,
                      morning_high INTEGER,
                      morning_low INTEGER,
                      afternoon_high INTEGER,
                      afternoon_low INTEGER,
                      notes TEXT,
                      today_average TEXT,
                      risk TEXT)''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS bloodpressure3_records
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      date TEXT NOT NULL,
                      day_of_week TEXT NOT NULL,
                      morning_high INTEGER,
                      morning_low INTEGER,
                      afternoon_high INTEGER,
                      afternoon_low INTEGER,
                      notes TEXT,
                      today_average TEXT,
                      risk TEXT)''')
        
        conn.commit()
        conn.close()
        print("数据库初始化成功")
    except Exception as e:
        print(f"初始化数据库失败: {str(e)}")
        raise

def get_chinese_weekday(date_str):
    """将日期转换为中文星期几"""
    english_weekday = datetime.strptime(date_str, '%Y-%m-%d').strftime('%A')
    return WEEKDAYS[english_weekday]

@app.route('/add_medicine_record', methods=['POST'])
@login_required
def add_medicine_record():
    try:
        date = request.form['date']
        day_of_week = get_chinese_weekday(date)
        medicine_taken = 'medicine_taken' in request.form
        notes = request.form.get('notes', '')
        
        db = get_db()
        db.execute('''INSERT INTO medicine_records 
                     (date, day_of_week, medicine_taken, notes)
                     VALUES (?, ?, ?, ?)''',
                    [date, day_of_week, medicine_taken, notes])
        db.commit()
        db.close()
        
        # 自动上传到 GitHub
        force_upload_to_github()
        
        return redirect(url_for('landing'))
    except Exception as e:
        print(f"添加药物记录时出错: {str(e)}")
        return redirect(url_for('landing'))

@app.route('/medicine_detail')
@login_required
def medicine_detail():
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 10
        
        db = get_db()
        try:
            total = db.execute('SELECT COUNT(*) FROM medicine_records').fetchone()[0]
            total_pages = (total + per_page - 1) // per_page
            
            offset = (page - 1) * per_page
            records = db.execute('''SELECT * FROM medicine_records 
                                  ORDER BY date DESC LIMIT ? OFFSET ?''',
                               [per_page, offset]).fetchall()
            db.close()
            
            return render_template('medicinedetail.html',
                                records=records,
                                current_page=page,
                                total_pages=total_pages)
                                
        except sqlite3.DatabaseError:
            # 如果数据库访问出错，初始化数据库
            db.close()
            init_db()
            # 返回空记录
            return render_template('medicinedetail.html',
                                records=[],
                                current_page=1,
                                total_pages=1)
                                
    except Exception as e:
        print(f"访问药物记录页面时出错: {str(e)}")
        # 返回空记录
        return render_template('medicinedetail.html',
                            records=[],
                            current_page=1,
                            total_pages=1)

@app.route('/edit_medicine_record/<int:id>', methods=['POST'])
@login_required
def edit_medicine_record(id):
    try:
        medicine_taken = 'medicine_taken' in request.form
        notes = request.form.get('notes', '')
        
        db = get_db()
        db.execute('UPDATE medicine_records SET medicine_taken = ?, notes = ? WHERE id = ?',
                  [medicine_taken, notes, id])
        db.commit()
        db.close()
        
        # 自动上传到 GitHub
        force_upload_to_github()
        
        return redirect(url_for('medicine_detail'))
    except Exception as e:
        print(f"编辑药物记录时出错: {str(e)}")
        return redirect(url_for('medicine_detail'))

@app.route('/delete_medicine_record/<int:id>')
@login_required
def delete_medicine_record(id):
    try:
        db = get_db()
        db.execute('DELETE FROM medicine_records WHERE id = ?', [id])
        db.commit()
        db.close()
        
        # 自动上传到 GitHub
        force_upload_to_github()
        
        return redirect(url_for('medicine_detail'))
    except Exception as e:
        print(f"删除药物记录时出错: {str(e)}")
        return redirect(url_for('medicine_detail'))

@app.route('/add_checkin_record', methods=['POST'])
@login_required
def add_checkin_record():
    try:
        date = request.form['date']
        day_of_week = get_chinese_weekday(date)
        checkin = 'checkin' in request.form
        checkout = 'checkout' in request.form
        notes = request.form.get('notes', '')
        income = request.form.get('income', 0)
        
        db = get_db()
        db.execute('''INSERT INTO checkin_records 
                     (date, day_of_week, checkin, checkout, notes, income)
                     VALUES (?, ?, ?, ?, ?, ?)''',
                    [date, day_of_week, checkin, checkout, notes, income])
        db.commit()
        db.close()
        
        # 自动上传到 GitHub
        force_upload_to_github()
        
        return redirect(url_for('landing'))
    except Exception as e:
        print(f"添加签到记录时出错: {str(e)}")
        return redirect(url_for('landing'))

@app.route('/checkin_detail')
@login_required
def checkin_detail():
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    db = get_db()
    total = db.execute('SELECT COUNT(*) FROM checkin_records').fetchone()[0]
    total_pages = (total + per_page - 1) // per_page
    
    offset = (page - 1) * per_page
    records = db.execute('''SELECT * FROM checkin_records 
                           ORDER BY date DESC LIMIT ? OFFSET ?''',
                        [per_page, offset]).fetchall()
    db.close()
    
    return render_template('checkindetail.html',
                         records=records,
                         current_page=page,
                         total_pages=total_pages)

@app.route('/edit_checkin_record/<int:id>', methods=['POST'])
@login_required
def edit_checkin_record(id):
    try:
        checkin = 'checkin' in request.form
        checkout = 'checkout' in request.form
        notes = request.form.get('notes', '')
        income = request.form.get('income', 0)
        
        db = get_db()
        db.execute('''UPDATE checkin_records 
                     SET checkin = ?, checkout = ?, notes = ?, income = ?
                     WHERE id = ?''',
                  [checkin, checkout, notes, income, id])
        db.commit()
        db.close()
        
        # 自动上传到 GitHub
        force_upload_to_github()
        
        return redirect(url_for('checkin_detail'))
    except Exception as e:
        print(f"编辑签到记录时出错: {str(e)}")
        return redirect(url_for('checkin_detail'))

@app.route('/delete_checkin_record/<int:id>')
@login_required
def delete_checkin_record(id):
    db = get_db()
    db.execute('DELETE FROM checkin_records WHERE id = ?', [id])
    db.commit()
    db.close()
    
    push_db_updates()
    return redirect(url_for('checkin_detail'))

@app.route('/checkin_calendar')
@login_required
def checkin_calendar():
    current_month = datetime.now()
    calendar_data = monthcalendar(current_month.year, current_month.month)
    
    # 获取上个月和下个月的日期
    prev_month = (current_month.replace(day=1) - timedelta(days=1)).replace(day=1)
    next_month = (current_month.replace(day=28) + timedelta(days=4)).replace(day=1)
    
    db = get_db()
    records = db.execute('''SELECT date, checkin, checkout 
                           FROM checkin_records 
                           WHERE strftime('%Y-%m', date) = ?''',
                        [current_month.strftime('%Y-%m')]).fetchall()
    
    # 获取本月的收入统计
    monthly_income = db.execute('''
        SELECT SUM(income) as total
        FROM checkin_records
        WHERE strftime('%Y-%m', date) = ?
    ''', [current_month.strftime('%Y-%m')]).fetchone()['total'] or 0
    db.close()
    
    # 转换记录为字典以便快速查找
    record_dict = {r['date']: {'checkin': r['checkin'], 'checkout': r['checkout']} 
                  for r in records}
    
    return render_template('checkincalendardetail.html',
                         calendar=calendar_data,
                         current_month=current_month,
                         prev_month=prev_month,
                         next_month=next_month,
                         records=record_dict,
                         monthly_income=monthly_income)

@app.route('/checkin_calendar/<int:year>/<int:month>')
@login_required
def checkin_calendar_month(year, month):
    selected_month = datetime(year, month, 1)
    calendar_data = monthcalendar(year, month)
    
    # 获取上个月和下个月的日期
    prev_month = (selected_month.replace(day=1) - timedelta(days=1)).replace(day=1)
    next_month = (selected_month.replace(day=28) + timedelta(days=4)).replace(day=1)
    
    db = get_db()
    records = db.execute('''SELECT date, checkin, checkout 
                           FROM checkin_records 
                           WHERE strftime('%Y-%m', date) = ?''',
                        [selected_month.strftime('%Y-%m')]).fetchall()
    
    # 获取选中月份的收入统计
    monthly_income = db.execute('''
        SELECT SUM(income) as total
        FROM checkin_records
        WHERE strftime('%Y-%m', date) = ?
    ''', [selected_month.strftime('%Y-%m')]).fetchone()['total'] or 0
    db.close()
    
    # 转换记录为字典以便快速查找
    record_dict = {r['date']: {'checkin': r['checkin'], 'checkout': r['checkout']} 
                  for r in records}
    
    return render_template('checkincalendardetail.html',
                         calendar=calendar_data,
                         current_month=selected_month,
                         prev_month=prev_month,
                         next_month=next_month,
                         records=record_dict,
                         monthly_income=monthly_income)

@app.route('/add_blood_pressure', methods=['POST'])
@login_required
def add_blood_pressure():
    try:
        date = request.form['date']
        day_of_week = get_chinese_weekday(date)
        morning_high = request.form.get('morning_high', '')
        morning_low = request.form.get('morning_low', '')
        afternoon_high = request.form.get('afternoon_high', '')
        afternoon_low = request.form.get('afternoon_low', '')
        notes = request.form.get('notes', '')
        risk = request.form.get('risk', '')
        
        # 计算日均值
        daily_high = daily_low = None
        try:
            if morning_high and afternoon_high:
                daily_high = round((float(morning_high) + float(afternoon_high)) / 2, 1)
            elif morning_high:
                daily_high = float(morning_high)
            elif afternoon_high:
                daily_high = float(afternoon_high)
                
            if morning_low and afternoon_low:
                daily_low = round((float(morning_low) + float(afternoon_low)) / 2, 1)
            elif morning_low:
                daily_low = float(morning_low)
            elif afternoon_low:
                daily_low = float(afternoon_low)
            
            # 设置 today_average
            today_average = f"{daily_high}/{daily_low}" if daily_high is not None and daily_low is not None else ""
        except (ValueError, TypeError):
            today_average = ""
        
        db = get_db()
        db.execute('''INSERT INTO bloodpressure_records 
                     (date, day_of_week, morning_high, morning_low, 
                      afternoon_high, afternoon_low, notes, risk, today_average)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    [date, day_of_week, morning_high, morning_low, 
                     afternoon_high, afternoon_low, notes, risk, today_average])
        db.commit()
        db.close()
        
        force_upload_to_github()
        return redirect(url_for('landing'))
    except Exception as e:
        print(f"添加血压记录时出错: {str(e)}")
        return redirect(url_for('landing'))

@app.route('/edit_blood_pressure/<int:id>', methods=['POST'])
@login_required
def edit_blood_pressure(id):
    try:
        morning_high = request.form.get('morning_high')
        morning_low = request.form.get('morning_low')
        afternoon_high = request.form.get('afternoon_high')
        afternoon_low = request.form.get('afternoon_low')
        notes = request.form.get('notes', '')
        
        # 计算日均值
        daily_high = daily_low = None
        if morning_high and afternoon_high:
            daily_high = round((float(morning_high) + float(afternoon_high)) / 2, 1)
        elif morning_high:
            daily_high = float(morning_high)
        elif afternoon_high:
            daily_high = float(afternoon_high)
            
        if morning_low and afternoon_low:
            daily_low = round((float(morning_low) + float(afternoon_low)) / 2, 1)
        elif morning_low:
            daily_low = float(morning_low)
        elif afternoon_low:
            daily_low = float(afternoon_low)
        
        # 设置 today_average
        today_average = f"{daily_high}/{daily_low}" if daily_high is not None and daily_low is not None else ""
        
        db = get_db()
        db.execute('''UPDATE bloodpressure_records 
                     SET morning_high = ?, morning_low = ?,
                         afternoon_high = ?, afternoon_low = ?,
                         notes = ?, today_average = ?
                     WHERE id = ?''',
                  [morning_high, morning_low, afternoon_high, 
                   afternoon_low, notes, today_average, id])
        db.commit()
        db.close()
        
        force_upload_to_github()
        return redirect(url_for('blood_pressure_detail'))
    except Exception as e:
        print(f"编辑血压记录时出错: {str(e)}")
        return redirect(url_for('blood_pressure_detail'))

@app.route('/delete_blood_pressure/<int:id>')
@login_required
def delete_blood_pressure(id):
    db = get_db()
    db.execute('DELETE FROM bloodpressure_records WHERE id = ?', [id])
    db.commit()
    db.close()
    
    push_db_updates()
    return redirect(url_for('blood_pressure_detail'))

@app.route('/add_blood_pressure2', methods=['POST'])
@login_required
def add_blood_pressure2():
    try:
        date = request.form['date']
        day_of_week = get_chinese_weekday(date)
        morning_high = request.form.get('morning_high', '')
        morning_low = request.form.get('morning_low', '')
        afternoon_high = request.form.get('afternoon_high', '')
        afternoon_low = request.form.get('afternoon_low', '')
        notes = request.form.get('notes', '')
        risk = request.form.get('risk', '')
        
        # 计算日均值
        daily_high = daily_low = None
        try:
            if morning_high and afternoon_high:
                daily_high = round((float(morning_high) + float(afternoon_high)) / 2, 1)
            elif morning_high:
                daily_high = float(morning_high)
            elif afternoon_high:
                daily_high = float(afternoon_high)
                
            if morning_low and afternoon_low:
                daily_low = round((float(morning_low) + float(afternoon_low)) / 2, 1)
            elif morning_low:
                daily_low = float(morning_low)
            elif afternoon_low:
                daily_low = float(afternoon_low)
            
            # 设置 today_average
            today_average = f"{daily_high}/{daily_low}" if daily_high is not None and daily_low is not None else ""
        except (ValueError, TypeError):
            today_average = ""
        
        db = get_db()
        db.execute('''INSERT INTO bloodpressure2_records 
                     (date, day_of_week, morning_high, morning_low, 
                      afternoon_high, afternoon_low, notes, risk, today_average)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    [date, day_of_week, morning_high, morning_low, 
                     afternoon_high, afternoon_low, notes, risk, today_average])
        db.commit()
        db.close()
        
        force_upload_to_github()
        return redirect(url_for('landing'))
    except Exception as e:
        print(f"添加血压记录时出错: {str(e)}")
        return redirect(url_for('landing'))

@app.route('/edit_blood_pressure2/<int:id>', methods=['POST'])
@login_required
def edit_blood_pressure2(id):
    try:
        morning_high = request.form.get('morning_high')
        morning_low = request.form.get('morning_low')
        afternoon_high = request.form.get('afternoon_high')
        afternoon_low = request.form.get('afternoon_low')
        notes = request.form.get('notes', '')
        
        # 计算日均值
        daily_high = daily_low = None
        if morning_high and afternoon_high:
            daily_high = round((float(morning_high) + float(afternoon_high)) / 2, 1)
        elif morning_high:
            daily_high = float(morning_high)
        elif afternoon_high:
            daily_high = float(afternoon_high)
            
        if morning_low and afternoon_low:
            daily_low = round((float(morning_low) + float(afternoon_low)) / 2, 1)
        elif morning_low:
            daily_low = float(morning_low)
        elif afternoon_low:
            daily_low = float(afternoon_low)
        
        # 设置 today_average
        today_average = f"{daily_high}/{daily_low}" if daily_high is not None and daily_low is not None else ""
        
        db = get_db()
        db.execute('''UPDATE bloodpressure2_records 
                     SET morning_high = ?, morning_low = ?,
                         afternoon_high = ?, afternoon_low = ?,
                         notes = ?, today_average = ?
                     WHERE id = ?''',
                  [morning_high, morning_low, afternoon_high, 
                   afternoon_low, notes, today_average, id])
        db.commit()
        db.close()
        
        force_upload_to_github()
        return redirect(url_for('blood_pressure2_detail'))
    except Exception as e:
        print(f"编辑血压记录时出错: {str(e)}")
        return redirect(url_for('blood_pressure2_detail'))

@app.route('/delete_blood_pressure2/<int:id>')
@login_required
def delete_blood_pressure2(id):
    try:
        db = get_db()
        db.execute('DELETE FROM bloodpressure2_records WHERE id = ?', [id])
        db.commit()
        db.close()
        
        # 自动上传到 GitHub
        force_upload_to_github()
        
        return redirect(url_for('blood_pressure2_detail'))
    except Exception as e:
        print(f"删除血压记录时出错: {str(e)}")
        return redirect(url_for('blood_pressure2_detail'))

@app.route('/add_blood_pressure3', methods=['POST'])
@login_required
def add_blood_pressure3():
    try:
        date = request.form['date']
        day_of_week = get_chinese_weekday(date)
        morning_high = request.form.get('morning_high', '')
        morning_low = request.form.get('morning_low', '')
        afternoon_high = request.form.get('afternoon_high', '')
        afternoon_low = request.form.get('afternoon_low', '')
        notes = request.form.get('notes', '')
        risk = request.form.get('risk', '')
        
        # 计算日均值
        daily_high = daily_low = None
        try:
            if morning_high and afternoon_high:
                daily_high = round((float(morning_high) + float(afternoon_high)) / 2, 1)
            elif morning_high:
                daily_high = float(morning_high)
            elif afternoon_high:
                daily_high = float(afternoon_high)
                
            if morning_low and afternoon_low:
                daily_low = round((float(morning_low) + float(afternoon_low)) / 2, 1)
            elif morning_low:
                daily_low = float(morning_low)
            elif afternoon_low:
                daily_low = float(afternoon_low)
            
            # 设置 today_average
            today_average = f"{daily_high}/{daily_low}" if daily_high is not None and daily_low is not None else ""
        except (ValueError, TypeError):
            today_average = ""
        
        db = get_db()
        db.execute('''INSERT INTO bloodpressure3_records 
                     (date, day_of_week, morning_high, morning_low, 
                      afternoon_high, afternoon_low, notes, risk, today_average)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    [date, day_of_week, morning_high, morning_low, 
                     afternoon_high, afternoon_low, notes, risk, today_average])
        db.commit()
        db.close()
        
        force_upload_to_github()
        return redirect(url_for('landing'))
    except Exception as e:
        print(f"添加血压记录时出错: {str(e)}")
        return redirect(url_for('landing'))

@app.route('/edit_blood_pressure3/<int:id>', methods=['POST'])
@login_required
def edit_blood_pressure3(id):
    try:
        morning_high = request.form.get('morning_high')
        morning_low = request.form.get('morning_low')
        afternoon_high = request.form.get('afternoon_high')
        afternoon_low = request.form.get('afternoon_low')
        notes = request.form.get('notes', '')
        
        # 计算日均值
        daily_high = daily_low = None
        if morning_high and afternoon_high:
            daily_high = round((float(morning_high) + float(afternoon_high)) / 2, 1)
        elif morning_high:
            daily_high = float(morning_high)
        elif afternoon_high:
            daily_high = float(afternoon_high)
            
        if morning_low and afternoon_low:
            daily_low = round((float(morning_low) + float(afternoon_low)) / 2, 1)
        elif morning_low:
            daily_low = float(morning_low)
        elif afternoon_low:
            daily_low = float(afternoon_low)
        
        # 设置 today_average
        today_average = f"{daily_high}/{daily_low}" if daily_high is not None and daily_low is not None else ""
        
        db = get_db()
        db.execute('''UPDATE bloodpressure3_records 
                     SET morning_high = ?, morning_low = ?,
                         afternoon_high = ?, afternoon_low = ?,
                         notes = ?, today_average = ?
                     WHERE id = ?''',
                  [morning_high, morning_low, afternoon_high, 
                   afternoon_low, notes, today_average, id])
        db.commit()
        db.close()
        
        force_upload_to_github()
        return redirect(url_for('blood_pressure3_detail'))
    except Exception as e:
        print(f"编辑血压记录时出错: {str(e)}")
        return redirect(url_for('blood_pressure3_detail'))

@app.route('/delete_blood_pressure3/<int:id>')
@login_required
def delete_blood_pressure3(id):
    try:
        db = get_db()
        db.execute('DELETE FROM bloodpressure3_records WHERE id = ?', [id])
        db.commit()
        db.close()
        
        # 自动上传到 GitHub
        force_upload_to_github()
        
        return redirect(url_for('blood_pressure3_detail'))
    except Exception as e:
        print(f"删除血压记录时出错: {str(e)}")
        return redirect(url_for('blood_pressure3_detail'))

@app.route('/blood_pressure2_detail')
@login_required
def blood_pressure2_detail():
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    db = get_db()
    total = db.execute('SELECT COUNT(*) FROM bloodpressure2_records').fetchone()[0]
    total_pages = (total + per_page - 1) // per_page
    
    offset = (page - 1) * per_page
    records = db.execute('''SELECT * FROM bloodpressure2_records 
                           ORDER BY date DESC LIMIT ? OFFSET ?''',
                        [per_page, offset]).fetchall()
    
    # 将记录转换为字典列表，并计算日均值
    records_with_daily = []
    for record in records:
        record_dict = dict(record)
        # 修改日均值计算逻辑
        if record['morning_high'] and record['afternoon_high']:
            record_dict['daily_high'] = round((record['morning_high'] + record['afternoon_high']) / 2, 1)
        elif record['morning_high']:
            record_dict['daily_high'] = record['morning_high']
        elif record['afternoon_high']:
            record_dict['daily_high'] = record['afternoon_high']
        else:
            record_dict['daily_high'] = None
        
        if record['morning_low'] and record['afternoon_low']:
            record_dict['daily_low'] = round((record['morning_low'] + record['afternoon_low']) / 2, 1)
        elif record['morning_low']:
            record_dict['daily_low'] = record['morning_low']
        elif record['afternoon_low']:
            record_dict['daily_low'] = record['afternoon_low']
        else:
            record_dict['daily_low'] = None
        
        records_with_daily.append(record_dict)
    
    db.close()
    
    return render_template('bloodpressure2detail.html',
                         records=records_with_daily,
                         current_page=page,
                         total_pages=total_pages)

@app.route('/blood_pressure3_detail')
@login_required
def blood_pressure3_detail():
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    db = get_db()
    total = db.execute('SELECT COUNT(*) FROM bloodpressure3_records').fetchone()[0]
    total_pages = (total + per_page - 1) // per_page
    
    offset = (page - 1) * per_page
    records = db.execute('''SELECT * FROM bloodpressure3_records 
                           ORDER BY date DESC LIMIT ? OFFSET ?''',
                        [per_page, offset]).fetchall()
    
    # 将记录转换为字典列表，并计算日均值
    records_with_daily = []
    for record in records:
        record_dict = dict(record)
        # 修改日均值计算逻辑
        if record['morning_high'] and record['afternoon_high']:
            record_dict['daily_high'] = round((record['morning_high'] + record['afternoon_high']) / 2, 1)
        elif record['morning_high']:
            record_dict['daily_high'] = record['morning_high']
        elif record['afternoon_high']:
            record_dict['daily_high'] = record['afternoon_high']
        else:
            record_dict['daily_high'] = None
        
        if record['morning_low'] and record['afternoon_low']:
            record_dict['daily_low'] = round((record['morning_low'] + record['afternoon_low']) / 2, 1)
        elif record['morning_low']:
            record_dict['daily_low'] = record['morning_low']
        elif record['afternoon_low']:
            record_dict['daily_low'] = record['afternoon_low']
        else:
            record_dict['daily_low'] = None
        
        records_with_daily.append(record_dict)
    
    db.close()
    
    return render_template('bloodpressure3detail.html',
                         records=records_with_daily,
                         current_page=page,
                         total_pages=total_pages)

@app.route('/medicine_calendar')
@login_required
def medicine_calendar():
    current_month = datetime.now()
    calendar_data = monthcalendar(current_month.year, current_month.month)
    
    db = get_db()
    records = db.execute('''SELECT date, medicine_taken 
                           FROM medicine_records 
                           WHERE strftime('%Y-%m', date) = ?''',
                        [current_month.strftime('%Y-%m')]).fetchall()
    db.close()
    
    # 转换记录为字典以便快速查找
    record_dict = {r['date']: {'medicine_taken': r['medicine_taken']} 
                  for r in records}
    
    return render_template('medicinecalendardetail.html',
                         calendar=calendar_data,
                         current_month=current_month,
                         records=record_dict)

@app.route('/medicine_calendar/<int:year>/<int:month>')
@login_required
def medicine_calendar_month(year, month):
    selected_month = datetime(year, month, 1)
    calendar_data = monthcalendar(year, month)
    
    db = get_db()
    records = db.execute('''SELECT date, medicine_taken 
                           FROM medicine_records 
                           WHERE strftime('%Y-%m', date) = ?''',
                        [selected_month.strftime('%Y-%m')]).fetchall()
    db.close()
    
    # 转换记录为字典以便快速查找
    record_dict = {r['date']: {'medicine_taken': r['medicine_taken']} 
                  for r in records}
    
    return render_template('medicinecalendardetail.html',
                         calendar=calendar_data,
                         current_month=selected_month,
                         records=record_dict)

@app.route('/income_detail')
@login_required
def income_detail():
    # 获取日期范围参数
    start_date = request.args.get('start_date', 
                                (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
    end_date = request.args.get('end_date', datetime.now().strftime('%Y-%m-%d'))
    
    db = get_db()
    # 获取指定日期范围内的收入记录
    records = db.execute('''SELECT date, income 
                           FROM checkin_records 
                           WHERE date BETWEEN ? AND ?
                           ORDER BY date DESC''',
                        [start_date, end_date]).fetchall()
    
    # 计算总收入
    total_income = db.execute('''SELECT SUM(income) as total 
                                FROM checkin_records 
                                WHERE date BETWEEN ? AND ?''',
                             [start_date, end_date]).fetchone()['total'] or 0
    
    # 计算每日平均收入
    days = (datetime.strptime(end_date, '%Y-%m-%d') - 
            datetime.strptime(start_date, '%Y-%m-%d')).days + 1
    average_income = total_income / days if days > 0 else 0
    
    # 获取收入数据用于图表
    dates = [r['date'] for r in records]
    incomes = [float(r['income']) for r in records]
    
    db.close()
    
    return render_template('incomedetail.html',
                         start_date=start_date,
                         end_date=end_date,
                         records=records,
                         total_income=total_income,
                         average_income=average_income,
                         dates=dates,
                         incomes=incomes)

@app.route('/download_income_report')
@login_required
def download_income_report():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    db = get_db()
    records = db.execute('''
        SELECT date, day_of_week, checkin, checkout, income, notes
        FROM checkin_records 
        WHERE date BETWEEN ? AND ?
        ORDER BY date
    ''', [start_date, end_date]).fetchall()
    db.close()
    
    # 创建Excel文件
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output)
    worksheet = workbook.add_worksheet('收入报告')
    
    # 设置列宽
    worksheet.set_column('A:A', 12)  # 日期
    worksheet.set_column('B:B', 8)   # 星期
    worksheet.set_column('C:D', 8)   # 签到/签退
    worksheet.set_column('E:E', 10)  # 收入
    worksheet.set_column('F:F', 30)  # 备注
    
    # 写入表头
    headers = ['日期', '星期', '签到', '签退', '收入', '备注']
    for col, header in enumerate(headers):
        worksheet.write(0, col, header)
    
    # 写入数据
    for row, record in enumerate(records, 1):
        worksheet.write(row, 0, record['date'])
        worksheet.write(row, 1, record['day_of_week'])
        worksheet.write(row, 2, '是' if record['checkin'] else '否')
        worksheet.write(row, 3, '是' if record['checkout'] else '否')
        worksheet.write(row, 4, float(record['income']))
        worksheet.write(row, 5, record['notes'])
    
    workbook.close()
    output.seek(0)
    
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'收入报告_{start_date}至{end_date}.xlsx'
    )

@app.route('/blood_pressure_chart')
@login_required
def blood_pressure_chart():
    db = get_db()
    records = db.execute('''
        SELECT date, morning_high, morning_low, afternoon_high, afternoon_low
        FROM bloodpressure_records 
        ORDER BY date ASC
    ''').fetchall()
    db.close()
    
    dates = []
    morning_high = []
    morning_low = []
    afternoon_high = []
    afternoon_low = []
    
    for record in records:
        try:
            if any([record['morning_high'], record['morning_low'], 
                   record['afternoon_high'], record['afternoon_low']]):
                dates.append(record['date'])
                morning_high.append(float(record['morning_high']) if record['morning_high'] else None)
                morning_low.append(float(record['morning_low']) if record['morning_low'] else None)
                afternoon_high.append(float(record['afternoon_high']) if record['afternoon_high'] else None)
                afternoon_low.append(float(record['afternoon_low']) if record['afternoon_low'] else None)
        except (ValueError, TypeError) as e:
            print(f"处理记录出错: {str(e)}")
            continue
    
    return render_template('bloodpressurechart.html',
                         dates=dates,
                         morning_high=morning_high,
                         morning_low=morning_low,
                         afternoon_high=afternoon_high,
                         afternoon_low=afternoon_low)

@app.route('/blood_pressure_print')
@login_required
def blood_pressure_print():
    # 获取所有记录
    db = get_db()
    records = db.execute('''
        SELECT date, day_of_week, morning_high, morning_low, 
               afternoon_high, afternoon_low, notes, risk
        FROM bloodpressure_records 
        ORDER BY date DESC
    ''').fetchall()
    
    # 计算每条记录的日均值
    records_with_daily = []
    for record in records:
        record_dict = dict(record)
        if record['morning_high'] and record['afternoon_high']:
            record_dict['daily_high'] = round((record['morning_high'] + record['afternoon_high']) / 2, 1)
        else:
            record_dict['daily_high'] = None
        
        if record['morning_low'] and record['afternoon_low']:
            record_dict['daily_low'] = round((record['morning_low'] + record['afternoon_low']) / 2, 1)
        else:
            record_dict['daily_low'] = None
        
        records_with_daily.append(record_dict)
    
    db.close()
    
    # 创建Excel文件
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output)
    worksheet = workbook.add_worksheet('血压记录')
    
    # 设置列宽
    worksheet.set_column('A:A', 12)  # 日期
    worksheet.set_column('B:B', 8)   # 星期
    worksheet.set_column('C:F', 10)  # 血压值
    worksheet.set_column('G:G', 10)  # 日均值
    worksheet.set_column('H:H', 30)  # 备注
    worksheet.set_column('I:I', 10)  # 风险等级
    
    # 写入表头
    headers = ['日期', '星期', '晨间收缩压', '晨间舒张压', 
              '晚间收缩压', '晚间舒张压', '日均收缩压/舒张压', '备注', '风险等级']
    for col, header in enumerate(headers):
        worksheet.write(0, col, header)
    
    # 写入数据
    for row, record in enumerate(records_with_daily, 1):
        worksheet.write(row, 0, record['date'])
        worksheet.write(row, 1, record['day_of_week'])
        worksheet.write(row, 2, record['morning_high'])
        worksheet.write(row, 3, record['morning_low'])
        worksheet.write(row, 4, record['afternoon_high'])
        worksheet.write(row, 5, record['afternoon_low'])
        # 写入日均值
        if record['daily_high'] and record['daily_low']:
            worksheet.write(row, 6, f"{record['daily_high']}/{record['daily_low']}")
        else:
            worksheet.write(row, 6, '-')
        worksheet.write(row, 7, record['notes'])
        worksheet.write(row, 8, record['risk'])
    
    workbook.close()
    output.seek(0)
    
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'血压记录_{datetime.now().strftime("%Y%m%d")}.xlsx'
    )

@app.route('/blood_pressure2_print')
@login_required
def blood_pressure2_print():
    # 获取所有记录
    db = get_db()
    records = db.execute('''
        SELECT date, day_of_week, morning_high, morning_low, 
               afternoon_high, afternoon_low, notes, risk
        FROM bloodpressure2_records 
        ORDER BY date DESC
    ''').fetchall()
    
    # 计算每条记录的日均值
    records_with_daily = []
    for record in records:
        record_dict = dict(record)
        if record['morning_high'] and record['afternoon_high']:
            record_dict['daily_high'] = round((record['morning_high'] + record['afternoon_high']) / 2, 1)
        else:
            record_dict['daily_high'] = None
        
        if record['morning_low'] and record['afternoon_low']:
            record_dict['daily_low'] = round((record['morning_low'] + record['afternoon_low']) / 2, 1)
        else:
            record_dict['daily_low'] = None
        
        records_with_daily.append(record_dict)
    
    db.close()
    
    # 创建Excel文件
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output)
    worksheet = workbook.add_worksheet('血压记录')
    
    # 设置列宽
    worksheet.set_column('A:A', 12)  # 日期
    worksheet.set_column('B:B', 8)   # 星期
    worksheet.set_column('C:F', 10)  # 血压值
    worksheet.set_column('G:G', 10)  # 日均值
    worksheet.set_column('H:H', 30)  # 备注
    worksheet.set_column('I:I', 10)  # 风险等级
    
    # 写入表头
    headers = ['日期', '星期', '晨间收缩压', '晨间舒张压', 
              '晚间收缩压', '晚间舒张压', '日均收缩压/舒张压', '备注', '风险等级']
    for col, header in enumerate(headers):
        worksheet.write(0, col, header)
    
    # 写入数据
    for row, record in enumerate(records_with_daily, 1):
        worksheet.write(row, 0, record['date'])
        worksheet.write(row, 1, record['day_of_week'])
        worksheet.write(row, 2, record['morning_high'])
        worksheet.write(row, 3, record['morning_low'])
        worksheet.write(row, 4, record['afternoon_high'])
        worksheet.write(row, 5, record['afternoon_low'])
        # 写入日均值
        if record['daily_high'] and record['daily_low']:
            worksheet.write(row, 6, f"{record['daily_high']}/{record['daily_low']}")
        else:
            worksheet.write(row, 6, '-')
        worksheet.write(row, 7, record['notes'])
        worksheet.write(row, 8, record['risk'])
    
    workbook.close()
    output.seek(0)
    
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'血压记录_毛_{datetime.now().strftime("%Y%m%d")}.xlsx'
    )

@app.route('/blood_pressure3_print')
@login_required
def blood_pressure3_print():
    # 获取所有记录
    db = get_db()
    records = db.execute('''
        SELECT date, day_of_week, morning_high, morning_low, 
               afternoon_high, afternoon_low, notes, risk
        FROM bloodpressure3_records 
        ORDER BY date DESC
    ''').fetchall()
    
    # 计算每条记录的日均值
    records_with_daily = []
    for record in records:
        record_dict = dict(record)
        if record['morning_high'] and record['afternoon_high']:
            record_dict['daily_high'] = round((record['morning_high'] + record['afternoon_high']) / 2, 1)
        else:
            record_dict['daily_high'] = None
        
        if record['morning_low'] and record['afternoon_low']:
            record_dict['daily_low'] = round((record['morning_low'] + record['afternoon_low']) / 2, 1)
        else:
            record_dict['daily_low'] = None
        
        records_with_daily.append(record_dict)
    
    db.close()
    
    # 创建Excel文件
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output)
    worksheet = workbook.add_worksheet('血压记录')
    
    # 设置列宽
    worksheet.set_column('A:A', 12)  # 日期
    worksheet.set_column('B:B', 8)   # 星期
    worksheet.set_column('C:F', 10)  # 血压值
    worksheet.set_column('G:G', 10)  # 日均值
    worksheet.set_column('H:H', 30)  # 备注
    worksheet.set_column('I:I', 10)  # 风险等级
    
    # 写入表头
    headers = ['日期', '星期', '晨间收缩压', '晨间舒张压', 
              '晚间收缩压', '晚间舒张压', '日均收缩压/舒张压', '备注', '风险等级']
    for col, header in enumerate(headers):
        worksheet.write(0, col, header)
    
    # 写入数据
    for row, record in enumerate(records_with_daily, 1):
        worksheet.write(row, 0, record['date'])
        worksheet.write(row, 1, record['day_of_week'])
        worksheet.write(row, 2, record['morning_high'])
        worksheet.write(row, 3, record['morning_low'])
        worksheet.write(row, 4, record['afternoon_high'])
        worksheet.write(row, 5, record['afternoon_low'])
        # 写入日均值
        if record['daily_high'] and record['daily_low']:
            worksheet.write(row, 6, f"{record['daily_high']}/{record['daily_low']}")
        else:
            worksheet.write(row, 6, '-')
        worksheet.write(row, 7, record['notes'])
        worksheet.write(row, 8, record['risk'])
    
    workbook.close()
    output.seek(0)
    
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'血压记录_祺_{datetime.now().strftime("%Y%m%d")}.xlsx'
    )

@app.route('/blood_pressure_average')
@login_required
def blood_pressure_average():
    # 获取日期范围参数，默认最近30天
    end_date = request.args.get('end_date', datetime.now().strftime('%Y-%m-%d'))
    start_date = request.args.get('start_date', 
                                (datetime.strptime(end_date, '%Y-%m-%d') - timedelta(days=30)).strftime('%Y-%m-%d'))
    
    # 获取指定日期范围的记录
    db = get_db()
    records = db.execute('''
        SELECT date, morning_high, morning_low, afternoon_high, afternoon_low 
        FROM bloodpressure_records 
        WHERE date BETWEEN ? AND ?
        ORDER BY date ASC
    ''', [start_date, end_date]).fetchall()
    db.close()
    
    # 计算平均值
    morning_high_sum = morning_high_count = 0
    morning_low_sum = morning_low_count = 0
    afternoon_high_sum = afternoon_high_count = 0
    afternoon_low_sum = afternoon_low_count = 0
    daily_high_sum = daily_high_count = 0
    daily_low_sum = daily_low_count = 0
    
    for record in records:
        # 计算每天的平均值
        daily_high = daily_low = None
        high_count = low_count = 0
        
        if record['morning_high'] and record['afternoon_high']:
            daily_high = (record['morning_high'] + record['afternoon_high']) / 2
            daily_high_sum += daily_high
            daily_high_count += 1
        
        if record['morning_low'] and record['afternoon_low']:
            daily_low = (record['morning_low'] + record['afternoon_low']) / 2
            daily_low_sum += daily_low
            daily_low_count += 1
        
        if record['morning_high']:
            morning_high_sum += record['morning_high']
            morning_high_count += 1
        if record['morning_low']:
            morning_low_sum += record['morning_low']
            morning_low_count += 1
        if record['afternoon_high']:
            afternoon_high_sum += record['afternoon_high']
            afternoon_high_count += 1
        if record['afternoon_low']:
            afternoon_low_sum += record['afternoon_low']
            afternoon_low_count += 1
    
    # 计算平均值，避免除以零
    averages = {
        'morning_high': round(morning_high_sum / morning_high_count, 1) if morning_high_count > 0 else 0,
        'morning_low': round(morning_low_sum / morning_low_count, 1) if morning_low_count > 0 else 0,
        'afternoon_high': round(afternoon_high_sum / afternoon_high_count, 1) if afternoon_high_count > 0 else 0,
        'afternoon_low': round(afternoon_low_sum / afternoon_low_count, 1) if afternoon_low_count > 0 else 0,
        'daily_high': round(daily_high_sum / daily_high_count, 1) if daily_high_count > 0 else 0,
        'daily_low': round(daily_low_sum / daily_low_count, 1) if daily_low_count > 0 else 0
    }
    
    return render_template('bloodpressureaverage.html',
                         averages=averages,
                         days=len(records),
                         start_date=start_date,
                         end_date=end_date)

@app.route('/blood_pressure2_chart')
@login_required
def blood_pressure2_chart():
    db = get_db()
    records = db.execute('''
        SELECT date, morning_high, morning_low, afternoon_high, afternoon_low
        FROM bloodpressure2_records 
        ORDER BY date ASC
    ''').fetchall()
    db.close()
    
    dates = []
    morning_high = []
    morning_low = []
    afternoon_high = []
    afternoon_low = []
    
    for record in records:
        try:
            if any([record['morning_high'], record['morning_low'], 
                   record['afternoon_high'], record['afternoon_low']]):
                dates.append(record['date'])
                morning_high.append(float(record['morning_high']) if record['morning_high'] else None)
                morning_low.append(float(record['morning_low']) if record['morning_low'] else None)
                afternoon_high.append(float(record['afternoon_high']) if record['afternoon_high'] else None)
                afternoon_low.append(float(record['afternoon_low']) if record['afternoon_low'] else None)
        except (ValueError, TypeError) as e:
            print(f"处理记录出错: {str(e)}")
            continue
    
    return render_template('bloodpressure2chart.html',
                         dates=dates,
                         morning_high=morning_high,
                         morning_low=morning_low,
                         afternoon_high=afternoon_high,
                         afternoon_low=afternoon_low)

@app.route('/blood_pressure3_chart')
@login_required
def blood_pressure3_chart():
    db = get_db()
    records = db.execute('''
        SELECT date, morning_high, morning_low, afternoon_high, afternoon_low
        FROM bloodpressure3_records 
        ORDER BY date ASC
    ''').fetchall()
    db.close()
    
    dates = []
    morning_high = []
    morning_low = []
    afternoon_high = []
    afternoon_low = []
    
    for record in records:
        try:
            if any([record['morning_high'], record['morning_low'], 
                   record['afternoon_high'], record['afternoon_low']]):
                dates.append(record['date'])
                morning_high.append(float(record['morning_high']) if record['morning_high'] else None)
                morning_low.append(float(record['morning_low']) if record['morning_low'] else None)
                afternoon_high.append(float(record['afternoon_high']) if record['afternoon_high'] else None)
                afternoon_low.append(float(record['afternoon_low']) if record['afternoon_low'] else None)
        except (ValueError, TypeError) as e:
            print(f"处理记录出错: {str(e)}")
            continue
    
    return render_template('bloodpressure3chart.html',
                         dates=dates,
                         morning_high=morning_high,
                         morning_low=morning_low,
                         afternoon_high=afternoon_high,
                         afternoon_low=afternoon_low)

@app.route('/blood_pressure2_average')
@login_required
def blood_pressure2_average():
    # 获取日期范围参数，默认最近30天
    end_date = request.args.get('end_date', datetime.now().strftime('%Y-%m-%d'))
    start_date = request.args.get('start_date', 
                                (datetime.strptime(end_date, '%Y-%m-%d') - timedelta(days=30)).strftime('%Y-%m-%d'))
    
    # 获取指定日期范围的记录
    db = get_db()
    records = db.execute('''
        SELECT date, morning_high, morning_low, afternoon_high, afternoon_low 
        FROM bloodpressure2_records 
        WHERE date BETWEEN ? AND ?
        ORDER BY date ASC
    ''', [start_date, end_date]).fetchall()
    db.close()
    
    # 计算平均值
    morning_high_sum = morning_high_count = 0
    morning_low_sum = morning_low_count = 0
    afternoon_high_sum = afternoon_high_count = 0
    afternoon_low_sum = afternoon_low_count = 0
    daily_high_sum = daily_high_count = 0
    daily_low_sum = daily_low_count = 0
    
    for record in records:
        # 计算每天的平均值
        daily_high = daily_low = None
        high_count = low_count = 0
        
        if record['morning_high'] and record['afternoon_high']:
            daily_high = (record['morning_high'] + record['afternoon_high']) / 2
            daily_high_sum += daily_high
            daily_high_count += 1
        
        if record['morning_low'] and record['afternoon_low']:
            daily_low = (record['morning_low'] + record['afternoon_low']) / 2
            daily_low_sum += daily_low
            daily_low_count += 1
        
        if record['morning_high']:
            morning_high_sum += record['morning_high']
            morning_high_count += 1
        if record['morning_low']:
            morning_low_sum += record['morning_low']
            morning_low_count += 1
        if record['afternoon_high']:
            afternoon_high_sum += record['afternoon_high']
            afternoon_high_count += 1
        if record['afternoon_low']:
            afternoon_low_sum += record['afternoon_low']
            afternoon_low_count += 1
    
    # 计算平均值，避免除以零
    averages = {
        'morning_high': round(morning_high_sum / morning_high_count, 1) if morning_high_count > 0 else 0,
        'morning_low': round(morning_low_sum / morning_low_count, 1) if morning_low_count > 0 else 0,
        'afternoon_high': round(afternoon_high_sum / afternoon_high_count, 1) if afternoon_high_count > 0 else 0,
        'afternoon_low': round(afternoon_low_sum / afternoon_low_count, 1) if afternoon_low_count > 0 else 0,
        'daily_high': round(daily_high_sum / daily_high_count, 1) if daily_high_count > 0 else 0,
        'daily_low': round(daily_low_sum / daily_low_count, 1) if daily_low_count > 0 else 0
    }
    
    return render_template('bloodpressure2average.html',
                         averages=averages,
                         days=len(records),
                         start_date=start_date,
                         end_date=end_date)

@app.route('/blood_pressure3_average')
@login_required
def blood_pressure3_average():
    # 获取日期范围参数，默认最近30天
    end_date = request.args.get('end_date', datetime.now().strftime('%Y-%m-%d'))
    start_date = request.args.get('start_date', 
                                (datetime.strptime(end_date, '%Y-%m-%d') - timedelta(days=30)).strftime('%Y-%m-%d'))
    
    # 获取指定日期范围的记录
    db = get_db()
    records = db.execute('''
        SELECT date, morning_high, morning_low, afternoon_high, afternoon_low 
        FROM bloodpressure3_records 
        WHERE date BETWEEN ? AND ?
        ORDER BY date ASC
    ''', [start_date, end_date]).fetchall()
    db.close()
    
    # 计算平均值
    morning_high_sum = morning_high_count = 0
    morning_low_sum = morning_low_count = 0
    afternoon_high_sum = afternoon_high_count = 0
    afternoon_low_sum = afternoon_low_count = 0
    daily_high_sum = daily_high_count = 0
    daily_low_sum = daily_low_count = 0
    
    for record in records:
        # 计算每天的平均值
        daily_high = daily_low = None
        high_count = low_count = 0
        
        if record['morning_high'] and record['afternoon_high']:
            daily_high = (record['morning_high'] + record['afternoon_high']) / 2
            daily_high_sum += daily_high
            daily_high_count += 1
        
        if record['morning_low'] and record['afternoon_low']:
            daily_low = (record['morning_low'] + record['afternoon_low']) / 2
            daily_low_sum += daily_low
            daily_low_count += 1
        
        if record['morning_high']:
            morning_high_sum += record['morning_high']
            morning_high_count += 1
        if record['morning_low']:
            morning_low_sum += record['morning_low']
            morning_low_count += 1
        if record['afternoon_high']:
            afternoon_high_sum += record['afternoon_high']
            afternoon_high_count += 1
        if record['afternoon_low']:
            afternoon_low_sum += record['afternoon_low']
            afternoon_low_count += 1
    
    # 计算平均值，避免除以零
    averages = {
        'morning_high': round(morning_high_sum / morning_high_count, 1) if morning_high_count > 0 else 0,
        'morning_low': round(morning_low_sum / morning_low_count, 1) if morning_low_count > 0 else 0,
        'afternoon_high': round(afternoon_high_sum / afternoon_high_count, 1) if afternoon_high_count > 0 else 0,
        'afternoon_low': round(afternoon_low_sum / afternoon_low_count, 1) if afternoon_low_count > 0 else 0,
        'daily_high': round(daily_high_sum / daily_high_count, 1) if daily_high_count > 0 else 0,
        'daily_low': round(daily_low_sum / daily_low_count, 1) if daily_low_count > 0 else 0
    }
    
    return render_template('bloodpressure3average.html',
                         averages=averages,
                         days=len(records),
                         start_date=start_date,
                         end_date=end_date)

@app.route('/blood_pressure_print_range')
@login_required
def blood_pressure_print_range():
    return render_template('bloodpressureprintrange.html')

@app.route('/blood_pressure2_print_range')
@login_required
def blood_pressure2_print_range():
    return render_template('bloodpressure2printrange.html')

@app.route('/blood_pressure3_print_range')
@login_required
def blood_pressure3_print_range():
    return render_template('bloodpressure3printrange.html')

@app.route('/blood_pressure_print_selected', methods=['POST'])
@login_required
def blood_pressure_print_selected():
    start_date = request.form['start_date']
    end_date = request.form['end_date']
    
    db = get_db()
    records = db.execute('''
        SELECT date, day_of_week, morning_high, morning_low, 
               afternoon_high, afternoon_low, notes, risk
        FROM bloodpressure_records 
        WHERE date BETWEEN ? AND ?
        ORDER BY date DESC
    ''', [start_date, end_date]).fetchall()
    
    # 创建Excel文件
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output)
    worksheet = workbook.add_worksheet('血压记录')
    
    # 设置列宽
    worksheet.set_column('A:A', 12)  # 日期
    worksheet.set_column('B:B', 8)   # 星期
    worksheet.set_column('C:F', 10)  # 血压值
    worksheet.set_column('G:G', 10)  # 日均值
    worksheet.set_column('H:H', 30)  # 备注
    worksheet.set_column('I:I', 10)  # 风险等级
    
    # 写入表头
    headers = ['日期', '星期', '晨间收缩压', '晨间舒张压', 
              '晚间收缩压', '晚间舒张压', '日均收缩压/舒张压', '备注', '风险等级']
    for col, header in enumerate(headers):
        worksheet.write(0, col, header)
    
    # 写入数据
    for row, record in enumerate(records, 1):
        # 计算日均值
        daily_high = daily_low = None
        if record['morning_high'] and record['afternoon_high']:
            daily_high = round((record['morning_high'] + record['afternoon_high']) / 2, 1)
        if record['morning_low'] and record['afternoon_low']:
            daily_low = round((record['morning_low'] + record['afternoon_low']) / 2, 1)
        
        worksheet.write(row, 0, record['date'])
        worksheet.write(row, 1, record['day_of_week'])
        worksheet.write(row, 2, record['morning_high'])
        worksheet.write(row, 3, record['morning_low'])
        worksheet.write(row, 4, record['afternoon_high'])
        worksheet.write(row, 5, record['afternoon_low'])
        # 写入日均值
        if daily_high and daily_low:
            worksheet.write(row, 6, f"{daily_high}/{daily_low}")
        else:
            worksheet.write(row, 6, '-')
        worksheet.write(row, 7, record['notes'])
        worksheet.write(row, 8, record['risk'])
    
    workbook.close()
    output.seek(0)
    
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'血压记录_{start_date}至{end_date}.xlsx'
    )

@app.route('/blood_pressure2_print_selected', methods=['POST'])
@login_required
def blood_pressure2_print_selected():
    start_date = request.form['start_date']
    end_date = request.form['end_date']
    
    db = get_db()
    records = db.execute('''
        SELECT date, day_of_week, morning_high, morning_low, 
               afternoon_high, afternoon_low, notes, risk
        FROM bloodpressure2_records 
        WHERE date BETWEEN ? AND ?
        ORDER BY date DESC
    ''', [start_date, end_date]).fetchall()
    
    # 创建Excel文件
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output)
    worksheet = workbook.add_worksheet('血压记录')
    
    # 设置列宽
    worksheet.set_column('A:A', 12)  # 日期
    worksheet.set_column('B:B', 8)   # 星期
    worksheet.set_column('C:F', 10)  # 血压值
    worksheet.set_column('G:G', 10)  # 日均值
    worksheet.set_column('H:H', 30)  # 备注
    worksheet.set_column('I:I', 10)  # 风险等级
    
    # 写入表头
    headers = ['日期', '星期', '晨间收缩压', '晨间舒张压', 
              '晚间收缩压', '晚间舒张压', '日均收缩压/舒张压', '备注', '风险等级']
    for col, header in enumerate(headers):
        worksheet.write(0, col, header)
    
    # 写入数据
    for row, record in enumerate(records, 1):
        # 计算日均值
        daily_high = daily_low = None
        if record['morning_high'] and record['afternoon_high']:
            daily_high = round((record['morning_high'] + record['afternoon_high']) / 2, 1)
        if record['morning_low'] and record['afternoon_low']:
            daily_low = round((record['morning_low'] + record['afternoon_low']) / 2, 1)
        
        worksheet.write(row, 0, record['date'])
        worksheet.write(row, 1, record['day_of_week'])
        worksheet.write(row, 2, record['morning_high'])
        worksheet.write(row, 3, record['morning_low'])
        worksheet.write(row, 4, record['afternoon_high'])
        worksheet.write(row, 5, record['afternoon_low'])
        # 写入日均值
        if daily_high and daily_low:
            worksheet.write(row, 6, f"{daily_high}/{daily_low}")
        else:
            worksheet.write(row, 6, '-')
        worksheet.write(row, 7, record['notes'])
        worksheet.write(row, 8, record['risk'])
    
    workbook.close()
    output.seek(0)
    
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'血压记录_毛_{start_date}至{end_date}.xlsx'
    )

@app.route('/blood_pressure3_print_selected', methods=['POST'])
@login_required
def blood_pressure3_print_selected():
    start_date = request.form['start_date']
    end_date = request.form['end_date']
    
    db = get_db()
    records = db.execute('''
        SELECT date, day_of_week, morning_high, morning_low, 
               afternoon_high, afternoon_low, notes, risk
        FROM bloodpressure3_records 
        WHERE date BETWEEN ? AND ?
        ORDER BY date DESC
    ''', [start_date, end_date]).fetchall()
    
    # 创建Excel文件
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output)
    worksheet = workbook.add_worksheet('血压记录')
    
    # 设置列宽
    worksheet.set_column('A:A', 12)  # 日期
    worksheet.set_column('B:B', 8)   # 星期
    worksheet.set_column('C:F', 10)  # 血压值
    worksheet.set_column('G:G', 10)  # 日均值
    worksheet.set_column('H:H', 30)  # 备注
    worksheet.set_column('I:I', 10)  # 风险等级
    
    # 写入表头
    headers = ['日期', '星期', '晨间收缩压', '晨间舒张压', 
              '晚间收缩压', '晚间舒张压', '日均收缩压/舒张压', '备注', '风险等级']
    for col, header in enumerate(headers):
        worksheet.write(0, col, header)
    
    # 写入数据
    for row, record in enumerate(records, 1):
        # 计算日均值
        daily_high = daily_low = None
        if record['morning_high'] and record['afternoon_high']:
            daily_high = round((record['morning_high'] + record['afternoon_high']) / 2, 1)
        if record['morning_low'] and record['afternoon_low']:
            daily_low = round((record['morning_low'] + record['afternoon_low']) / 2, 1)
        
        worksheet.write(row, 0, record['date'])
        worksheet.write(row, 1, record['day_of_week'])
        worksheet.write(row, 2, record['morning_high'])
        worksheet.write(row, 3, record['morning_low'])
        worksheet.write(row, 4, record['afternoon_high'])
        worksheet.write(row, 5, record['afternoon_low'])
        # 写入日均值
        if daily_high and daily_low:
            worksheet.write(row, 6, f"{daily_high}/{daily_low}")
        else:
            worksheet.write(row, 6, '-')
        worksheet.write(row, 7, record['notes'])
        worksheet.write(row, 8, record['risk'])
    
    workbook.close()
    output.seek(0)
    
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'血压记录_祺_{start_date}至{end_date}.xlsx'
    )

@app.route('/blood_pressure_detail')
@login_required
def blood_pressure_detail():
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    db = get_db()
    total = db.execute('SELECT COUNT(*) FROM bloodpressure_records').fetchone()[0]
    total_pages = (total + per_page - 1) // per_page
    
    offset = (page - 1) * per_page
    records = db.execute('''SELECT * FROM bloodpressure_records 
                           ORDER BY date DESC LIMIT ? OFFSET ?''',
                        [per_page, offset]).fetchall()
    
    # 将记录转换为字典列表，并计算日均值
    records_with_daily = []
    for record in records:
        record_dict = dict(record)
        # 修改日均值计算逻辑
        if record['morning_high'] and record['afternoon_high']:
            record_dict['daily_high'] = round((record['morning_high'] + record['afternoon_high']) / 2, 1)
        elif record['morning_high']:
            record_dict['daily_high'] = record['morning_high']
        elif record['afternoon_high']:
            record_dict['daily_high'] = record['afternoon_high']
        else:
            record_dict['daily_high'] = None
        
        if record['morning_low'] and record['afternoon_low']:
            record_dict['daily_low'] = round((record['morning_low'] + record['afternoon_low']) / 2, 1)
        elif record['morning_low']:
            record_dict['daily_low'] = record['morning_low']
        elif record['afternoon_low']:
            record_dict['daily_low'] = record['afternoon_low']
        else:
            record_dict['daily_low'] = None
        
        records_with_daily.append(record_dict)
    
    db.close()
    
    return render_template('bloodpressuredetail.html',
                         records=records_with_daily,
                         current_page=page,
                         total_pages=total_pages)

@app.route('/update_today_average')
@login_required
def update_today_average():
    try:
        db = get_db()
        
        # 更新 bloodpressure_records
        records = db.execute('SELECT id, morning_high, morning_low, afternoon_high, afternoon_low FROM bloodpressure_records').fetchall()
        for record in records:
            daily_high = daily_low = None
            try:
                if record['morning_high'] and record['afternoon_high']:
                    daily_high = round((float(record['morning_high']) + float(record['afternoon_high'])) / 2, 1)
                elif record['morning_high']:
                    daily_high = float(record['morning_high'])
                elif record['afternoon_high']:
                    daily_high = float(record['afternoon_high'])
                    
                if record['morning_low'] and record['afternoon_low']:
                    daily_low = round((float(record['morning_low']) + float(record['afternoon_low'])) / 2, 1)
                elif record['morning_low']:
                    daily_low = float(record['morning_low'])
                elif record['afternoon_low']:
                    daily_low = float(record['afternoon_low'])
                
                today_average = f"{daily_high}/{daily_low}" if daily_high is not None and daily_low is not None else ""
                db.execute('UPDATE bloodpressure_records SET today_average = ? WHERE id = ?', 
                          [today_average, record['id']])
            except (ValueError, TypeError):
                continue
        
        # 更新 bloodpressure2_records
        records = db.execute('SELECT id, morning_high, morning_low, afternoon_high, afternoon_low FROM bloodpressure2_records').fetchall()
        for record in records:
            daily_high = daily_low = None
            try:
                if record['morning_high'] and record['afternoon_high']:
                    daily_high = round((float(record['morning_high']) + float(record['afternoon_high'])) / 2, 1)
                elif record['morning_high']:
                    daily_high = float(record['morning_high'])
                elif record['afternoon_high']:
                    daily_high = float(record['afternoon_high'])
                    
                if record['morning_low'] and record['afternoon_low']:
                    daily_low = round((float(record['morning_low']) + float(record['afternoon_low'])) / 2, 1)
                elif record['morning_low']:
                    daily_low = float(record['morning_low'])
                elif record['afternoon_low']:
                    daily_low = float(record['afternoon_low'])
                
                today_average = f"{daily_high}/{daily_low}" if daily_high is not None and daily_low is not None else ""
                db.execute('UPDATE bloodpressure2_records SET today_average = ? WHERE id = ?', 
                          [today_average, record['id']])
            except (ValueError, TypeError):
                continue
        
        # 更新 bloodpressure3_records
        records = db.execute('SELECT id, morning_high, morning_low, afternoon_high, afternoon_low FROM bloodpressure3_records').fetchall()
        for record in records:
            daily_high = daily_low = None
            try:
                if record['morning_high'] and record['afternoon_high']:
                    daily_high = round((float(record['morning_high']) + float(record['afternoon_high'])) / 2, 1)
                elif record['morning_high']:
                    daily_high = float(record['morning_high'])
                elif record['afternoon_high']:
                    daily_high = float(record['afternoon_high'])
                    
                if record['morning_low'] and record['afternoon_low']:
                    daily_low = round((float(record['morning_low']) + float(record['afternoon_low'])) / 2, 1)
                elif record['morning_low']:
                    daily_low = float(record['morning_low'])
                elif record['afternoon_low']:
                    daily_low = float(record['afternoon_low'])
                
                today_average = f"{daily_high}/{daily_low}" if daily_high is not None and daily_low is not None else ""
                db.execute('UPDATE bloodpressure3_records SET today_average = ? WHERE id = ?', 
                          [today_average, record['id']])
            except (ValueError, TypeError):
                continue
        
        db.commit()
        db.close()
        
        # 上传更新后的数据库
        force_upload_to_github()
        
        flash('所有记录的日均值已更新', 'success')
        return redirect(url_for('landing'))
    except Exception as e:
        print(f"更新日均值时出错: {str(e)}")
        flash('更新日均值时出错', 'error')
        return redirect(url_for('landing'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

