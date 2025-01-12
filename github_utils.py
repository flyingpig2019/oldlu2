import os
from github import Github
from datetime import datetime, timedelta
import pytz
import sqlite3
import tempfile
import shutil
import time
import base64

def force_upload_to_github():
    """强制更新 GitHub 上的数据库文件"""
    try:
        token = os.getenv('GITHUB_TOKEN')
        repo_name = os.getenv('GITHUB_REPO')
        username = os.getenv('GITHUB_USERNAME')

        if not all([token, repo_name, username]):
            return False

        # 连接到GitHub
        g = Github(token)
        repo = g.get_user(username).get_repo(repo_name)

        # 获取东部时间
        eastern = pytz.timezone('US/Eastern')
        current_time = datetime.now(eastern)
        time_str = current_time.strftime('%Y-%m-%d %H:%M:%S EST')

        try:
            # 读取并编码文件
            with open('monitor.db', 'rb') as f:
                content = f.read()

            # 强制更新文件
            try:
                file = repo.get_contents("monitor.db")
                repo.update_file(
                    path="monitor.db",
                    message=f"Update monitor.db - {time_str}",
                    content=content,
                    sha=file.sha
                )
            except:
                repo.create_file(
                    path="monitor.db",
                    message=f"Create monitor.db - {time_str}",
                    content=content
                )
            return True
        except:
            return False
    except:
        return False

def download_from_github():
    """从 GitHub 下载数据库文件"""
    try:
        token = os.getenv('GITHUB_TOKEN')
        repo_name = os.getenv('GITHUB_REPO')
        username = os.getenv('GITHUB_USERNAME')

        if not all([token, repo_name, username]):
            return False, "环境变量未正确设置"

        print("\n=== 开始从GitHub下载文件 ===")

        # 连接到GitHub
        g = Github(token)
        repo = g.get_user(username).get_repo(repo_name)

        try:
            # 获取文件内容
            file = repo.get_contents("monitor.db")
            content = base64.b64decode(file.content)

            # 创建临时文件
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_file.write(content)
                temp_path = temp_file.name

            # 验证数据库
            try:
                conn = sqlite3.connect(temp_path)
                conn.execute("SELECT 1")
                conn.close()

                # 如果验证成功，替换原有数据库
                if os.path.exists('monitor.db'):
                #    os.remove('monitor.db')
                    shutil.move(temp_path, 'monitor.db')

                print("=== 文件下载成功 ===\n")
                return True, "文件下载成功"

            except sqlite3.DatabaseError:
                os.remove(temp_path)
                return False, "下载的文件不是有效的数据库"

        except Exception as e:
            print(e)
            if "404" in str(e):
                return False, "GitHub上找不到文件"
            return False, f"下载文件失败: {str(e)}"

    except Exception as e:
        return False, f"下载过程发生异常: {str(e)}"

# 为了保持兼容性
def push_db_updates():
    """已废弃的函数，保持向后兼容"""
    return True, "操作已更改，请使用上传按钮手动同步"

def pull_db_from_github():
    """已废弃的函数，保持向后兼容"""
    return True, "操作已更改，请使用下载按钮手动同步"

def upload_to_github():
    """已废弃的函数，保持向后兼容"""
    try:
        token = os.getenv('GITHUB_TOKEN')
        repo_name = os.getenv('GITHUB_REPO')
        username = os.getenv('GITHUB_USERNAME')

        if not all([token, repo_name, username]):
            return False, "环境变量未正确设置"

        # 调用新的函数
        success = force_upload_to_github()
        if success:
            return True, "文件上传成功"
        else:
            return False, "文件上传失败"

    except Exception as e:
        return False, f"上传过程发生异常: {str(e)}" 