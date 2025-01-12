from waitress import serve
from app import app
from create_db import create_database
from create_tables import create_tables
import os

if __name__ == '__main__':
    print('正在初始化服务器...')
    # 检查数据库文件是否存在
    if not os.path.exists('monitor.db'):
        print('创建数据库...')
        create_database()
    
    print('确保所有表都已创建...')
    create_tables()
    
    print('正在启动服务器...')
    serve(app, host='0.0.0.0', port=5000) 