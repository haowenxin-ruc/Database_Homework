import imaplib
from config import config

def check_163_security_settings():
    """检查163邮箱的安全设置选项"""
    print("=== 检查163邮箱安全设置 ===")
    
    try:
        # 连接并尝试各种可能的安全设置
        mail = imaplib.IMAP4_SSL('imap.163.com', 993)
        
        # 登录
        mail.login(config.MAIL_USERNAME, config.MAIL_PASSWORD)
        print("✅ 登录成功")
        
        # 尝试不同的认证方式
        print("\n尝试不同的认证方式:")
        
        # 方法1: 标准SELECT
        try:
            status, data = mail.select('INBOX')
            print(f"标准SELECT: {status}")
        except Exception as e:
            print(f"标准SELECT失败: {e}")
        
        # 方法2: 使用EXAMINE (只读模式)
        try:
            status, data = mail.examine('INBOX')
            print(f"EXAMINE(只读): {status}")
        except Exception as e:
            print(f"EXAMINE失败: {e}")
        
        # 方法3: 检查其他文件夹
        folders = ['INBOX', 'inbox', '收件箱']
        for folder in folders:
            try:
                status, data = mail.select(folder)
                print(f"文件夹 '{folder}': {status}")
                if status == 'OK':
                    break
            except Exception as e:
                print(f"文件夹 '{folder}' 失败: {e}")
        
        mail.logout()
        
    except Exception as e:
        print(f"❌ 检查失败: {str(e)}")

def test_alternative_ports():
    """测试其他端口"""
    print("\n=== 测试其他端口 ===")
    
    ports = [993, 143, 995]  # IMAP SSL, IMAP, POP3 SSL
    
    for port in ports:
        print(f"\n测试端口 {port}:")
        try:
            if port == 993:
                mail = imaplib.IMAP4_SSL('imap.163.com', port)
            else:
                mail = imaplib.IMAP4('imap.163.com', port)
                if port == 143:
                    mail.starttls()  # 尝试STARTTLS
            
            mail.login(config.MAIL_USERNAME, config.MAIL_PASSWORD)
            print("  ✅ 登录成功")
            
            status, data = mail.select('INBOX')
            print(f"  选择INBOX: {status}")
            
            mail.logout()
            
        except Exception as e:
            print(f"  ❌ 失败: {e}")

if __name__ == "__main__":
    check_163_security_settings()
    test_alternative_ports()