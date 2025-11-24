import imaplib
from config import config

def list_folders():
    """列出所有可用的邮箱文件夹"""
    print("=== 列出所有邮箱文件夹 ===")
    
    try:
        # 连接服务器
        mail = imaplib.IMAP4_SSL('imap.163.com', 993)
        mail.login(config.MAIL_USERNAME, config.MAIL_PASSWORD)
        print("✅ 登录成功")
        
        # 列出所有文件夹
        status, folders = mail.list()
        
        if status == 'OK':
            print("可用的文件夹:")
            for folder in folders:
                # 解析文件夹信息
                if isinstance(folder, bytes):
                    folder = folder.decode('utf-8')
                print(f"  - {folder}")
        else:
            print(f"❌ 列出文件夹失败: {status}")
        
        # 关闭连接
        mail.logout()
        
    except Exception as e:
        print(f"❌ 错误: {str(e)}")

if __name__ == "__main__":
    list_folders()