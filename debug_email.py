import smtplib
import socket
import sys
from config import config

def debug_email_config():
    print("=== 邮件配置详细调试 ===")
    
    # 显示当前配置
    print(f"邮件服务器: {config.MAIL_SERVER}")
    print(f"邮件端口: {config.MAIL_PORT}")
    print(f"邮箱用户名: {config.MAIL_USERNAME}")
    print(f"密码长度: {len(config.MAIL_PASSWORD) if config.MAIL_PASSWORD else 0}")
    
    # 检查配置完整性
    if not all([config.MAIL_SERVER, config.MAIL_USERNAME, config.MAIL_PASSWORD]):
        print("❌ 邮件配置不完整")
        return False
    
    # 测试DNS解析
    try:
        print(f"\n1. 测试DNS解析...")
        ip_list = socket.getaddrinfo(config.MAIL_SERVER, config.MAIL_PORT)
        for result in ip_list:
            print(f"   ✓ 解析到: {result[4][0]}:{result[4][1]}")
    except Exception as e:
        print(f"   ❌ DNS解析失败: {e}")
        return False
    
    # 测试端口连接
    try:
        print(f"\n2. 测试端口连接...")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        result = sock.connect_ex((config.MAIL_SERVER, config.MAIL_PORT))
        if result == 0:
            print(f"   ✓ 端口 {config.MAIL_PORT} 连接成功")
            sock.close()
        else:
            print(f"   ❌ 端口 {config.MAIL_PORT} 连接失败 (错误码: {result})")
            return False
    except Exception as e:
        print(f"   ❌ 端口连接异常: {e}")
        return False
    
    # 测试SMTP连接
    try:
        print(f"\n3. 测试SMTP连接...")
        if config.MAIL_PORT == 465:
            server = smtplib.SMTP_SSL(config.MAIL_SERVER, config.MAIL_PORT, timeout=10)
        else:
            server = smtplib.SMTP(config.MAIL_SERVER, config.MAIL_PORT, timeout=10)
            if config.MAIL_USE_TLS:
                server.starttls()
        
        print("   ✓ SMTP连接建立成功")
        
        # 测试登录
        print(f"\n4. 测试邮箱登录...")
        server.login(config.MAIL_USERNAME, config.MAIL_PASSWORD)
        print("   ✓ 邮箱登录成功")
        
        server.quit()
        print(f"\n🎉 所有测试通过！邮件配置正确")
        return True
        
    except smtplib.SMTPAuthenticationError as e:
        print(f"   ❌ 认证失败: {e}")
        print("   请检查：")
        print("   - 邮箱地址是否正确")
        print("   - 是否使用了授权码（而不是登录密码）")
        print("   - 授权码是否已过期")
        return False
    except Exception as e:
        print(f"   ❌ SMTP连接失败: {e}")
        return False

# 确保有这一行来调用函数
if __name__ == "__main__":
    debug_email_config()