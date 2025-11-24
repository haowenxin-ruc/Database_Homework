import os

class Config:
    SECRET_KEY = 'your-secret-key-here-change-in-production'
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    
    # SQLite 数据库配置（简单易用）
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(BASE_DIR, 'data_collection.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # 邮件配置（稍后填写）
    IMAP_SERVER = 'imap.qq.com'
    MAIL_SERVER = 'smtp.qq.com'
    IMAP_PORT=993
    MAIL_PORT = 465
    MAIL_USE_TLS = False  # 465端口不使用TLS，使用SSL
    MAIL_USERNAME = '2379296267@qq.com'
    MAIL_PASSWORD = 'xyuovjmlzdbyebff'  # 替换为你的邮箱授权码
    
    # 大模型API配置（稍后填写）
    AI_API_KEY = '' 
    AI_BASE_URL = 'https://api.deepseek.com'  # DeepSeek官方地址
    AI_MODEL_NAME = 'deepseek-chat' # 或者 deepseek-reasoner

config = Config()