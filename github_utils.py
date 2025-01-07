import os
from github import Github
from datetime import datetime
import base64
import shutil
import sqlite3

def init_db():
    """初始化数据库结构"""
    try:
        conn = sqlite3.connect('monitor.db')
        c = conn.cursor()
        
        # 创建所需的表（使用 IF NOT EXISTS）
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
        
        # 创建bloodpressure2_records表（毛的血压记录）
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
        
        # 创建bloodpressure3_records表（祺的血压记录）
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
        return True
    except Exception as e:
        print(f"初始化数据库失败: {str(e)}")
        return False

def backup_to_github():
    """将本地数据库备份到 GitHub"""
    try:
        token = os.getenv('GITHUB_TOKEN')
        repo_name = os.getenv('GITHUB_REPO')
        username = os.getenv('GITHUB_USERNAME')

        if not all([token, repo_name, username]):
            return False, "环境变量未正确设置"

        print("\n=== 开始备份数据库到GitHub ===")

        # 连接到GitHub
        g = Github(token)
        repo = g.get_user(username).get_repo(repo_name)

        # 读取当前数据库文件
        with open('monitor.db', 'rb') as f:
            content = f.read()
            content_b64 = base64.b64encode(content).decode()

        try:
            # 更新或创建数据库文件
            try:
                file = repo.get_contents("monitor.db")
                repo.update_file(
                    path="monitor.db",
                    message=f"Backup database: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    content=content_b64,
                    sha=file.sha
                )
            except:
                repo.create_file(
                    path="monitor.db",
                    message=f"Initial database backup: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    content=content_b64
                )

            print("=== 数据库备份成功 ===\n")
            return True, "数据库备份成功"

        except Exception as e:
            error_msg = f"备份数据库失败: {str(e)}"
            print(f"错误: {error_msg}")
            return False, error_msg

    except Exception as e:
        error_msg = f"备份过程发生异常: {str(e)}"
        print(f"错误: {error_msg}")
        return False, error_msg

def restore_from_github():
    """从 GitHub 恢复数据库（仅在本地数据库损坏或丢失时使用）"""
    try:
        token = os.getenv('GITHUB_TOKEN')
        repo_name = os.getenv('GITHUB_REPO')
        username = os.getenv('GITHUB_USERNAME')

        if not all([token, repo_name, username]):
            return False, "环境变量未正确设置"

        print("\n=== 开始从GitHub恢复数据库 ===")

        # 连接到GitHub
        g = Github(token)
        repo = g.get_user(username).get_repo(repo_name)

        try:
            # 获取数据库文件内容
            file = repo.get_contents("monitor.db")
            content = base64.b64decode(file.content)

            # 备份当前数据库（如果存在）
            if os.path.exists('monitor.db'):
                backup_name = f'monitor_local_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db'
                shutil.copy2('monitor.db', backup_name)
                print(f"已备份当前数据库为: {backup_name}")

            # 写入恢复的数据库
            with open('monitor.db', 'wb') as f:
                f.write(content)

            print("=== 数据库恢复成功 ===\n")
            return True, "数据库恢复成功"

        except Exception as e:
            if "404" in str(e):
                if not os.path.exists('monitor.db'):
                    if init_db():
                        return True, "已创建新的本地数据库"
                return True, "继续使用现有的本地数据库"
            return False, f"恢复数据库失败: {str(e)}"

    except Exception as e:
        return False, f"恢复过程发生异常: {str(e)}"

# 为了保持兼容性，保留原函数名但改变功能
def push_db_updates():
    """将本地数据库备份到 GitHub（兼容性函数）"""
    return backup_to_github()

def pull_db_from_github():
    """从 GitHub 恢复数据库（兼容性函数）"""
    return restore_from_github() 