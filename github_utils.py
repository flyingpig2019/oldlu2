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

def pull_db_from_github():
    """从 GitHub 下载数据库并替换本地数据库"""
    try:
        token = os.getenv('GITHUB_TOKEN')
        repo_name = os.getenv('GITHUB_REPO')
        username = os.getenv('GITHUB_USERNAME')

        if not all([token, repo_name, username]):
            return False, "环境变量未正确设置"

        print("\n=== 开始从GitHub同步数据库 ===")

        # 连接到GitHub
        g = Github(token)
        repo = g.get_user(username).get_repo(repo_name)

        try:
            # 获取数据库文件内容
            file = repo.get_contents("monitor.db")
            content = base64.b64decode(file.content)

            # 备份当前数据库
            if os.path.exists('monitor.db'):
                backup_name = f'monitor_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db'
                shutil.copy2('monitor.db', backup_name)
                print(f"已备份当前数据库为: {backup_name}")

            # 直接替换本地数据库
            with open('monitor.db', 'wb') as f:
                f.write(content)

            print("=== 数据库同步成功 ===\n")
            return True, "数据库同步成功"

        except Exception as e:
            if "404" in str(e):
                print("GitHub仓库中找不到数据库文件")
                if not os.path.exists('monitor.db'):
                    if init_db():
                        return True, "已创建新的本地数据库"
                return True, "继续使用现有的本地数据库"
            return False, f"下载数据库失败: {str(e)}"

    except Exception as e:
        return False, f"同步过程发生异常: {str(e)}"

def push_db_updates():
    """推送本地数据库到 GitHub，只保留最新的备份"""
    try:
        token = os.getenv('GITHUB_TOKEN')
        repo_name = os.getenv('GITHUB_REPO')
        username = os.getenv('GITHUB_USERNAME')

        if not all([token, repo_name, username]):
            return False, "环境变量未正确设置"

        # 连接到GitHub
        g = Github(token)
        repo = g.get_user(username).get_repo(repo_name)

        # 读取当前数据库文件
        with open('monitor.db', 'rb') as f:
            content = f.read()
            content_b64 = base64.b64encode(content).decode()

        try:
            # 删除旧的备份文件（如果存在）
            try:
                backup_file = repo.get_contents("monitor_backup.db")
                repo.delete_file(
                    path="monitor_backup.db",
                    message="Remove old backup",
                    sha=backup_file.sha
                )
            except:
                pass  # 如果没有旧备份文件，继续执行

            # 将当前的 monitor.db 重命名为 monitor_backup.db
            try:
                current_file = repo.get_contents("monitor.db")
                repo.create_file(
                    path="monitor_backup.db",
                    message="Create backup of current database",
                    content=base64.b64encode(base64.b64decode(current_file.content)).decode()
                )
            except:
                pass  # 如果当前没有 monitor.db，继续执行

            # 更新或创建新的 monitor.db
            try:
                file = repo.get_contents("monitor.db")
                repo.update_file(
                    path="monitor.db",
                    message=f"Update database: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    content=content_b64,
                    sha=file.sha
                )
            except:
                repo.create_file(
                    path="monitor.db",
                    message=f"Create database: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    content=content_b64
                )

            return True, "数据库更新成功"

        except Exception as e:
            return False, f"更新数据库失败: {str(e)}"

    except Exception as e:
        return False, f"推送数据库失败: {str(e)}" 