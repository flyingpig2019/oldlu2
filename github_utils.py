import os
from github import Github
from datetime import datetime
import base64
import sqlite3

def upload_to_github():
    """将本地数据库上传到 GitHub（直接替换）"""
    try:
        token = os.getenv('GITHUB_TOKEN')
        repo_name = os.getenv('GITHUB_REPO')
        username = os.getenv('GITHUB_USERNAME')

        if not all([token, repo_name, username]):
            return False, "环境变量未正确设置"

        print("\n=== 开始上传数据库到GitHub ===")

        # 连接到GitHub
        g = Github(token)
        repo = g.get_user(username).get_repo(repo_name)

        # 读取当前数据库文件
        try:
            with open('monitor.db', 'rb') as f:
                content = f.read()
                content_b64 = base64.b64encode(content).decode()

            # 更新或创建数据库文件
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

            print("=== 数据库上传成功 ===\n")
            return True, "数据库上传成功"

        except Exception as e:
            error_msg = f"上传数据库失败: {str(e)}"
            print(f"错误: {error_msg}")
            return False, error_msg

    except Exception as e:
        error_msg = f"上传过程发生异常: {str(e)}"
        print(f"错误: {error_msg}")
        return False, error_msg

def download_from_github():
    """从 GitHub 下载数据库"""
    try:
        token = os.getenv('GITHUB_TOKEN')
        repo_name = os.getenv('GITHUB_REPO')
        username = os.getenv('GITHUB_USERNAME')

        if not all([token, repo_name, username]):
            return False, "环境变量未正确设置"

        print("\n=== 开始从GitHub下载数据库 ===")

        # 连接到GitHub
        g = Github(token)
        repo = g.get_user(username).get_repo(repo_name)

        try:
            # 获取数据库文件内容
            file = repo.get_contents("monitor.db")
            content = base64.b64decode(file.content)

            # 备份当前数据库
            if os.path.exists('monitor.db'):
                backup_name = f'monitor_local_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db'
                try:
                    with open('monitor.db', 'rb') as src, open(backup_name, 'wb') as dst:
                        dst.write(src.read())
                    print(f"已备份当前数据库为: {backup_name}")
                except:
                    pass

            # 写入新的数据库文件
            with open('monitor.db', 'wb') as f:
                f.write(content)

            print("=== 数据库下载成功 ===\n")
            return True, "数据库下载成功"

        except Exception as e:
            if "404" in str(e):
                return False, "GitHub上找不到数据库文件"
            return False, f"下载数据库失败: {str(e)}"

    except Exception as e:
        return False, f"下载过程发生异常: {str(e)}"

# 为了保持兼容性
def push_db_updates():
    """已废弃的函数，保持向后兼容"""
    return True, "操作已更改，请使用上传按钮手动同步"

def pull_db_from_github():
    """已废弃的函数，保持向后兼容"""
    return True, "操作已更改，请使用下载按钮手动同步" 