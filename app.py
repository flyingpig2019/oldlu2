from flask import Flask, render_template, request, redirect, url_for, session, send_file
from datetime import datetime, timedelta
import sqlite3
import os
import subprocess
import logging
from dotenv import load_dotenv
from functools import wraps
from calendar import monthcalendar
from github_utils import push_db_updates
import xlsxwriter
import io

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
    return render_template('landing.html', current_date=datetime.now().strftime('%Y-%m-%d'))

def get_db():
    conn = sqlite3.connect('monitor.db')
    conn.row_factory = sqlite3.Row
    return conn

def get_chinese_weekday(date_str):
    english_weekday = datetime.strptime(date_str, '%Y-%m-%d').strftime('%A')
    return WEEKDAYS[english_weekday]

@app.route('/add_medicine_record', methods=['POST'])
@login_required
def add_medicine_record():
    date = request.form['date']
    medicine_taken = 'medicine_taken' in request.form
    notes = request.form.get('notes', '')
    day_of_week = get_chinese_weekday(date)
    
    db = get_db()
    db.execute('INSERT INTO medicine_records (date, day_of_week, medicine_taken, notes) VALUES (?, ?, ?, ?)',
               [date, day_of_week, medicine_taken, notes])
    db.commit()
    db.close()
    push_db_updates()
    return redirect(url_for('landing'))

@app.route('/add_checkin_record', methods=['POST'])
@login_required
def add_checkin_record():
    date = request.form['date']
    notes = request.form.get('notes', '')
    day_of_week = get_chinese_weekday(date)
    
    db = get_db()
    existing = db.execute('SELECT * FROM checkin_records WHERE date = ?', [date]).fetchone()
    
    if 'checkin_submit' in request.form:
        checkin = 'checkin' in request.form
        if existing:
            db.execute('''UPDATE checkin_records 
                         SET checkin = ?, notes = ?
                         WHERE date = ?''', [checkin, notes, date])
        else:
            db.execute('''INSERT INTO checkin_records 
                         (date, day_of_week, checkin, checkout, notes, income)
                         VALUES (?, ?, ?, ?, ?, ?)''',
                      [date, day_of_week, checkin, False, notes, 0.0])
    
    elif 'checkout_submit' in request.form:
        checkout = 'checkout' in request.form
        if existing:
            # 如果已经签到并且现在签退，添加收入
            income = 75.0 if existing['checkin'] and checkout else 0.0
            db.execute('''UPDATE checkin_records 
                         SET checkout = ?, notes = ?, income = ?
                         WHERE date = ?''', [checkout, notes, income, date])
        else:
            db.execute('''INSERT INTO checkin_records 
                         (date, day_of_week, checkin, checkout, notes, income)
                         VALUES (?, ?, ?, ?, ?, ?)''',
                      [date, day_of_week, False, checkout, notes, 0.0])
    
    db.commit()
    db.close()
    push_db_updates()
    return redirect(url_for('landing'))

@app.route('/add_blood_pressure', methods=['POST'])
@login_required
def add_blood_pressure():
    date = request.form['date']
    day_of_week = get_chinese_weekday(date)
    db = get_db()
    
    if 'morning_submit' in request.form:
        morning_high = request.form.get('morning_high', 0)
        morning_low = request.form.get('morning_low', 0)
        
        # 检查是否已存在记录
        existing = db.execute('SELECT * FROM bloodpressure_records WHERE date = ?', [date]).fetchone()
        if existing:
            db.execute('''UPDATE bloodpressure_records 
                         SET morning_high = ?, morning_low = ?
                         WHERE date = ?''', [morning_high, morning_low, date])
        else:
            db.execute('''INSERT INTO bloodpressure_records 
                         (date, day_of_week, morning_high, morning_low)
                         VALUES (?, ?, ?, ?)''', [date, day_of_week, morning_high, morning_low])
    
    elif 'afternoon_submit' in request.form:
        afternoon_high = request.form.get('afternoon_high', 0)
        afternoon_low = request.form.get('afternoon_low', 0)
        
        existing = db.execute('SELECT * FROM bloodpressure_records WHERE date = ?', [date]).fetchone()
        if existing:
            db.execute('''UPDATE bloodpressure_records 
                         SET afternoon_high = ?, afternoon_low = ?
                         WHERE date = ?''', [afternoon_high, afternoon_low, date])
        else:
            db.execute('''INSERT INTO bloodpressure_records 
                         (date, day_of_week, afternoon_high, afternoon_low)
                         VALUES (?, ?, ?, ?)''', [date, day_of_week, afternoon_high, afternoon_low])
    
    # 更新平均值和风险等级
    record = db.execute('SELECT * FROM bloodpressure_records WHERE date = ?', [date]).fetchone()
    if record:
        high_avg = 0
        low_avg = 0
        count = 0
        
        if record['morning_high'] and record['morning_low']:
            high_avg += int(record['morning_high'])
            low_avg += int(record['morning_low'])
            count += 1
        
        if record['afternoon_high'] and record['afternoon_low']:
            high_avg += int(record['afternoon_high'])
            low_avg += int(record['afternoon_low'])
            count += 1
        
        if count > 0:
            high_avg = high_avg / count
            low_avg = low_avg / count
            today_average = f"H: {high_avg:.1f}, L: {low_avg:.1f}"
            
            # 计算风险等级
            risk = "good"
            if high_avg > 140 or low_avg > 85:
                risk = "high risk"
            elif high_avg > 130 or low_avg > 80:
                risk = "middle risk"
            elif high_avg > 120 or low_avg > 80:
                risk = "low risk"
            
            db.execute('''UPDATE bloodpressure_records 
                         SET today_average = ?, risk = ?
                         WHERE date = ?''', [today_average, risk, date])
    
    db.commit()
    db.close()
    push_db_updates()
    return redirect(url_for('landing'))

@app.route('/medicine_detail')
@login_required
def medicine_detail():
    # 获取当前页码，默认为1
    page = request.args.get('page', 1, type=int)
    per_page = 25  # 每页显示25条记录
    
    db = get_db()
    # 获取总记录数
    total_records = db.execute('SELECT COUNT(*) as count FROM medicine_records').fetchone()['count']
    
    # 计算总页数
    total_pages = (total_records + per_page - 1) // per_page
    
    # 获取当前页的记录
    offset = (page - 1) * per_page
    records = db.execute('''
        SELECT * FROM medicine_records 
        ORDER BY date DESC 
        LIMIT ? OFFSET ?
    ''', [per_page, offset]).fetchall()
    
    db.close()
    
    return render_template('medicinedetail.html', 
                         records=records,
                         current_page=page,
                         total_pages=total_pages)

@app.route('/medicine_calendar')
@login_required
def medicine_calendar():
    # 获取当前日期和上个月的日期
    today = datetime.now()
    last_month = today - timedelta(days=today.day + 1)
    
    # 获取最近两个月的记录
    db = get_db()
    records = db.execute('''
        SELECT date, medicine_taken 
        FROM medicine_records 
        WHERE date >= ? 
        ORDER BY date
    ''', [last_month.strftime('%Y-%m-%d')]).fetchall()
    
    # 计算本月服药率
    current_month = today.strftime('%Y-%m')
    current_month_records = db.execute('''
        SELECT COUNT(*) as total,
               SUM(CASE WHEN medicine_taken = 1 THEN 1 ELSE 0 END) as taken
        FROM medicine_records
        WHERE strftime('%Y-%m', date) = ?
    ''', [current_month]).fetchone()
    
    # 计算服药率
    total_days = current_month_records['total'] if current_month_records['total'] > 0 else 1
    medicine_taken = current_month_records['taken'] or 0
    medicine_rate = round((medicine_taken / total_days) * 100, 1)
    
    # 将记录转换为字典以便快速查找
    records_dict = {record['date']: record for record in records}
    
    # 准备两个月的日历数据
    months = []
    for month_date in [today, last_month]:
        year = month_date.year
        month = month_date.month
        
        # 获取月历
        cal = monthcalendar(year, month)
        
        # 准备周数据
        weeks = []
        for week in cal:
            week_data = []
            for day in week:
                if day == 0:
                    week_data.append({'empty': True})
                else:
                    date_str = f"{year}-{month:02d}-{day:02d}"
                    record = records_dict.get(date_str)
                    status = ''
                    if record:
                        status = 'success' if record['medicine_taken'] else 'fail'
                    
                    week_data.append({
                        'empty': False,
                        'day': day,
                        'record': record,
                        'status': status
                    })
            weeks.append(week_data)
        
        months.append({
            'year': year,
            'month': month,
            'weeks': weeks
        })
    
    db.close()
    return render_template('medicinecalendardetail.html', 
                         months=months,
                         medicine_rate=medicine_rate)

@app.route('/edit_medicine/<int:id>', methods=['POST'])
@login_required
def edit_medicine(id):
    medicine_taken = 'medicine_taken' in request.form
    notes = request.form.get('notes', '')
    
    db = get_db()
    db.execute('UPDATE medicine_records SET medicine_taken = ?, notes = ? WHERE id = ?',
               [medicine_taken, notes, id])
    db.commit()
    db.close()
    push_db_updates()
    return redirect(url_for('medicine_detail'))

@app.route('/delete_medicine/<int:id>')
@login_required
def delete_medicine(id):
    db = get_db()
    db.execute('DELETE FROM medicine_records WHERE id = ?', [id])
    db.commit()
    db.close()
    push_db_updates()
    return redirect(url_for('medicine_detail'))

@app.route('/checkin_detail')
@login_required
def checkin_detail():
    # 获取当前页码，默认为1
    page = request.args.get('page', 1, type=int)
    per_page = 25  # 每页显示25条记录
    
    db = get_db()
    # 获取总记录数
    total_records = db.execute('SELECT COUNT(*) as count FROM checkin_records').fetchone()['count']
    
    # 计算总页数
    total_pages = (total_records + per_page - 1) // per_page
    
    # 获取当前页的记录
    offset = (page - 1) * per_page
    records = db.execute('''
        SELECT * FROM checkin_records 
        ORDER BY date DESC 
        LIMIT ? OFFSET ?
    ''', [per_page, offset]).fetchall()
    
    db.close()
    
    return render_template('checkindetail.html', 
                         records=records,
                         current_page=page,
                         total_pages=total_pages)

@app.route('/checkin_calendar')
@login_required
def checkin_calendar():
    # 获取当前日期和上个月的日期
    today = datetime.now()
    last_month = today - timedelta(days=today.day + 1)
    
    # 获取最近两个月的记录
    db = get_db()
    records = db.execute('''
        SELECT date, checkin, checkout, income 
        FROM checkin_records 
        WHERE date >= ? 
        ORDER BY date
    ''', [last_month.strftime('%Y-%m-%d')]).fetchall()
    db.close()
    
    # 将记录转换为字典以便快速查找
    records_dict = {record['date']: record for record in records}
    
    # 准备两个月的日历数据
    months = []
    # 先处理当前月份，再处理上个月
    for month_date in [today, last_month]:
        year = month_date.year
        month = month_date.month
        
        # 获取月历
        cal = monthcalendar(year, month)
        
        # 准备周数据
        weeks = []
        for week in cal:
            week_data = []
            for day in week:
                if day == 0:
                    week_data.append({'empty': True})
                else:
                    date_str = f"{year}-{month:02d}-{day:02d}"
                    record = records_dict.get(date_str)
                    status = ''
                    if record:
                        status = 'complete' if record['checkin'] and record['checkout'] else 'incomplete'
                    
                    week_data.append({
                        'empty': False,
                        'day': day,
                        'record': record,
                        'status': status
                    })
            weeks.append(week_data)
        
        months.append({
            'year': year,
            'month': month,
            'weeks': weeks
        })
    
    return render_template('checkincalendardetail.html', months=months)

@app.route('/income_detail', methods=['GET', 'POST'])
@login_required
def income_detail():
    total_income = 0
    if request.method == 'POST':
        start_date = request.form['start_date']
        end_date = request.form['end_date']
        db = get_db()
        result = db.execute('''SELECT SUM(income) as total 
                              FROM checkin_records 
                              WHERE date BETWEEN ? AND ?''', 
                           [start_date, end_date]).fetchone()
        total_income = result['total'] if result['total'] else 0
        db.close()
    return render_template('incomedetail.html', total_income=total_income)

@app.route('/edit_checkin/<int:id>', methods=['POST'])
@login_required
def edit_checkin(id):
    checkin = 'checkin' in request.form
    checkout = 'checkout' in request.form
    notes = request.form.get('notes', '')
    income = 75.0 if checkin and checkout else 0.0
    
    db = get_db()
    db.execute('''UPDATE checkin_records 
                  SET checkin = ?, checkout = ?, notes = ?, income = ? 
                  WHERE id = ?''',
               [checkin, checkout, notes, income, id])
    db.commit()
    db.close()
    push_db_updates()
    return redirect(url_for('checkin_detail'))

@app.route('/delete_checkin/<int:id>')
@login_required
def delete_checkin(id):
    db = get_db()
    db.execute('DELETE FROM checkin_records WHERE id = ?', [id])
    db.commit()
    db.close()
    push_db_updates()
    return redirect(url_for('checkin_detail'))

@app.route('/blood_pressure_detail')
@login_required
def blood_pressure_detail():
    # 获取当前页码，默认为1
    page = request.args.get('page', 1, type=int)
    per_page = 25  # 每页显示25条记录
    
    db = get_db()
    # 获取总记录数
    total_records = db.execute('SELECT COUNT(*) as count FROM bloodpressure_records').fetchone()['count']
    
    # 计算总页数
    total_pages = (total_records + per_page - 1) // per_page
    
    # 获取当前页的记录
    offset = (page - 1) * per_page
    records = db.execute('''
        SELECT * FROM bloodpressure_records 
        ORDER BY date DESC 
        LIMIT ? OFFSET ?
    ''', [per_page, offset]).fetchall()
    
    db.close()
    
    return render_template('bloodpressuredetail.html', 
                         records=records,
                         current_page=page,
                         total_pages=total_pages)

@app.route('/blood_pressure_average', methods=['GET', 'POST'])
@login_required
def blood_pressure_average():
    average_high = 0
    average_low = 0
    if request.method == 'POST':
        start_date = request.form['start_date']
        end_date = request.form['end_date']
        db = get_db()
        result = db.execute('''
            SELECT 
                AVG(CASE 
                    WHEN morning_high IS NOT NULL AND afternoon_high IS NOT NULL 
                    THEN (morning_high + afternoon_high) / 2
                    WHEN morning_high IS NOT NULL THEN morning_high
                    ELSE afternoon_high
                END) as avg_high,
                AVG(CASE 
                    WHEN morning_low IS NOT NULL AND afternoon_low IS NOT NULL 
                    THEN (morning_low + afternoon_low) / 2
                    WHEN morning_low IS NOT NULL THEN morning_low
                    ELSE afternoon_low
                END) as avg_low
            FROM bloodpressure_records 
            WHERE date BETWEEN ? AND ?
        ''', [start_date, end_date]).fetchone()
        
        average_high = result['avg_high'] if result['avg_high'] else 0
        average_low = result['avg_low'] if result['avg_low'] else 0
        
        db.close()
    return render_template('bloodpressureaverage.html', 
                         average_high=average_high, 
                         average_low=average_low)

@app.route('/blood_pressure_chart', methods=['GET', 'POST'])
@login_required
def blood_pressure_chart():
    if request.method == 'POST':
        start_date = request.form['start_date']
        end_date = request.form['end_date']
        chart_type = request.form.get('chart_type', 'bar')
        
        db = get_db()
        records = db.execute('''
            SELECT date, 
                   COALESCE(morning_high, 0) as morning_high,
                   COALESCE(afternoon_high, 0) as afternoon_high,
                   COALESCE(morning_low, 0) as morning_low,
                   COALESCE(afternoon_low, 0) as afternoon_low,
                   risk
            FROM bloodpressure_records 
            WHERE date BETWEEN ? AND ?
            ORDER BY date
        ''', [start_date, end_date]).fetchall()
        
        dates = [record['date'] for record in records]
        high_values = []
        low_values = []
        risk_data = {'good': 0, 'low_risk': 0, 'middle_risk': 0, 'high_risk': 0}
        
        for record in records:
            # 计算高压和低压平均值
            high_count = low_count = 0
            high_sum = low_sum = 0
            
            if record['morning_high'] > 0:
                high_sum += record['morning_high']
                high_count += 1
            if record['afternoon_high'] > 0:
                high_sum += record['afternoon_high']
                high_count += 1
                
            if record['morning_low'] > 0:
                low_sum += record['morning_low']
                low_count += 1
            if record['afternoon_low'] > 0:
                low_sum += record['afternoon_low']
                low_count += 1
            
            high_avg = high_sum / high_count if high_count > 0 else 0
            low_avg = low_sum / low_count if low_count > 0 else 0
            
            high_values.append(high_avg)
            low_values.append(low_avg)
            
            # 统计风险等级
            risk = record['risk']
            if risk:
                risk_key = risk.replace(' ', '_')
                risk_data[risk_key] = risk_data.get(risk_key, 0) + 1
        
        show_pie = (chart_type == 'pie')
        
        return render_template('bloodpressurechart.html',
                             dates=dates,
                             high_values=high_values,
                             low_values=low_values,
                             risk_data=risk_data,
                             show_chart=True,
                             show_pie=show_pie,
                             chart_type=chart_type)
    
    return render_template('bloodpressurechart.html', show_chart=False)

@app.route('/edit_blood_pressure/<int:id>', methods=['POST'])
@login_required
def edit_blood_pressure(id):
    morning_high = request.form.get('morning_high', 0)
    morning_low = request.form.get('morning_low', 0)
    afternoon_high = request.form.get('afternoon_high', 0)
    afternoon_low = request.form.get('afternoon_low', 0)
    notes = request.form.get('notes', '')
    
    # 计算平均值和风险等级
    high_avg = 0
    low_avg = 0
    count = 0
    
    if morning_high and morning_low:
        high_avg += int(morning_high)
        low_avg += int(morning_low)
        count += 1
    
    if afternoon_high and afternoon_low:
        high_avg += int(afternoon_high)
        low_avg += int(afternoon_low)
        count += 1
    
    if count > 0:
        high_avg = high_avg / count
        low_avg = low_avg / count
        today_average = f"H: {high_avg:.1f}, L: {low_avg:.1f}"
        
        risk = "good"
        if high_avg > 140 or low_avg > 85:
            risk = "high risk"
        elif high_avg > 130 or low_avg > 80:
            risk = "middle risk"
        elif high_avg > 120 or low_avg > 80:
            risk = "low risk"
    
    db = get_db()
    db.execute('''UPDATE bloodpressure_records 
                  SET morning_high = ?, morning_low = ?, 
                      afternoon_high = ?, afternoon_low = ?,
                      notes = ?, today_average = ?, risk = ?
                  WHERE id = ?''',
               [morning_high, morning_low, afternoon_high, afternoon_low,
                notes, today_average, risk, id])
    db.commit()
    db.close()
    push_db_updates()
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

@app.route('/blood_pressure_print')
@login_required
def blood_pressure_print():
    return render_template('bloodpressureprint.html')

@app.route('/download_blood_pressure_table')
@login_required
def download_blood_pressure_table():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    db = get_db()
    records = db.execute('''
        SELECT date, day_of_week, 
               morning_high, morning_low, 
               afternoon_high, afternoon_low,
               today_average, risk, notes
        FROM bloodpressure_records 
        WHERE date BETWEEN ? AND ?
        ORDER BY date
    ''', [start_date, end_date]).fetchall()
    db.close()
    
    # 创建Excel文件
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output)
    worksheet = workbook.add_worksheet('血压记录')
    
    # 设置列宽
    worksheet.set_column('A:A', 12)  # 日期
    worksheet.set_column('B:B', 8)   # 星期
    worksheet.set_column('C:F', 10)  # 血压值
    worksheet.set_column('G:G', 15)  # 今日平均
    worksheet.set_column('H:H', 10)  # 风险等级
    worksheet.set_column('I:I', 30)  # 备注
    
    # 写入表头
    headers = ['日期', '星期', '早间高压', '早间低压', '晚间高压', 
              '晚间低压', '今日平均', '风险等级', '备注']
    for col, header in enumerate(headers):
        worksheet.write(0, col, header)
    
    # 写入数据
    for row, record in enumerate(records, 1):
        worksheet.write(row, 0, record['date'])
        worksheet.write(row, 1, record['day_of_week'])
        worksheet.write(row, 2, record['morning_high'])
        worksheet.write(row, 3, record['morning_low'])
        worksheet.write(row, 4, record['afternoon_high'])
        worksheet.write(row, 5, record['afternoon_low'])
        worksheet.write(row, 6, record['today_average'])
        worksheet.write(row, 7, record['risk'])
        worksheet.write(row, 8, record['notes'])
    
    workbook.close()
    output.seek(0)
    
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'血压记录_{start_date}至{end_date}.xlsx'
    )

@app.route('/download_blood_pressure_chart')
@login_required
def download_blood_pressure_chart():
    return redirect(url_for('blood_pressure_detail'))  # 暂时移除图表功能

# 这里将继续添加其他路由...

def init_db():
    # 检查数据库文件是否存在
    db_path = 'monitor.db'
    try:
        if os.path.exists(db_path):
            # 尝试连接现有数据库
            test_conn = sqlite3.connect(db_path)
            test_conn.close()
        else:
            # 如果数据库不存在，创建新的
            conn = sqlite3.connect(db_path)
            c = conn.cursor()
            
            # 创建medicine_records表
            c.execute('''CREATE TABLE IF NOT EXISTS medicine_records
                         (id INTEGER PRIMARY KEY AUTOINCREMENT,
                          date TEXT NOT NULL,
                          day_of_week TEXT NOT NULL,
                          medicine_taken BOOLEAN NOT NULL,
                          notes TEXT)''')
            
            # 创建checkin_records表
            c.execute('''CREATE TABLE IF NOT EXISTS checkin_records
                         (id INTEGER PRIMARY KEY AUTOINCREMENT,
                          date TEXT NOT NULL,
                          day_of_week TEXT NOT NULL,
                          checkin BOOLEAN NOT NULL,
                          checkout BOOLEAN NOT NULL,
                          notes TEXT,
                          income DECIMAL(10,2))''')
            
            # 创建bloodpressure_records表
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
            
            conn.commit()
            conn.close()
            print("数据库初始化成功")

    except sqlite3.DatabaseError as e:
        print(f"数据库错误: {str(e)}")
        # 如果数据库文件损坏，删除它并重新创建
        if os.path.exists(db_path):
            os.remove(db_path)
            print("删除损坏的数据库文件")
            # 递归调用以重新创建数据库
            init_db()
    except Exception as e:
        print(f"初始化数据库时出错: {str(e)}")

# 在应用启动时初始化数据库
init_db()

def push_to_github():
    """推送更改到GitHub仓库"""
    try:
        # 获取环境变量
        github_token = os.getenv('GITHUB_TOKEN')
        github_username = os.getenv('GITHUB_USERNAME')
        github_repo = os.getenv('GITHUB_REPO')
        
        print("\n=== 开始同步数据库到GitHub ===")
        
        # 构建远程仓库URL
        remote_url = f'https://{github_token}@github.com/{github_username}/{github_repo}'
        
        # 检查是否是Git仓库，如果不是则初始化
        if not os.path.exists('.git'):
            print("初始化Git仓库...")
            subprocess.run(['git', 'init'])
            
            # 设置远程仓库
            subprocess.run(['git', 'remote', 'add', 'origin', remote_url])
            
            # 拉取远程仓库的内容
            subprocess.run(['git', 'fetch', 'origin'])
            subprocess.run(['git', 'checkout', '-b', 'main', 'origin/main'])
        
        # 设置Git配置
        subprocess.run(['git', 'config', '--global', 'user.name', github_username])
        subprocess.run(['git', 'config', '--global', 'user.email', f'{github_username}@users.noreply.github.com'])
        
        # 只添加monitor.db文件
        subprocess.run(['git', 'add', 'monitor.db'])
        
        # 检查是否有更改需要提交
        status = subprocess.run(['git', 'status', '--porcelain', 'monitor.db'], 
                              capture_output=True, text=True).stdout.strip()
        
        if not status:
            print("数据库没有变化，无需更新")
            return
        
        # 提交更改
        commit_message = f"Update database at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        result = subprocess.run(['git', 'commit', '-m', commit_message], capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"错误: Git commit 失败 - {result.stderr}")
            return
        
        # 先拉取最新的更改
        subprocess.run(['git', 'pull', '--rebase', 'origin', 'main'])
        
        # 推送到远程仓库
        result = subprocess.run(['git', 'push', 'origin', 'main'], capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"错误: Git push 失败 - {result.stderr}")
            return
        
        print("=== 数据库同步成功 ===\n")
        
    except Exception as e:
        print(f"错误: 同步过程发生异常 - {str(e)}\n")

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000) 