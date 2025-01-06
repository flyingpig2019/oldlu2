CREATE TABLE IF NOT EXISTS medicine_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    day_of_week TEXT NOT NULL,
    medicine_taken BOOLEAN NOT NULL,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS checkin_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    day_of_week TEXT NOT NULL,
    checkin BOOLEAN NOT NULL,
    checkout BOOLEAN NOT NULL,
    notes TEXT,
    income DECIMAL(10,2)
);

CREATE TABLE IF NOT EXISTS bloodpressure_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    day_of_week TEXT NOT NULL,
    morning_high INTEGER,
    morning_low INTEGER,
    afternoon_high INTEGER,
    afternoon_low INTEGER,
    notes TEXT,
    today_average TEXT,
    risk TEXT
); 