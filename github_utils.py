import os
from github import Github
from datetime import datetime
import pytz
import base64

def push_db_updates():
    """推送数据库更新到 GitHub"""
    try:
        # 获取环境变量
        token = os.getenv('GITHUB_TOKEN')
        repo_name = os.getenv('GITHUB_REPO')
        username = os.getenv('GITHUB_USERNAME')

        print("\n=== 开始同步数据库到GitHub ===")

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
            return False

        # 获取当前时间（北京时间）
        tz = pytz.timezone('Asia/Shanghai')
        current_time = datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')
        commit_message = f"Update database at {current_time}"

        try:
            # 检查文件是否存在
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
            except:
                # 文件不存在，创建新文件
                repo.create_file(
                    path="monitor.db",
                    message=commit_message,
                    content=content_b64
                )
                print("数据库文件已创建")

            print("=== 数据库同步成功 ===\n")
            return True

        except Exception as e:
            print(f"错误: GitHub API操作失败 - {str(e)}")
            return False

    except Exception as e:
        print(f"错误: 同步过程发生异常 - {str(e)}")
        return False 