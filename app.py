from flask import Flask, render_template, request, redirect, url_for, session, send_file, flash, jsonify
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
@login_required
def index():
    """首页"""
    from datetime import datetime
    current_year = datetime.now().year
    current_month = datetime.now().month
    return render_template('index.html', 
                         current_year=current_year,
                         current_month=current_month)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # 修改为实际的用户名和密码
        if username == 'oldlu214' and password == 'Fanghua530':
            session['logged_in'] = True
            return redirect(url_for('index'))
        else:
            flash('用户名或密码错误', 'error')
    
    # 确保传递current_year和current_month到模板
    current_year = datetime.now().year
    current_month = datetime.now().month
    return render_template('login.html', 
                         current_year=current_year,
                         current_month=current_month)

@app.route('/logout')
def logout():
    session.clear()  # 清除所有session数据
    flash('您已成功退出', 'success')
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
    """获取数据库连接"""
    db = sqlite3.connect('monitor.db')
    db.row_factory = sqlite3.Row
    return db

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
    """获取中文星期几"""
    date_obj = datetime.strptime(date_str, '%Y-%m-%d')
    return WEEKDAYS[date_obj.strftime('%A')]

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
        
        # 如果签到和签出都完成，自动设置收入为75
        income = 75 if checkin and checkout else request.form.get('income', 0)
        
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
    # 修改查询以按日期分组，获取每天最新的状态，并包含 id
    records = db.execute('''
        WITH daily_records AS (
            SELECT 
                id,
                date,
                day_of_week,
                MAX(checkin) as checkin_status,
                MAX(checkout) as checkout_status,
                GROUP_CONCAT(notes, ' ') as all_notes
            FROM (
                SELECT 
                    id,
                    date,
                    day_of_week,
                    checkin,
                    checkout,
                    notes
                FROM checkin_records
                ORDER BY id DESC
            )
            GROUP BY date
        )
        SELECT 
            id,
            date,
            day_of_week,
            checkin_status,
            checkout_status,
            CASE 
                WHEN checkin_status = 1 AND checkout_status = 1 THEN 75 
                ELSE 0 
            END as total_income,
            all_notes
        FROM daily_records
        ORDER BY date DESC
        LIMIT ? OFFSET ?
    ''', [per_page, (page - 1) * per_page]).fetchall()
    
    # 获取总记录数（按天计算）
    total = db.execute('''
        SELECT COUNT(DISTINCT date) 
        FROM checkin_records
    ''').fetchone()[0]
    
    # 转换记录格式
    formatted_records = []
    for record in records:
        formatted_records.append({
            'id': record['id'],
            'date': record['date'],
            'day_of_week': record['day_of_week'],
            'checkin': record['checkin_status'],
            'checkout': record['checkout_status'],
            'income': record['total_income'],
            'notes': record['all_notes'].strip() if record['all_notes'] else ''
        })
    
    db.close()
    
    total_pages = (total + per_page - 1) // per_page
    
    return render_template('checkindetail.html',
                         records=formatted_records,
                         current_page=page,
                         total_pages=total_pages)

@app.route('/edit_checkin_record/<int:id>', methods=['POST'])
@login_required
def edit_checkin_record(id):
    try:
        checkin = 'checkin' in request.form
        checkout = 'checkout' in request.form
        notes = request.form.get('notes', '')
        
        # 如果签到和签出都完成，自动设置收入为75
        income = 75 if checkin and checkout else request.form.get('income', 0)
        
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
    try:
        db = get_db()
        # 首先获取要删除记录的日期
        date = db.execute('SELECT date FROM checkin_records WHERE id = ?', [id]).fetchone()['date']
        
        # 删除该日期的所有记录
        db.execute('DELETE FROM checkin_records WHERE date = ?', [date])
        db.commit()
        db.close()
        
        # 自动上传到 GitHub
        force_upload_to_github()
        
        flash('成功删除该天的所有签到记录', 'success')
        return redirect(url_for('checkin_detail'))
    except Exception as e:
        print(f"删除签到记录时出错: {str(e)}")
        flash('删除记录时出错', 'error')
        return redirect(url_for('checkin_detail'))

@app.route('/checkin_calendar')
@login_required
def checkin_calendar():
    current_month = datetime.now()
    # 使用 calendar.monthcalendar 获取月历数据
    calendar_data = monthcalendar(current_month.year, current_month.month)
    
    # 获取月份第一天是星期几（0是星期一，6是星期日）
    first_day = datetime(current_month.year, current_month.month, 1)
    first_weekday = first_day.weekday()
    
    # 调整日历数据，使星期日显示在正确位置
    adjusted_calendar = []
    for week in calendar_data:
        adjusted_week = week[:-1]  # 去掉最后一个元素（星期日）
        adjusted_week.append(week[-1])  # 将星期日添加到最后
        adjusted_calendar.append(adjusted_week)
    
    # 获取上个月和下个月的日期
    prev_month = (current_month.replace(day=1) - timedelta(days=1)).replace(day=1)
    next_month = (current_month.replace(day=28) + timedelta(days=4)).replace(day=1)
    
    db = get_db()
    # 修改查询以获取每天的签到签出状态
    records = db.execute('''
        WITH daily_records AS (
            SELECT 
                date,
                MAX(checkin) as has_checkin,
                MAX(checkout) as has_checkout
            FROM checkin_records 
            WHERE strftime('%Y-%m', date) = ?
            GROUP BY date
        )
        SELECT 
            date,
            has_checkin,
            has_checkout,
            CASE 
                WHEN has_checkin = 1 AND has_checkout = 1 THEN 75 
                ELSE 0 
            END as total_income
        FROM daily_records
    ''', [current_month.strftime('%Y-%m')]).fetchall()
    
    # 获取本月的收入统计（根据签到签出状态计算）
    monthly_income = db.execute('''
        WITH daily_records AS (
            SELECT 
                date,
                MAX(checkin) as has_checkin,
                MAX(checkout) as has_checkout
            FROM checkin_records 
            WHERE strftime('%Y-%m', date) = ?
            GROUP BY date
        )
        SELECT SUM(
            CASE 
                WHEN has_checkin = 1 AND has_checkout = 1 THEN 75 
                ELSE 0 
            END
        ) as total
        FROM daily_records
    ''', [current_month.strftime('%Y-%m')]).fetchone()['total'] or 0
    
    db.close()
    
    # 转换记录为字典以便快速查找
    record_dict = {}
    for r in records:
        record_dict[r['date']] = {
            'checkin': r['has_checkin'],
            'checkout': r['has_checkout'],
            'income': r['total_income'],
            'completed': r['has_checkin'] and r['has_checkout']
        }
    
    return render_template('checkincalendardetail.html',
                         calendar=adjusted_calendar,
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

def calculate_risk(high, low):
    """计算血压风险等级"""
    if high <= 120 and low <= 70:
        return "良好"
    elif high <= 130 and low <= 80:
        return "中等"
    else:
        return "偏高"

@app.route('/add_blood_pressure', methods=['POST'])
@login_required
def add_blood_pressure():
    try:
        date = request.form['date']
        day_of_week = get_chinese_weekday(date)
        owner_id = 1  # 血压监测
        notes = request.form.get('notes', '')
        
        db = get_db()
        
        if 'morning_submit' in request.form:
            morning_high = request.form.get('morning_high', '')
            morning_low = request.form.get('morning_low', '')
            
            try:
                # 插入或更新早间记录
                db.execute('''INSERT INTO morning_bloodpressure_records 
                            (date, day_of_week, owner_id, morning_high, morning_low)
                            VALUES (?, ?, ?, ?, ?)''',
                         [date, day_of_week, owner_id, morning_high, morning_low])
            except sqlite3.IntegrityError:
                db.execute('''UPDATE morning_bloodpressure_records 
                            SET morning_high = ?, morning_low = ?
                            WHERE date = ? AND owner_id = ?''',
                         [morning_high, morning_low, date, owner_id])
            
            # 更新备注
            try:
                db.execute('''INSERT INTO bloodpressure_notes_records 
                            (date, day_of_week, owner_id, notes)
                            VALUES (?, ?, ?, ?)''',
                         [date, day_of_week, owner_id, notes])
            except sqlite3.IntegrityError:
                db.execute('''UPDATE bloodpressure_notes_records 
                            SET notes = ?
                            WHERE date = ? AND owner_id = ?''',
                         [notes, date, owner_id])
        
        elif 'afternoon_submit' in request.form:
            night_high = request.form.get('afternoon_high', '')
            night_low = request.form.get('afternoon_low', '')
            
            try:
                # 插入或更新晚间记录
                db.execute('''INSERT INTO night_bloodpressure_records 
                            (date, day_of_week, owner_id, night_high, night_low)
                            VALUES (?, ?, ?, ?, ?)''',
                         [date, day_of_week, owner_id, night_high, night_low])
            except sqlite3.IntegrityError:
                db.execute('''UPDATE night_bloodpressure_records 
                            SET night_high = ?, night_low = ?
                            WHERE date = ? AND owner_id = ?''',
                         [night_high, night_low, date, owner_id])
            
            # 更新备注
            try:
                db.execute('''INSERT INTO bloodpressure_notes_records 
                            (date, day_of_week, owner_id, notes)
                            VALUES (?, ?, ?, ?)''',
                         [date, day_of_week, owner_id, notes])
            except sqlite3.IntegrityError:
                db.execute('''UPDATE bloodpressure_notes_records 
                            SET notes = ?
                            WHERE date = ? AND owner_id = ?''',
                         [notes, date, owner_id])
        
        # 计算并更新日均值和风险等级
        record = db.execute('''
            SELECT m.morning_high, m.morning_low, n.night_high, n.night_low
            FROM morning_bloodpressure_records m
            LEFT JOIN night_bloodpressure_records n 
            ON m.date = n.date AND m.owner_id = n.owner_id
            WHERE m.date = ? AND m.owner_id = ?
        ''', [date, owner_id]).fetchone()
        
        if record:
            avg_high = avg_low = None
            if record['morning_high'] and record['night_high']:
                avg_high = round((record['morning_high'] + record['night_high']) / 2, 1)
            elif record['morning_high']:
                avg_high = record['morning_high']
            elif record['night_high']:
                avg_high = record['night_high']
                
            if record['morning_low'] and record['night_low']:
                avg_low = round((record['morning_low'] + record['night_low']) / 2, 1)
            elif record['morning_low']:
                avg_low = record['morning_low']
            elif record['night_low']:
                avg_low = record['night_low']
            
            if avg_high and avg_low:
                average = f"{avg_high}/{avg_low}"
                risk = calculate_risk(avg_high, avg_low)
                
                try:
                    db.execute('''INSERT INTO bloodpressure_calculation_records 
                                (date, day_of_week, owner_id, average, risk)
                                VALUES (?, ?, ?, ?, ?)''',
                             [date, day_of_week, owner_id, average, risk])
                except sqlite3.IntegrityError:
                    db.execute('''UPDATE bloodpressure_calculation_records 
                                SET average = ?, risk = ?
                                WHERE date = ? AND owner_id = ?''',
                             [average, risk, date, owner_id])
        
        db.commit()
        db.close()
        
        force_upload_to_github()
        return redirect(url_for('blood_pressure_detail'))
    except Exception as e:
        print(f"添加血压记录时出错: {str(e)}")
        return redirect(url_for('blood_pressure_detail'))

@app.route('/edit_blood_pressure/<date>', methods=['POST'])  # 修改这里
@login_required
def edit_blood_pressure(date):  # 修改这里
    try:
        day_of_week = get_chinese_weekday(date)
        owner_id = 1  # 血压监测
        morning_high = request.form.get('morning_high')
        morning_low = request.form.get('morning_low')
        afternoon_high = request.form.get('afternoon_high')
        afternoon_low = request.form.get('afternoon_low')
        notes = request.form.get('notes', '')
        
        db = get_db()
        
        # 更新早间数据
        if morning_high or morning_low:
            try:
                db.execute('''INSERT INTO morning_bloodpressure_records 
                             (date, day_of_week, owner_id, morning_high, morning_low)
                             VALUES (?, ?, ?, ?, ?)''',
                         [date, day_of_week, owner_id, morning_high, morning_low])
            except sqlite3.IntegrityError:
                db.execute('''UPDATE morning_bloodpressure_records 
                             SET morning_high = ?, morning_low = ?
                             WHERE date = ? AND owner_id = ?''',
                         [morning_high, morning_low, date, owner_id])
        
        # 更新晚间数据
        if afternoon_high or afternoon_low:
            try:
                db.execute('''INSERT INTO night_bloodpressure_records 
                             (date, day_of_week, owner_id, night_high, night_low)
                             VALUES (?, ?, ?, ?, ?)''',
                         [date, day_of_week, owner_id, afternoon_high, afternoon_low])
            except sqlite3.IntegrityError:
                db.execute('''UPDATE night_bloodpressure_records 
                             SET night_high = ?, night_low = ?
                             WHERE date = ? AND owner_id = ?''',
                         [afternoon_high, afternoon_low, date, owner_id])
        
        # 更新备注
        try:
            db.execute('''INSERT INTO bloodpressure_notes_records 
                         (date, day_of_week, owner_id, notes)
                         VALUES (?, ?, ?, ?)''',
                      [date, day_of_week, owner_id, notes])
        except sqlite3.IntegrityError:
            db.execute('''UPDATE bloodpressure_notes_records 
                         SET notes = ?
                         WHERE date = ? AND owner_id = ?''',
                      [notes, date, owner_id])
        
        # 重新计算日均值和风险等级
        update_blood_pressure_calculation(db, date, owner_id)
        
        db.commit()
        db.close()
        
        force_upload_to_github()
        flash('记录更新成功', 'success')
    except Exception as e:
        print(f"编辑血压记录时出错: {str(e)}")
        flash('编辑记录时出错', 'error')
    
    return redirect(url_for('blood_pressure_detail'))

@app.route('/delete_blood_pressure/<date>')  # 修改这里
@login_required
def delete_blood_pressure(date):  # 修改这里
    try:
        owner_id = 1  # 血压监测
        db = get_db()
        
        # 删除所有相关记录
        db.execute('DELETE FROM morning_bloodpressure_records WHERE date = ? AND owner_id = ?', 
                  [date, owner_id])
        db.execute('DELETE FROM night_bloodpressure_records WHERE date = ? AND owner_id = ?', 
                  [date, owner_id])
        db.execute('DELETE FROM bloodpressure_calculation_records WHERE date = ? AND owner_id = ?', 
                  [date, owner_id])
        db.execute('DELETE FROM bloodpressure_notes_records WHERE date = ? AND owner_id = ?', 
                  [date, owner_id])
        
        db.commit()
        db.close()
        
        force_upload_to_github()
        flash('记录删除成功', 'success')
    except Exception as e:
        print(f"删除记录时出错: {str(e)}")
        flash('删除记录时出错', 'error')
    
    return redirect(url_for('blood_pressure_detail'))

@app.route('/add_blood_pressure2', methods=['POST'])
@login_required
def add_blood_pressure2():
    try:
        date = request.form['date']
        day_of_week = get_chinese_weekday(date)
        owner_id = 2  # 血压监测-毛
        notes = request.form.get('notes', '')
        
        db = get_db()
        
        if 'morning_submit' in request.form:
            morning_high = request.form.get('morning_high', '')
            morning_low = request.form.get('morning_low', '')
            
            try:
                # 插入或更新早间记录
                db.execute('''INSERT INTO morning_bloodpressure_records 
                            (date, day_of_week, owner_id, morning_high, morning_low)
                            VALUES (?, ?, ?, ?, ?)''',
                         [date, day_of_week, owner_id, morning_high, morning_low])
            except sqlite3.IntegrityError:
                db.execute('''UPDATE morning_bloodpressure_records 
                            SET morning_high = ?, morning_low = ?
                            WHERE date = ? AND owner_id = ?''',
                         [morning_high, morning_low, date, owner_id])
            
            # 更新备注
            try:
                db.execute('''INSERT INTO bloodpressure_notes_records 
                            (date, day_of_week, owner_id, notes)
                            VALUES (?, ?, ?, ?)''',
                         [date, day_of_week, owner_id, notes])
            except sqlite3.IntegrityError:
                db.execute('''UPDATE bloodpressure_notes_records 
                            SET notes = ?
                            WHERE date = ? AND owner_id = ?''',
                         [notes, date, owner_id])
        
        elif 'afternoon_submit' in request.form:
            night_high = request.form.get('afternoon_high', '')
            night_low = request.form.get('afternoon_low', '')
            
            try:
                # 插入或更新晚间记录
                db.execute('''INSERT INTO night_bloodpressure_records 
                            (date, day_of_week, owner_id, night_high, night_low)
                            VALUES (?, ?, ?, ?, ?)''',
                         [date, day_of_week, owner_id, night_high, night_low])
            except sqlite3.IntegrityError:
                db.execute('''UPDATE night_bloodpressure_records 
                            SET night_high = ?, night_low = ?
                            WHERE date = ? AND owner_id = ?''',
                         [night_high, night_low, date, owner_id])
            
            # 更新备注
            try:
                db.execute('''INSERT INTO bloodpressure_notes_records 
                            (date, day_of_week, owner_id, notes)
                            VALUES (?, ?, ?, ?)''',
                         [date, day_of_week, owner_id, notes])
            except sqlite3.IntegrityError:
                db.execute('''UPDATE bloodpressure_notes_records 
                            SET notes = ?
                            WHERE date = ? AND owner_id = ?''',
                         [notes, date, owner_id])
        
        # 计算并更新日均值和风险等级
        record = db.execute('''
            SELECT m.morning_high, m.morning_low, n.night_high, n.night_low
            FROM morning_bloodpressure_records m
            LEFT JOIN night_bloodpressure_records n 
            ON m.date = n.date AND m.owner_id = n.owner_id
            WHERE m.date = ? AND m.owner_id = ?
        ''', [date, owner_id]).fetchone()
        
        if record:
            avg_high = avg_low = None
            if record['morning_high'] and record['night_high']:
                avg_high = round((record['morning_high'] + record['night_high']) / 2, 1)
            elif record['morning_high']:
                avg_high = record['morning_high']
            elif record['night_high']:
                avg_high = record['night_high']
                
            if record['morning_low'] and record['night_low']:
                avg_low = round((record['morning_low'] + record['night_low']) / 2, 1)
            elif record['morning_low']:
                avg_low = record['morning_low']
            elif record['night_low']:
                avg_low = record['night_low']
            
            if avg_high and avg_low:
                average = f"{avg_high}/{avg_low}"
                risk = calculate_risk(avg_high, avg_low)
                
                try:
                    db.execute('''INSERT INTO bloodpressure_calculation_records 
                                (date, day_of_week, owner_id, average, risk)
                                VALUES (?, ?, ?, ?, ?)''',
                             [date, day_of_week, owner_id, average, risk])
                except sqlite3.IntegrityError:
                    db.execute('''UPDATE bloodpressure_calculation_records 
                                SET average = ?, risk = ?
                                WHERE date = ? AND owner_id = ?''',
                             [average, risk, date, owner_id])
        
        db.commit()
        db.close()
        
        force_upload_to_github()
        return redirect(url_for('blood_pressure2_detail'))
    except Exception as e:
        print(f"添加血压记录时出错: {str(e)}")
        return redirect(url_for('blood_pressure2_detail'))

@app.route('/edit_blood_pressure2/<date>', methods=['POST'])
@login_required
def edit_blood_pressure2(date):  # 修改这里
    try:
        day_of_week = get_chinese_weekday(date)
        owner_id = 2  # 血压监测-毛
        morning_high = request.form.get('morning_high')
        morning_low = request.form.get('morning_low')
        afternoon_high = request.form.get('afternoon_high')
        afternoon_low = request.form.get('afternoon_low')
        notes = request.form.get('notes', '')
        
        db = get_db()
        
        # 更新早间数据
        if morning_high or morning_low:
            try:
                db.execute('''INSERT INTO morning_bloodpressure_records 
                             (date, day_of_week, owner_id, morning_high, morning_low)
                             VALUES (?, ?, ?, ?, ?)''',
                         [date, day_of_week, owner_id, morning_high, morning_low])
            except sqlite3.IntegrityError:
                db.execute('''UPDATE morning_bloodpressure_records 
                             SET morning_high = ?, morning_low = ?
                             WHERE date = ? AND owner_id = ?''',
                         [morning_high, morning_low, date, owner_id])
        
        # 更新晚间数据
        if afternoon_high or afternoon_low:
            try:
                db.execute('''INSERT INTO night_bloodpressure_records 
                             (date, day_of_week, owner_id, night_high, night_low)
                             VALUES (?, ?, ?, ?, ?)''',
                         [date, day_of_week, owner_id, afternoon_high, afternoon_low])
            except sqlite3.IntegrityError:
                db.execute('''UPDATE night_bloodpressure_records 
                             SET night_high = ?, night_low = ?
                             WHERE date = ? AND owner_id = ?''',
                         [afternoon_high, afternoon_low, date, owner_id])
        
        # 更新备注
        try:
            db.execute('''INSERT INTO bloodpressure_notes_records 
                         (date, day_of_week, owner_id, notes)
                         VALUES (?, ?, ?, ?)''',
                      [date, day_of_week, owner_id, notes])
        except sqlite3.IntegrityError:
            db.execute('''UPDATE bloodpressure_notes_records 
                         SET notes = ?
                         WHERE date = ? AND owner_id = ?''',
                      [notes, date, owner_id])
        
        # 重新计算日均值和风险等级
        record = db.execute('''
            SELECT m.morning_high, m.morning_low, n.night_high, n.night_low
            FROM morning_bloodpressure_records m
            LEFT JOIN night_bloodpressure_records n 
            ON m.date = n.date AND m.owner_id = n.owner_id
            WHERE m.date = ? AND m.owner_id = ?
        ''', [date, owner_id]).fetchone()
        
        if record:
            avg_high = avg_low = None
            if record['morning_high'] and record['night_high']:
                avg_high = round((record['morning_high'] + record['night_high']) / 2, 1)
            elif record['morning_high']:
                avg_high = record['morning_high']
            elif record['night_high']:
                avg_high = record['night_high']
                
            if record['morning_low'] and record['night_low']:
                avg_low = round((record['morning_low'] + record['night_low']) / 2, 1)
            elif record['morning_low']:
                avg_low = record['morning_low']
            elif record['night_low']:
                avg_low = record['night_low']
            
            if avg_high and avg_low:
                average = f"{avg_high}/{avg_low}"
                risk = calculate_risk(avg_high, avg_low)
                
                try:
                    db.execute('''INSERT INTO bloodpressure_calculation_records 
                                (date, day_of_week, owner_id, average, risk)
                                VALUES (?, ?, ?, ?, ?)''',
                             [date, day_of_week, owner_id, average, risk])
                except sqlite3.IntegrityError:
                    db.execute('''UPDATE bloodpressure_calculation_records 
                                SET average = ?, risk = ?
                                WHERE date = ? AND owner_id = ?''',
                             [average, risk, date, owner_id])
        
        db.commit()
        db.close()
        
        force_upload_to_github()
        return redirect(url_for('blood_pressure2_detail'))
    except Exception as e:
        print(f"编辑血压记录时出错: {str(e)}")
        return redirect(url_for('blood_pressure2_detail'))

@app.route('/delete_blood_pressure2/<date>')
@login_required
def delete_blood_pressure2(date):
    try:
        owner_id = 2  # 血压监测-毛
        db = get_db()
        
        # 删除所有相关记录
        db.execute('DELETE FROM morning_bloodpressure_records WHERE date = ? AND owner_id = ?', [date, owner_id])
        db.execute('DELETE FROM night_bloodpressure_records WHERE date = ? AND owner_id = ?', [date, owner_id])
        db.execute('DELETE FROM bloodpressure_calculation_records WHERE date = ? AND owner_id = ?', [date, owner_id])
        db.execute('DELETE FROM bloodpressure_notes_records WHERE date = ? AND owner_id = ?', [date, owner_id])
        
        db.commit()
        db.close()
        
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
        owner_id = 3  # 血压监测-祺
        notes = request.form.get('notes', '')
        
        db = get_db()
        
        if 'morning_submit' in request.form:
            morning_high = request.form.get('morning_high', '')
            morning_low = request.form.get('morning_low', '')
            
            try:
                # 插入或更新早间记录
                db.execute('''INSERT INTO morning_bloodpressure_records 
                            (date, day_of_week, owner_id, morning_high, morning_low)
                            VALUES (?, ?, ?, ?, ?)''',
                         [date, day_of_week, owner_id, morning_high, morning_low])
            except sqlite3.IntegrityError:
                db.execute('''UPDATE morning_bloodpressure_records 
                            SET morning_high = ?, morning_low = ?
                            WHERE date = ? AND owner_id = ?''',
                         [morning_high, morning_low, date, owner_id])
            
            # 更新备注
            try:
                db.execute('''INSERT INTO bloodpressure_notes_records 
                            (date, day_of_week, owner_id, notes)
                            VALUES (?, ?, ?, ?)''',
                         [date, day_of_week, owner_id, notes])
            except sqlite3.IntegrityError:
                db.execute('''UPDATE bloodpressure_notes_records 
                            SET notes = ?
                            WHERE date = ? AND owner_id = ?''',
                         [notes, date, owner_id])
        
        elif 'afternoon_submit' in request.form:
            night_high = request.form.get('afternoon_high', '')
            night_low = request.form.get('afternoon_low', '')
            
            try:
                # 插入或更新晚间记录
                db.execute('''INSERT INTO night_bloodpressure_records 
                            (date, day_of_week, owner_id, night_high, night_low)
                            VALUES (?, ?, ?, ?, ?)''',
                         [date, day_of_week, owner_id, night_high, night_low])
            except sqlite3.IntegrityError:
                db.execute('''UPDATE night_bloodpressure_records 
                            SET night_high = ?, night_low = ?
                            WHERE date = ? AND owner_id = ?''',
                         [night_high, night_low, date, owner_id])
            
            # 更新备注
            try:
                db.execute('''INSERT INTO bloodpressure_notes_records 
                            (date, day_of_week, owner_id, notes)
                            VALUES (?, ?, ?, ?)''',
                         [date, day_of_week, owner_id, notes])
            except sqlite3.IntegrityError:
                db.execute('''UPDATE bloodpressure_notes_records 
                            SET notes = ?
                            WHERE date = ? AND owner_id = ?''',
                         [notes, date, owner_id])
        
        # 计算并更新日均值和风险等级
        record = db.execute('''
            SELECT m.morning_high, m.morning_low, n.night_high, n.night_low
            FROM morning_bloodpressure_records m
            LEFT JOIN night_bloodpressure_records n 
            ON m.date = n.date AND m.owner_id = n.owner_id
            WHERE m.date = ? AND m.owner_id = ?
        ''', [date, owner_id]).fetchone()
        
        if record:
            avg_high = avg_low = None
            if record['morning_high'] and record['night_high']:
                avg_high = round((record['morning_high'] + record['night_high']) / 2, 1)
            elif record['morning_high']:
                avg_high = record['morning_high']
            elif record['night_high']:
                avg_high = record['night_high']
                
            if record['morning_low'] and record['night_low']:
                avg_low = round((record['morning_low'] + record['night_low']) / 2, 1)
            elif record['morning_low']:
                avg_low = record['morning_low']
            elif record['night_low']:
                avg_low = record['night_low']
            
            if avg_high and avg_low:
                average = f"{avg_high}/{avg_low}"
                risk = calculate_risk(avg_high, avg_low)
                
                try:
                    db.execute('''INSERT INTO bloodpressure_calculation_records 
                                (date, day_of_week, owner_id, average, risk)
                                VALUES (?, ?, ?, ?, ?)''',
                             [date, day_of_week, owner_id, average, risk])
                except sqlite3.IntegrityError:
                    db.execute('''UPDATE bloodpressure_calculation_records 
                                SET average = ?, risk = ?
                                WHERE date = ? AND owner_id = ?''',
                             [average, risk, date, owner_id])
        
        db.commit()
        db.close()
        
        force_upload_to_github()
        return redirect(url_for('blood_pressure3_detail'))
    except Exception as e:
        print(f"添加血压记录时出错: {str(e)}")
        return redirect(url_for('blood_pressure3_detail'))

@app.route('/edit_blood_pressure3/<date>', methods=['POST'])
@login_required
def edit_blood_pressure3(date):
    try:
        day_of_week = get_chinese_weekday(date)
        owner_id = 3  # 血压监测-祺
        morning_high = request.form.get('morning_high')
        morning_low = request.form.get('morning_low')
        afternoon_high = request.form.get('afternoon_high')
        afternoon_low = request.form.get('afternoon_low')
        notes = request.form.get('notes', '')
        
        db = get_db()
        
        # 更新早间数据
        if morning_high or morning_low:
            try:
                db.execute('''INSERT INTO morning_bloodpressure_records 
                             (date, day_of_week, owner_id, morning_high, morning_low)
                             VALUES (?, ?, ?, ?, ?)''',
                         [date, day_of_week, owner_id, morning_high, morning_low])
            except sqlite3.IntegrityError:
                db.execute('''UPDATE morning_bloodpressure_records 
                             SET morning_high = ?, morning_low = ?
                             WHERE date = ? AND owner_id = ?''',
                         [morning_high, morning_low, date, owner_id])
        
        # 更新晚间数据
        if afternoon_high or afternoon_low:
            try:
                db.execute('''INSERT INTO night_bloodpressure_records 
                             (date, day_of_week, owner_id, night_high, night_low)
                             VALUES (?, ?, ?, ?, ?)''',
                         [date, day_of_week, owner_id, afternoon_high, afternoon_low])
            except sqlite3.IntegrityError:
                db.execute('''UPDATE night_bloodpressure_records 
                             SET night_high = ?, night_low = ?
                             WHERE date = ? AND owner_id = ?''',
                         [afternoon_high, afternoon_low, date, owner_id])
        
        # 更新备注
        try:
            db.execute('''INSERT INTO bloodpressure_notes_records 
                         (date, day_of_week, owner_id, notes)
                         VALUES (?, ?, ?, ?)''',
                      [date, day_of_week, owner_id, notes])
        except sqlite3.IntegrityError:
            db.execute('''UPDATE bloodpressure_notes_records 
                         SET notes = ?
                         WHERE date = ? AND owner_id = ?''',
                      [notes, date, owner_id])
        
        # 重新计算日均值和风险等级
        record = db.execute('''
            SELECT m.morning_high, m.morning_low, n.night_high, n.night_low
            FROM morning_bloodpressure_records m
            LEFT JOIN night_bloodpressure_records n 
            ON m.date = n.date AND m.owner_id = n.owner_id
            WHERE m.date = ? AND m.owner_id = ?
        ''', [date, owner_id]).fetchone()
        
        if record:
            avg_high = avg_low = None
            if record['morning_high'] and record['night_high']:
                avg_high = round((record['morning_high'] + record['night_high']) / 2, 1)
            elif record['morning_high']:
                avg_high = record['morning_high']
            elif record['night_high']:
                avg_high = record['night_high']
                
            if record['morning_low'] and record['night_low']:
                avg_low = round((record['morning_low'] + record['night_low']) / 2, 1)
            elif record['morning_low']:
                avg_low = record['morning_low']
            elif record['night_low']:
                avg_low = record['night_low']
            
            if avg_high and avg_low:
                average = f"{avg_high}/{avg_low}"
                risk = calculate_risk(avg_high, avg_low)
                
                try:
                    db.execute('''INSERT INTO bloodpressure_calculation_records 
                                (date, day_of_week, owner_id, average, risk)
                                VALUES (?, ?, ?, ?, ?)''',
                             [date, day_of_week, owner_id, average, risk])
                except sqlite3.IntegrityError:
                    db.execute('''UPDATE bloodpressure_calculation_records 
                                SET average = ?, risk = ?
                                WHERE date = ? AND owner_id = ?''',
                             [average, risk, date, owner_id])
        
        db.commit()
        db.close()
        
        force_upload_to_github()
        return redirect(url_for('blood_pressure3_detail'))
    except Exception as e:
        print(f"编辑血压记录时出错: {str(e)}")
        return redirect(url_for('blood_pressure3_detail'))

@app.route('/delete_blood_pressure3/<date>')
@login_required
def delete_blood_pressure3(date):
    try:
        owner_id = 3  # 血压监测-祺
        db = get_db()
        
        # 删除所有相关记录
        db.execute('DELETE FROM morning_bloodpressure_records WHERE date = ? AND owner_id = ?', [date, owner_id])
        db.execute('DELETE FROM night_bloodpressure_records WHERE date = ? AND owner_id = ?', [date, owner_id])
        db.execute('DELETE FROM bloodpressure_calculation_records WHERE date = ? AND owner_id = ?', [date, owner_id])
        db.execute('DELETE FROM bloodpressure_notes_records WHERE date = ? AND owner_id = ?', [date, owner_id])
        
        db.commit()
        db.close()
        
        force_upload_to_github()
        return redirect(url_for('blood_pressure3_detail'))
    except Exception as e:
        print(f"删除血压记录时出错: {str(e)}")
        return redirect(url_for('blood_pressure3_detail'))

@app.route('/blood_pressure2_detail')
@login_required
def blood_pressure2_detail():
    page = request.args.get('page', 1, type=int)
    per_page = 10  # 每页显示10条记录
    offset = (page - 1) * per_page
    owner_id = 2  # 血压监测-毛
    
    db = get_db()
    
    # 获取总记录数
    total_records = db.execute('''
        SELECT COUNT(DISTINCT d.date) 
        FROM (
            SELECT date FROM morning_bloodpressure_records WHERE owner_id = ?
            UNION
            SELECT date FROM night_bloodpressure_records WHERE owner_id = ?
        ) d
    ''', [owner_id, owner_id]).fetchone()[0]
    
    # 计算总页数
    total_pages = (total_records + per_page - 1) // per_page
    
    # 获取当前页的记录
    records = db.execute('''
        WITH all_dates AS (
            SELECT DISTINCT date 
            FROM (
                SELECT date FROM morning_bloodpressure_records WHERE owner_id = ?
                UNION
                SELECT date FROM night_bloodpressure_records WHERE owner_id = ?
            )
            ORDER BY date DESC
            LIMIT ? OFFSET ?
        )
        SELECT 
            d.date,
            strftime('%w', d.date) as day_of_week,
            m.morning_high,
            m.morning_low,
            n.night_high,
            n.night_low,
            c.average,
            c.risk,
            nt.notes
        FROM all_dates d
        LEFT JOIN morning_bloodpressure_records m 
            ON d.date = m.date AND m.owner_id = ?
        LEFT JOIN night_bloodpressure_records n 
            ON d.date = n.date AND n.owner_id = ?
        LEFT JOIN bloodpressure_calculation_records c 
            ON d.date = c.date AND c.owner_id = ?
        LEFT JOIN bloodpressure_notes_records nt 
            ON d.date = nt.date AND nt.owner_id = ?
        ORDER BY d.date DESC
    ''', [owner_id, owner_id, per_page, offset, owner_id, owner_id, owner_id, owner_id]).fetchall()
    
    return render_template('bloodpressure2detail.html',
                         records=records,
                         current_page=page,
                         total_pages=total_pages,
                         today=datetime.now().strftime('%Y-%m-%d'))

@app.route('/blood_pressure2_chart')
@login_required
def blood_pressure2_chart():
    owner_id = 2  # 血压监测-毛
    db = get_db()
    
    # 获取所有记录并合并
    records = db.execute('''
        WITH all_dates AS (
            SELECT DISTINCT date 
            FROM (
                SELECT date FROM morning_bloodpressure_records WHERE owner_id = ?
                UNION
                SELECT date FROM night_bloodpressure_records WHERE owner_id = ?
            )
            ORDER BY date ASC
        )
        SELECT 
            d.date,
            m.morning_high,
            m.morning_low,
            n.night_high,
            n.night_low,
            c.average
        FROM all_dates d
        LEFT JOIN morning_bloodpressure_records m 
            ON d.date = m.date AND m.owner_id = ?
        LEFT JOIN night_bloodpressure_records n 
            ON d.date = n.date AND n.owner_id = ?
        LEFT JOIN bloodpressure_calculation_records c 
            ON d.date = c.date AND c.owner_id = ?
    ''', [owner_id] * 5).fetchall()
    
    dates = []
    morning_high = []
    morning_low = []
    night_high = []
    night_low = []
    averages = []
    
    for record in records:
        try:
            if any([record['morning_high'], record['morning_low'], 
                   record['night_high'], record['night_low']]):
                dates.append(record['date'])
                morning_high.append(float(record['morning_high']) if record['morning_high'] else None)
                morning_low.append(float(record['morning_low']) if record['morning_low'] else None)
                night_high.append(float(record['night_high']) if record['night_high'] else None)
                night_low.append(float(record['night_low']) if record['night_low'] else None)
                
                if record['average']:
                    avg_parts = record['average'].split('/')
                    averages.append({
                        'high': float(avg_parts[0]),
                        'low': float(avg_parts[1])
                    })
                else:
                    averages.append(None)
        except (ValueError, TypeError, IndexError) as e:
            print(f"处理记录出错: {str(e)}")
            continue
    
    return render_template('bloodpressure2chart.html',
                         dates=dates,
                         morning_high=morning_high,
                         morning_low=morning_low,
                         night_high=night_high,
                         night_low=night_low,
                         averages=averages)

@app.route('/blood_pressure3_detail')
@login_required
def blood_pressure3_detail():
    page = request.args.get('page', 1, type=int)
    per_page = 10  # 每页显示10条记录
    offset = (page - 1) * per_page
    owner_id = 3  # 血压监测-祺
    
    db = get_db()
    
    # 获取总记录数
    total_records = db.execute('''
        SELECT COUNT(DISTINCT d.date) 
        FROM (
            SELECT date FROM morning_bloodpressure_records WHERE owner_id = ?
            UNION
            SELECT date FROM night_bloodpressure_records WHERE owner_id = ?
        ) d
    ''', [owner_id, owner_id]).fetchone()[0]
    
    # 计算总页数
    total_pages = (total_records + per_page - 1) // per_page
    
    # 获取当前页的记录
    records = db.execute('''
        WITH all_dates AS (
            SELECT DISTINCT date 
            FROM (
                SELECT date FROM morning_bloodpressure_records WHERE owner_id = ?
                UNION
                SELECT date FROM night_bloodpressure_records WHERE owner_id = ?
            )
            ORDER BY date DESC
            LIMIT ? OFFSET ?
        )
        SELECT 
            d.date,
            strftime('%w', d.date) as day_of_week,
            m.morning_high,
            m.morning_low,
            n.night_high,
            n.night_low,
            c.average,
            c.risk,
            nt.notes
        FROM all_dates d
        LEFT JOIN morning_bloodpressure_records m 
            ON d.date = m.date AND m.owner_id = ?
        LEFT JOIN night_bloodpressure_records n 
            ON d.date = n.date AND n.owner_id = ?
        LEFT JOIN bloodpressure_calculation_records c 
            ON d.date = c.date AND c.owner_id = ?
        LEFT JOIN bloodpressure_notes_records nt 
            ON d.date = nt.date AND nt.owner_id = ?
        ORDER BY d.date DESC
    ''', [owner_id, owner_id, per_page, offset, owner_id, owner_id, owner_id, owner_id]).fetchall()
    
    return render_template('bloodpressure3detail.html',
                         records=records,
                         current_page=page,
                         total_pages=total_pages,
                         today=datetime.now().strftime('%Y-%m-%d'))

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
    per_page = 10  # 每页显示10条记录
    offset = (page - 1) * per_page
    owner_id = 1  # 血压监测
    
    db = get_db()
    
    # 获取总记录数
    total_records = db.execute('''
        SELECT COUNT(DISTINCT d.date) 
        FROM (
            SELECT date FROM morning_bloodpressure_records WHERE owner_id = ?
            UNION
            SELECT date FROM night_bloodpressure_records WHERE owner_id = ?
        ) d
    ''', [owner_id, owner_id]).fetchone()[0]
    
    # 计算总页数
    total_pages = (total_records + per_page - 1) // per_page
    
    # 获取当前页的记录
    records = db.execute('''
        WITH all_dates AS (
            SELECT DISTINCT date 
            FROM (
                SELECT date FROM morning_bloodpressure_records WHERE owner_id = ?
                UNION
                SELECT date FROM night_bloodpressure_records WHERE owner_id = ?
            )
            ORDER BY date DESC
            LIMIT ? OFFSET ?
        )
        SELECT 
            d.date,
            strftime('%w', d.date) as day_of_week,
            m.morning_high,
            m.morning_low,
            n.night_high,
            n.night_low,
            c.average,
            c.risk,
            nt.notes
        FROM all_dates d
        LEFT JOIN morning_bloodpressure_records m 
            ON d.date = m.date AND m.owner_id = ?
        LEFT JOIN night_bloodpressure_records n 
            ON d.date = n.date AND n.owner_id = ?
        LEFT JOIN bloodpressure_calculation_records c 
            ON d.date = c.date AND c.owner_id = ?
        LEFT JOIN bloodpressure_notes_records nt 
            ON d.date = nt.date AND nt.owner_id = ?
        ORDER BY d.date DESC
    ''', [owner_id, owner_id, per_page, offset, owner_id, owner_id, owner_id, owner_id]).fetchall()
    
    return render_template('bloodpressuredetail.html',
                         records=records,
                         current_page=page,
                         total_pages=total_pages,
                         today=datetime.now().strftime('%Y-%m-%d'))

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

@app.route('/checkin_records')
@login_required
def checkin_records():
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    db = get_db()
    # 修改查询以按日期分组，获取每天最新的状态
    records = db.execute('''
        SELECT 
            date,
            day_of_week,
            MAX(checkin) as checkin_status,
            MAX(checkout) as checkout_status,
            SUM(income) as total_income,
            GROUP_CONCAT(notes, ' ') as all_notes
        FROM (
            SELECT 
                date,
                day_of_week,
                checkin,
                checkout,
                income,
                notes
            FROM checkin_records
            ORDER BY id DESC
        )
        GROUP BY date
        ORDER BY date DESC
        LIMIT ? OFFSET ?
    ''', [per_page, (page - 1) * per_page]).fetchall()
    
    # 获取总记录数（按天计算）
    total = db.execute('''
        SELECT COUNT(DISTINCT date) 
        FROM checkin_records
    ''').fetchone()[0]
    
    # 转换记录格式
    formatted_records = []
    for record in records:
        formatted_records.append({
            'date': record['date'],
            'checkin_time': '已签到' if record['checkin_status'] else '未签到',
            'checkout_time': '已签出' if record['checkout_status'] else '未签出',
            'income': record['total_income'] or 0,
            'notes': record['all_notes'].strip() if record['all_notes'] else ''
        })
    
    db.close()
    
    total_pages = (total + per_page - 1) // per_page
    
    return render_template('checkinrecords.html',
                         records=formatted_records,
                         current_page=page,
                         total_pages=total_pages)

@app.route('/calculate_income_range')
@login_required
def calculate_income_range():
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        if not start_date or not end_date:
            return jsonify({'error': '缺少日期参数', 'total': 0})
        
        db = get_db()
        # 修改查询以根据签到签出状态计算收入
        result = db.execute('''
            WITH daily_records AS (
                SELECT 
                    date,
                    MAX(checkin) as has_checkin,
                    MAX(checkout) as has_checkout
                FROM checkin_records 
                WHERE date BETWEEN ? AND ?
                GROUP BY date
            )
            SELECT SUM(
                CASE 
                    WHEN has_checkin = 1 AND has_checkout = 1 THEN 75 
                    ELSE 0 
                END
            ) as total
            FROM daily_records
        ''', [start_date, end_date]).fetchone()
        
        total = result['total'] if result['total'] is not None else 0
        db.close()
        
        return jsonify({
            'success': True,
            'total': total,
            'start_date': start_date,
            'end_date': end_date
        })
    except Exception as e:
        print(f"计算收入范围时出错: {str(e)}")
        return jsonify({
            'error': str(e),
            'total': 0
        }), 500

@app.route('/download_blood_pressure_table')
@login_required
def download_blood_pressure_table():
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        owner_id = 1  # 血压监测
        
        db = get_db()
        records = db.execute('''
            WITH all_dates AS (
                SELECT DISTINCT date 
                FROM (
                    SELECT date FROM morning_bloodpressure_records WHERE owner_id = ?
                    UNION
                    SELECT date FROM night_bloodpressure_records WHERE owner_id = ?
                )
                WHERE date BETWEEN ? AND ?
                ORDER BY date DESC
            )
            SELECT 
                d.date,
                strftime('%w', d.date) as day_of_week,
                m.morning_high,
                m.morning_low,
                n.night_high,
                n.night_low,
                c.average,
                c.risk,
                nt.notes
            FROM all_dates d
            LEFT JOIN morning_bloodpressure_records m 
                ON d.date = m.date AND m.owner_id = ?
            LEFT JOIN night_bloodpressure_records n 
                ON d.date = n.date AND n.owner_id = ?
            LEFT JOIN bloodpressure_calculation_records c 
                ON d.date = c.date AND c.owner_id = ?
            LEFT JOIN bloodpressure_notes_records nt 
                ON d.date = nt.date AND nt.owner_id = ?
        ''', [owner_id, owner_id, start_date, end_date, owner_id, owner_id, owner_id, owner_id]).fetchall()
        
        # 创建Excel文件
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output)
        worksheet = workbook.add_worksheet('血压记录')
        
        # 设置列宽
        worksheet.set_column('A:A', 12)  # 日期
        worksheet.set_column('B:B', 8)   # 星期
        worksheet.set_column('C:F', 10)  # 血压值
        worksheet.set_column('G:G', 12)  # 日均值
        worksheet.set_column('H:H', 8)   # 风险等级
        worksheet.set_column('I:I', 30)  # 备注
        
        # 添加标题格式
        title_format = workbook.add_format({
            'bold': True,
            'align': 'center',
            'valign': 'vcenter',
            'bg_color': '#f8f9fa',
            'border': 1
        })
        
        # 添加数据格式
        data_format = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter',
            'border': 1
        })
        
        # 写入表头
        headers = ['日期', '星期', '晨间收缩压', '晨间舒张压', 
                  '晚间收缩压', '晚间舒张压', '日均血压', '风险等级', '备注']
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, title_format)
        
        # 写入数据
        weekday_map = {'0': '星期日', '1': '星期一', '2': '星期二', 
                      '3': '星期三', '4': '星期四', '5': '星期五', '6': '星期六'}
        
        for row, record in enumerate(records, 1):
            worksheet.write(row, 0, record['date'], data_format)
            worksheet.write(row, 1, weekday_map.get(record['day_of_week'], ''), data_format)
            worksheet.write(row, 2, record['morning_high'], data_format)
            worksheet.write(row, 3, record['morning_low'], data_format)
            worksheet.write(row, 4, record['night_high'], data_format)
            worksheet.write(row, 5, record['night_low'], data_format)
            worksheet.write(row, 6, record['average'] if record['average'] else '-', data_format)
            worksheet.write(row, 7, record['risk'] if record['risk'] else '-', data_format)
            worksheet.write(row, 8, record['notes'] if record['notes'] else '', data_format)
        
        workbook.close()
        output.seek(0)
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'血压记录_{start_date}至{end_date}.xlsx'
        )
        
    except Exception as e:
        print(f"下载血压记录表格时出错: {str(e)}")
        flash('下载表格时出错', 'error')
        return redirect(url_for('blood_pressure_detail'))

@app.route('/download_blood_pressure3_table')
@login_required
def download_blood_pressure3_table():
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        owner_id = 3  # 血压监测-祺
        
        db = get_db()
        records = db.execute('''
            WITH all_dates AS (
                SELECT DISTINCT date 
                FROM (
                    SELECT date FROM morning_bloodpressure_records WHERE owner_id = ?
                    UNION
                    SELECT date FROM night_bloodpressure_records WHERE owner_id = ?
                )
                WHERE date BETWEEN ? AND ?
                ORDER BY date DESC
            )
            SELECT 
                d.date,
                strftime('%w', d.date) as day_of_week,
                m.morning_high,
                m.morning_low,
                n.night_high,
                n.night_low,
                c.average,
                c.risk,
                nt.notes
            FROM all_dates d
            LEFT JOIN morning_bloodpressure_records m 
                ON d.date = m.date AND m.owner_id = ?
            LEFT JOIN night_bloodpressure_records n 
                ON d.date = n.date AND n.owner_id = ?
            LEFT JOIN bloodpressure_calculation_records c 
                ON d.date = c.date AND c.owner_id = ?
            LEFT JOIN bloodpressure_notes_records nt 
                ON d.date = nt.date AND nt.owner_id = ?
        ''', [owner_id, owner_id, start_date, end_date, owner_id, owner_id, owner_id, owner_id]).fetchall()
        
        # 创建Excel文件
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output)
        worksheet = workbook.add_worksheet('血压记录')
        
        # 设置列宽
        worksheet.set_column('A:A', 12)  # 日期
        worksheet.set_column('B:B', 8)   # 星期
        worksheet.set_column('C:F', 10)  # 血压值
        worksheet.set_column('G:G', 12)  # 日均值
        worksheet.set_column('H:H', 8)   # 风险等级
        worksheet.set_column('I:I', 30)  # 备注
        
        # 添加标题格式
        title_format = workbook.add_format({
            'bold': True,
            'align': 'center',
            'valign': 'vcenter',
            'bg_color': '#f8f9fa',
            'border': 1
        })
        
        # 添加数据格式
        data_format = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter',
            'border': 1
        })
        
        # 写入表头
        headers = ['日期', '星期', '晨间收缩压', '晨间舒张压', 
                  '晚间收缩压', '晚间舒张压', '日均血压', '风险等级', '备注']
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, title_format)
        
        # 写入数据
        weekday_map = {'0': '星期日', '1': '星期一', '2': '星期二', 
                      '3': '星期三', '4': '星期四', '5': '星期五', '6': '星期六'}
        
        for row, record in enumerate(records, 1):
            worksheet.write(row, 0, record['date'], data_format)
            worksheet.write(row, 1, weekday_map.get(record['day_of_week'], ''), data_format)
            worksheet.write(row, 2, record['morning_high'], data_format)
            worksheet.write(row, 3, record['morning_low'], data_format)
            worksheet.write(row, 4, record['night_high'], data_format)
            worksheet.write(row, 5, record['night_low'], data_format)
            worksheet.write(row, 6, record['average'] if record['average'] else '-', data_format)
            worksheet.write(row, 7, record['risk'] if record['risk'] else '-', data_format)
            worksheet.write(row, 8, record['notes'] if record['notes'] else '', data_format)
        
        workbook.close()
        output.seek(0)
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'血压记录_祺_{start_date}至{end_date}.xlsx'
        )
        
    except Exception as e:
        print(f"下载血压记录表格时出错: {str(e)}")
        flash('下载表格时出错', 'error')
        return redirect(url_for('blood_pressure3_detail'))

@app.route('/blood_pressure3_average')
@login_required
def blood_pressure3_average():
    owner_id = 3  # 血压监测-祺
    end_date = request.args.get('end_date', datetime.now().strftime('%Y-%m-%d'))
    start_date = request.args.get('start_date', 
                                (datetime.strptime(end_date, '%Y-%m-%d') - timedelta(days=30)).strftime('%Y-%m-%d'))
    
    db = get_db()
    
    # 获取指定日期范围的统计数据
    stats = db.execute('''
        WITH date_range AS (
            SELECT DISTINCT date 
            FROM (
                SELECT date FROM morning_bloodpressure_records WHERE owner_id = ?
                UNION
                SELECT date FROM night_bloodpressure_records WHERE owner_id = ?
            )
            WHERE date BETWEEN ? AND ?
        )
        SELECT 
            AVG(m.morning_high) as morning_high_avg,
            AVG(m.morning_low) as morning_low_avg,
            AVG(n.night_high) as night_high_avg,
            AVG(n.night_low) as night_low_avg,
            COUNT(DISTINCT d.date) as total_days,
            AVG(CASE 
                WHEN m.morning_high IS NOT NULL AND n.night_high IS NOT NULL 
                THEN (m.morning_high + n.night_high) / 2
                WHEN m.morning_high IS NOT NULL THEN m.morning_high
                WHEN n.night_high IS NOT NULL THEN n.night_high
            END) as daily_high_avg,
            AVG(CASE 
                WHEN m.morning_low IS NOT NULL AND n.night_low IS NOT NULL 
                THEN (m.morning_low + n.night_low) / 2
                WHEN m.morning_low IS NOT NULL THEN m.morning_low
                WHEN n.night_low IS NOT NULL THEN n.night_low
            END) as daily_low_avg
        FROM date_range d
        LEFT JOIN morning_bloodpressure_records m 
            ON d.date = m.date AND m.owner_id = ?
        LEFT JOIN night_bloodpressure_records n 
            ON d.date = n.date AND n.owner_id = ?
    ''', [owner_id, owner_id, start_date, end_date, owner_id, owner_id]).fetchone()
    
    # 计算平均值
    averages = {
        'morning_high': round(stats['morning_high_avg'], 1) if stats['morning_high_avg'] else 0,
        'morning_low': round(stats['morning_low_avg'], 1) if stats['morning_low_avg'] else 0,
        'night_high': round(stats['night_high_avg'], 1) if stats['night_high_avg'] else 0,
        'night_low': round(stats['night_low_avg'], 1) if stats['night_low_avg'] else 0,
        'daily_high': round(stats['daily_high_avg'], 1) if stats['daily_high_avg'] else 0,
        'daily_low': round(stats['daily_low_avg'], 1) if stats['daily_low_avg'] else 0
    }
    
    # 计算总体风险等级
    risk = calculate_risk(averages['daily_high'], averages['daily_low'])
    
    return render_template('bloodpressure3average.html',
                         averages=averages,
                         days=stats['total_days'],
                         start_date=start_date,
                         end_date=end_date,
                         risk=risk)

@app.route('/blood_pressure_average')
@login_required
def blood_pressure_average():
    owner_id = 1  # 血压监测
    end_date = request.args.get('end_date', datetime.now().strftime('%Y-%m-%d'))
    start_date = request.args.get('start_date', 
                                (datetime.strptime(end_date, '%Y-%m-%d') - timedelta(days=30)).strftime('%Y-%m-%d'))
    
    db = get_db()
    
    # 获取指定日期范围的统计数据
    stats = db.execute('''
        WITH date_range AS (
            SELECT DISTINCT date 
            FROM (
                SELECT date FROM morning_bloodpressure_records WHERE owner_id = ?
                UNION
                SELECT date FROM night_bloodpressure_records WHERE owner_id = ?
            )
            WHERE date BETWEEN ? AND ?
        )
        SELECT 
            AVG(m.morning_high) as morning_high_avg,
            AVG(m.morning_low) as morning_low_avg,
            AVG(n.night_high) as night_high_avg,
            AVG(n.night_low) as night_low_avg,
            COUNT(DISTINCT d.date) as total_days,
            AVG(CASE 
                WHEN m.morning_high IS NOT NULL AND n.night_high IS NOT NULL 
                THEN (m.morning_high + n.night_high) / 2
                WHEN m.morning_high IS NOT NULL THEN m.morning_high
                WHEN n.night_high IS NOT NULL THEN n.night_high
            END) as daily_high_avg,
            AVG(CASE 
                WHEN m.morning_low IS NOT NULL AND n.night_low IS NOT NULL 
                THEN (m.morning_low + n.night_low) / 2
                WHEN m.morning_low IS NOT NULL THEN m.morning_low
                WHEN n.night_low IS NOT NULL THEN n.night_low
            END) as daily_low_avg
        FROM date_range d
        LEFT JOIN morning_bloodpressure_records m 
            ON d.date = m.date AND m.owner_id = ?
        LEFT JOIN night_bloodpressure_records n 
            ON d.date = n.date AND n.owner_id = ?
    ''', [owner_id, owner_id, start_date, end_date, owner_id, owner_id]).fetchone()
    
    # 计算平均值
    averages = {
        'morning_high': round(stats['morning_high_avg'], 1) if stats['morning_high_avg'] else 0,
        'morning_low': round(stats['morning_low_avg'], 1) if stats['morning_low_avg'] else 0,
        'night_high': round(stats['night_high_avg'], 1) if stats['night_high_avg'] else 0,
        'night_low': round(stats['night_low_avg'], 1) if stats['night_low_avg'] else 0,
        'daily_high': round(stats['daily_high_avg'], 1) if stats['daily_high_avg'] else 0,
        'daily_low': round(stats['daily_low_avg'], 1) if stats['daily_low_avg'] else 0
    }
    
    # 计算总体风险等级
    risk = calculate_risk(averages['daily_high'], averages['daily_low'])
    
    return render_template('bloodpressureaverage.html',
                         averages=averages,
                         days=stats['total_days'],
                         start_date=start_date,
                         end_date=end_date,
                         risk=risk)

@app.route('/blood_pressure_chart')
@login_required
def blood_pressure_chart():
    owner_id = 1  # 血压监测
    db = get_db()
    
    # 获取所有记录并合并
    records = db.execute('''
        WITH all_dates AS (
            SELECT DISTINCT date 
            FROM (
                SELECT date FROM morning_bloodpressure_records WHERE owner_id = ?
                UNION
                SELECT date FROM night_bloodpressure_records WHERE owner_id = ?
            )
            ORDER BY date ASC
        )
        SELECT 
            d.date,
            m.morning_high,
            m.morning_low,
            n.night_high,
            n.night_low,
            c.average
        FROM all_dates d
        LEFT JOIN morning_bloodpressure_records m 
            ON d.date = m.date AND m.owner_id = ?
        LEFT JOIN night_bloodpressure_records n 
            ON d.date = n.date AND n.owner_id = ?
        LEFT JOIN bloodpressure_calculation_records c 
            ON d.date = c.date AND c.owner_id = ?
    ''', [owner_id] * 5).fetchall()
    
    dates = []
    morning_high = []
    morning_low = []
    night_high = []
    night_low = []
    averages = []
    
    for record in records:
        try:
            if any([record['morning_high'], record['morning_low'], 
                   record['night_high'], record['night_low']]):
                dates.append(record['date'])
                morning_high.append(float(record['morning_high']) if record['morning_high'] else None)
                morning_low.append(float(record['morning_low']) if record['morning_low'] else None)
                night_high.append(float(record['night_high']) if record['night_high'] else None)
                night_low.append(float(record['night_low']) if record['night_low'] else None)
                
                if record['average']:
                    avg_parts = record['average'].split('/')
                    averages.append({
                        'high': float(avg_parts[0]),
                        'low': float(avg_parts[1])
                    })
                else:
                    averages.append(None)
        except (ValueError, TypeError, IndexError) as e:
            print(f"处理记录出错: {str(e)}")
            continue
    
    return render_template('bloodpressurechart.html',
                         dates=dates,
                         morning_high=morning_high,
                         morning_low=morning_low,
                         night_high=night_high,
                         night_low=night_low,
                         averages=averages)

@app.route('/blood_pressure3_chart')
@login_required
def blood_pressure3_chart():
    owner_id = 3  # 血压监测-祺
    db = get_db()
    
    # 获取所有记录并合并
    records = db.execute('''
        WITH all_dates AS (
            SELECT DISTINCT date 
            FROM (
                SELECT date FROM morning_bloodpressure_records WHERE owner_id = ?
                UNION
                SELECT date FROM night_bloodpressure_records WHERE owner_id = ?
            )
            ORDER BY date ASC
        )
        SELECT 
            d.date,
            m.morning_high,
            m.morning_low,
            n.night_high,
            n.night_low,
            c.average
        FROM all_dates d
        LEFT JOIN morning_bloodpressure_records m 
            ON d.date = m.date AND m.owner_id = ?
        LEFT JOIN night_bloodpressure_records n 
            ON d.date = n.date AND n.owner_id = ?
        LEFT JOIN bloodpressure_calculation_records c 
            ON d.date = c.date AND c.owner_id = ?
    ''', [owner_id] * 5).fetchall()
    
    dates = []
    morning_high = []
    morning_low = []
    night_high = []
    night_low = []
    averages = []
    
    for record in records:
        try:
            if any([record['morning_high'], record['morning_low'], 
                   record['night_high'], record['night_low']]):
                dates.append(record['date'])
                morning_high.append(float(record['morning_high']) if record['morning_high'] else None)
                morning_low.append(float(record['morning_low']) if record['morning_low'] else None)
                night_high.append(float(record['night_high']) if record['night_high'] else None)
                night_low.append(float(record['night_low']) if record['night_low'] else None)
                
                if record['average']:
                    avg_parts = record['average'].split('/')
                    averages.append({
                        'high': float(avg_parts[0]),
                        'low': float(avg_parts[1])
                    })
                else:
                    averages.append(None)
        except (ValueError, TypeError, IndexError) as e:
            print(f"处理记录出错: {str(e)}")
            continue
    
    return render_template('bloodpressure3chart.html',
                         dates=dates,
                         morning_high=morning_high,
                         morning_low=morning_low,
                         night_high=night_high,
                         night_low=night_low,
                         averages=averages)

@app.route('/blood_pressure2_average')
@login_required
def blood_pressure2_average():
    owner_id = 2  # 血压监测-毛
    end_date = request.args.get('end_date', datetime.now().strftime('%Y-%m-%d'))
    start_date = request.args.get('start_date', 
                                (datetime.strptime(end_date, '%Y-%m-%d') - timedelta(days=30)).strftime('%Y-%m-%d'))
    
    db = get_db()
    
    # 获取指定日期范围的统计数据
    stats = db.execute('''
        WITH date_range AS (
            SELECT DISTINCT date 
            FROM (
                SELECT date FROM morning_bloodpressure_records WHERE owner_id = ?
                UNION
                SELECT date FROM night_bloodpressure_records WHERE owner_id = ?
            )
            WHERE date BETWEEN ? AND ?
        )
        SELECT 
            AVG(m.morning_high) as morning_high_avg,
            AVG(m.morning_low) as morning_low_avg,
            AVG(n.night_high) as night_high_avg,
            AVG(n.night_low) as night_low_avg,
            COUNT(DISTINCT d.date) as total_days,
            AVG(CASE 
                WHEN m.morning_high IS NOT NULL AND n.night_high IS NOT NULL 
                THEN (m.morning_high + n.night_high) / 2
                WHEN m.morning_high IS NOT NULL THEN m.morning_high
                WHEN n.night_high IS NOT NULL THEN n.night_high
            END) as daily_high_avg,
            AVG(CASE 
                WHEN m.morning_low IS NOT NULL AND n.night_low IS NOT NULL 
                THEN (m.morning_low + n.night_low) / 2
                WHEN m.morning_low IS NOT NULL THEN m.morning_low
                WHEN n.night_low IS NOT NULL THEN n.night_low
            END) as daily_low_avg
        FROM date_range d
        LEFT JOIN morning_bloodpressure_records m 
            ON d.date = m.date AND m.owner_id = ?
        LEFT JOIN night_bloodpressure_records n 
            ON d.date = n.date AND n.owner_id = ?
    ''', [owner_id, owner_id, start_date, end_date, owner_id, owner_id]).fetchone()
    
    # 计算平均值
    averages = {
        'morning_high': round(stats['morning_high_avg'], 1) if stats['morning_high_avg'] else 0,
        'morning_low': round(stats['morning_low_avg'], 1) if stats['morning_low_avg'] else 0,
        'night_high': round(stats['night_high_avg'], 1) if stats['night_high_avg'] else 0,
        'night_low': round(stats['night_low_avg'], 1) if stats['night_low_avg'] else 0,
        'daily_high': round(stats['daily_high_avg'], 1) if stats['daily_high_avg'] else 0,
        'daily_low': round(stats['daily_low_avg'], 1) if stats['daily_low_avg'] else 0
    }
    
    # 计算总体风险等级
    risk = calculate_risk(averages['daily_high'], averages['daily_low'])
    
    return render_template('bloodpressure2average.html',
                         averages=averages,
                         days=stats['total_days'],
                         start_date=start_date,
                         end_date=end_date,
                         risk=risk)

@app.route('/download_blood_pressure2_table')
@login_required
def download_blood_pressure2_table():
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        owner_id = 2  # 血压监测-毛
        
        db = get_db()
        records = db.execute('''
            WITH all_dates AS (
                SELECT DISTINCT date 
                FROM (
                    SELECT date FROM morning_bloodpressure_records WHERE owner_id = ?
                    UNION
                    SELECT date FROM night_bloodpressure_records WHERE owner_id = ?
                )
                WHERE date BETWEEN ? AND ?
                ORDER BY date DESC
            )
            SELECT 
                d.date,
                strftime('%w', d.date) as day_of_week,
                m.morning_high,
                m.morning_low,
                n.night_high,
                n.night_low,
                c.average,
                c.risk,
                nt.notes
            FROM all_dates d
            LEFT JOIN morning_bloodpressure_records m 
                ON d.date = m.date AND m.owner_id = ?
            LEFT JOIN night_bloodpressure_records n 
                ON d.date = n.date AND n.owner_id = ?
            LEFT JOIN bloodpressure_calculation_records c 
                ON d.date = c.date AND c.owner_id = ?
            LEFT JOIN bloodpressure_notes_records nt 
                ON d.date = nt.date AND nt.owner_id = ?
        ''', [owner_id, owner_id, start_date, end_date, owner_id, owner_id, owner_id, owner_id]).fetchall()
        
        # 创建Excel文件
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output)
        worksheet = workbook.add_worksheet('血压记录')
        
        # 设置列宽
        worksheet.set_column('A:A', 12)  # 日期
        worksheet.set_column('B:B', 8)   # 星期
        worksheet.set_column('C:F', 10)  # 血压值
        worksheet.set_column('G:G', 12)  # 日均值
        worksheet.set_column('H:H', 8)   # 风险等级
        worksheet.set_column('I:I', 30)  # 备注
        
        # 添加标题格式
        title_format = workbook.add_format({
            'bold': True,
            'align': 'center',
            'valign': 'vcenter',
            'bg_color': '#f8f9fa',
            'border': 1
        })
        
        # 添加数据格式
        data_format = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter',
            'border': 1
        })
        
        # 写入表头
        headers = ['日期', '星期', '晨间收缩压', '晨间舒张压', 
                  '晚间收缩压', '晚间舒张压', '日均血压', '风险等级', '备注']
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, title_format)
        
        # 写入数据
        weekday_map = {'0': '星期日', '1': '星期一', '2': '星期二', 
                      '3': '星期三', '4': '星期四', '5': '星期五', '6': '星期六'}
        
        for row, record in enumerate(records, 1):
            worksheet.write(row, 0, record['date'], data_format)
            worksheet.write(row, 1, weekday_map.get(record['day_of_week'], ''), data_format)
            worksheet.write(row, 2, record['morning_high'], data_format)
            worksheet.write(row, 3, record['morning_low'], data_format)
            worksheet.write(row, 4, record['night_high'], data_format)
            worksheet.write(row, 5, record['night_low'], data_format)
            worksheet.write(row, 6, record['average'] if record['average'] else '-', data_format)
            worksheet.write(row, 7, record['risk'] if record['risk'] else '-', data_format)
            worksheet.write(row, 8, record['notes'] if record['notes'] else '', data_format)
        
        workbook.close()
        output.seek(0)
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'血压记录_毛_{start_date}至{end_date}.xlsx'
        )
        
    except Exception as e:
        print(f"下载血压记录表格时出错: {str(e)}")
        flash('下载表格时出错', 'error')
        return redirect(url_for('blood_pressure2_detail'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

