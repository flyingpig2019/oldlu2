import sqlite3

def create_tables():
    """创建所需的表"""
    sql_commands = [
        '''CREATE TABLE IF NOT EXISTS bloodpressure2_records
           (id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            day_of_week TEXT NOT NULL,
            morning_high INTEGER,
            morning_low INTEGER,
            afternoon_high INTEGER,
            afternoon_low INTEGER,
            notes TEXT,
            today_average TEXT,
            risk TEXT)''',
            
        '''CREATE TABLE IF NOT EXISTS bloodpressure3_records
           (id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            day_of_week TEXT NOT NULL,
            morning_high INTEGER,
            morning_low INTEGER,
            afternoon_high INTEGER,
            afternoon_low INTEGER,
            notes TEXT,
            today_average TEXT,
            risk TEXT)'''
    ]
    
    conn = sqlite3.connect('monitor.db')
    cursor = conn.cursor()
    
    for command in sql_commands:
        cursor.execute(command)
    
    conn.commit()
    conn.close()
    print("表创建成功")

if __name__ == "__main__":
    create_tables() 