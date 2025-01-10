import sqlite3

def create_tables():
    """创建所有必要的数据表"""
    conn = sqlite3.connect('monitor.db')
    cursor = conn.cursor()
    
    # 创建早间血压记录表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS morning_bloodpressure_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            day_of_week TEXT NOT NULL,
            owner_id INTEGER NOT NULL,
            morning_high REAL,
            morning_low REAL,
            UNIQUE(date, owner_id)
        )
    ''')
    
    # 创建晚间血压记录表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS night_bloodpressure_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            day_of_week TEXT NOT NULL,
            owner_id INTEGER NOT NULL,
            night_high REAL,
            night_low REAL,
            UNIQUE(date, owner_id)
        )
    ''')
    
    # 创建血压计算记录表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bloodpressure_calculation_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            day_of_week TEXT NOT NULL,
            owner_id INTEGER NOT NULL,
            average TEXT,
            risk TEXT,
            UNIQUE(date, owner_id)
        )
    ''')
    
    # 创建血压备注记录表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bloodpressure_notes_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            day_of_week TEXT NOT NULL,
            owner_id INTEGER NOT NULL,
            notes TEXT,
            UNIQUE(date, owner_id)
        )
    ''')
    
    # 创建签到记录表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS checkin_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            checkin INTEGER DEFAULT 0,
            checkout INTEGER DEFAULT 0,
            income INTEGER DEFAULT 0,
            UNIQUE(date)
        )
    ''')
    
    conn.commit()
    conn.close()

if __name__ == '__main__':
    create_tables()
    print("数据表创建完成!") 