import os
from github import Github
from datetime import datetime
import pytz
import base64
import requests
import subprocess

def push_db_updates():
    """推送数据库更新到 GitHub"""
    try:
        print("正在同步数据库到GitHub...")
        # 获取环境变量
        token = os.getenv('GITHUB_TOKEN')
        repo_name = os.getenv('GITHUB_REPO')
        username = os.getenv('GITHUB_USERNAME')

        # 连接到GitHub
        g = Github(token)
        repo = g.get_user(username).get_repo(repo_name)

        # 读取数据库文件
        try:
            with open('monitor.db', 'rb') as file:
                content = file.read()
                content_b64 = base64.b64encode(content).decode()
        except Exception as e:
            print(f"错误: 读取数据库文件失败 - {str(e)}")
            return False, "读取数据库文件失败"

        # 获取当前时间作为提交信息
        commit_message = f"Update database: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        # 检查文件是否存在并更新
        try:
            file = repo.get_contents("monitor.db")
            # 更新文件
            repo.update_file(
                path="monitor.db",
                message=commit_message,
                content=content_b64,
                sha=file.sha
            )
            print("数据库文件已更新")
        except Exception as e:
            if "404" in str(e):  # 文件不存在
                # 创建新文件
                repo.create_file(
                    path="monitor.db",
                    message=commit_message,
                    content=content_b64
                )
                print("数据库文件已创建")
            else:
                raise  # 重新抛出其他类型的异常

        print("数据库同步成功！")
        return True, "数据库同步成功"

    except Exception as e:
        error_msg = f"同步数据库时出错: {str(e)}"
        print(error_msg)
        return False, f"同步数据库时出错: {str(e)}"

def pull_db_from_github():
    """从 GitHub 下载数据库"""
    try:
        # 获取环境变量
        token = os.getenv('GITHUB_TOKEN')
        repo_name = os.getenv('GITHUB_REPO')
        username = os.getenv('GITHUB_USERNAME')

        print("\n=== 开始从GitHub同步数据库 ===")

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
                os.rename('monitor.db', backup_name)
                print(f"已备份当前数据库为: {backup_name}")

            # 写入新的数据库文件
            with open('monitor.db', 'wb') as f:
                f.write(content)

            print("=== 数据库同步成功 ===\n")
            return True, "数据库同步成功"

        except Exception as e:
            print(f"错误: 下载数据库失败 - {str(e)}")
            # 如果失败，恢复备份
            if backup_name and os.path.exists(backup_name):
                os.rename(backup_name, 'monitor.db')
                print("已恢复数据库备份")
            return False, f"下载数据库失败: {str(e)}"

    except Exception as e:
        print(f"错误: 同步过程发生异常 - {str(e)}")
        return False, f"同步过程发生异常: {str(e)}" 