import sqlite3

def create_database():
    conn = sqlite3.connect('monitor.db')
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
    
    # 创建bloodpressure3_records表（为祺）
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

if __name__ == '__main__':
    create_database() 