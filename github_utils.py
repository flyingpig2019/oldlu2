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
    """从 GitHub 下载数据库"""
    try:
        # 获取环境变量
        token = os.getenv('GITHUB_TOKEN')
        repo_name = os.getenv('GITHUB_REPO')
        username = os.getenv('GITHUB_USERNAME')

        if not all([token, repo_name, username]):
            error_msg = "环境变量未正确设置 (GITHUB_TOKEN, GITHUB_REPO, GITHUB_USERNAME)"
            print(error_msg)
            return False, error_msg

        print("\n=== 开始从GitHub同步数据库 ===")

        # 如果本地数据库不存在，先创建一个
        if not os.path.exists('monitor.db'):
            print("本地数据库不存在，正在创建...")
            if not init_db():
                return False, "创建本地数据库失败"

        # 连接到GitHub
        g = Github(token)
        repo = g.get_user(username).get_repo(repo_name)
        backup_name = None

        try:
            # 获取数据库文件内容
            file = repo.get_contents("monitor.db")
            content = base64.b64decode(file.content)

            # 备份当前数据库
            if os.path.exists('monitor.db'):
                backup_name = f'monitor_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db'
                shutil.copy2('monitor.db', backup_name)
                print(f"已备份当前数据库为: {backup_name}")

            # 写入新的数据库文件
            with open('monitor.db', 'wb') as f:
                f.write(content)

            print("=== 数据库同步成功 ===\n")
            return True, "数据库同步成功"

        except Exception as e:
            if "404" in str(e):
                print("GitHub仓库中找不到数据库文件，将使用本地数据库")
                if not os.path.exists('monitor.db'):
                    if init_db():
                        return True, "已创建新的本地数据库"
                    else:
                        return False, "创建本地数据库失败"
                return True, "继续使用现有的本地数据库"
            else:
                error_msg = f"下载数据库失败: {str(e)}"
                print(f"错误: {error_msg}")
            
            # 如果失败且存在备份，恢复备份
            if backup_name and os.path.exists(backup_name):
                try:
                    shutil.copy2(backup_name, 'monitor.db')
                    print("已恢复数据库备份")
                except Exception as restore_error:
                    print(f"恢复备份失败: {str(restore_error)}")
            return False, error_msg

    except Exception as e:
        error_msg = f"同步过程发生异常: {str(e)}"
        print(f"错误: {error_msg}")
        return False, error_msg 

def push_db_updates():
    """推送数据库更新到 GitHub，只保留最新版本"""
    try:
        # 获取环境变量
        token = os.getenv('GITHUB_TOKEN')
        repo_name = os.getenv('GITHUB_REPO')
        username = os.getenv('GITHUB_USERNAME')

        if not all([token, repo_name, username]):
            error_msg = "环境变量未正确设置 (GITHUB_TOKEN, GITHUB_REPO, GITHUB_USERNAME)"
            print(error_msg)
            return False, error_msg

        print("\n=== 开始推送数据库到GitHub ===")

        # 连接到GitHub
        g = Github(token)
        repo = g.get_user(username).get_repo(repo_name)

        try:
            # 读取当前数据库文件
            with open('monitor.db', 'rb') as f:
                content = f.read()
                content_b64 = base64.b64encode(content).decode()

            try:
                # 检查文件是否存在
                file = repo.get_contents("monitor.db")
                
                # 删除所有以 "monitor_backup" 开头的文件
                contents = repo.get_contents("")
                for content_file in contents:
                    if content_file.path.startswith("monitor_backup"):
                        repo.delete_file(
                            content_file.path,
                            "Remove old backup",
                            content_file.sha
                        )
                        print(f"已删除旧备份: {content_file.path}")

                # 更新主数据库文件
                repo.update_file(
                    path="monitor.db",
                    message=f"Update database: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    content=content_b64,
                    sha=file.sha
                )
                print("数据库文件已更新")
                
            except Exception as e:
                if "404" in str(e):  # 文件不存在
                    # 创建新文件
                    repo.create_file(
                        path="monitor.db",
                        message=f"Create database: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                        content=content_b64
                    )
                    print("数据库文件已创建")
                else:
                    raise

            print("=== 数据库推送成功 ===\n")
            return True, "数据库推送成功"

        except Exception as e:
            error_msg = f"推送数据库失败: {str(e)}"
            print(f"错误: {error_msg}")
            return False, error_msg

    except Exception as e:
        error_msg = f"同步过程发生异常: {str(e)}"
        print(f"错误: {error_msg}")
        return False, error_msg 