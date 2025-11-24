import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.header import Header
import os
from config import config

class EmailSender:
    def __init__(self):
        self.smtp_server = config.MAIL_SERVER
        self.smtp_port = config.MAIL_PORT
        self.username = config.MAIL_USERNAME
        self.password = config.MAIL_PASSWORD
    
    def send_email(self, to_email, subject, content, attachment_path=None):
        """
        发送邮件 - 添加详细日志
        """
        print(f"\n=== 开始发送邮件 ===")
        print(f"发件人: {self.username}")
        print(f"收件人: {to_email}")
        print(f"邮件主题: {subject}")
        print(f"使用服务器: {self.smtp_server}:{self.smtp_port}")
        
        if not self.smtp_server or not self.username or not self.password:
            error_msg = "邮件服务器未配置"
            print(f"❌ {error_msg}")
            raise Exception(error_msg)
        
        # 验证邮箱格式
        if not self._is_valid_email(to_email):
            error_msg = f"收件人邮箱格式无效: {to_email}"
            print(f"❌ {error_msg}")
            return False
        
        if not self._is_valid_email(self.username):
            error_msg = f"发件人邮箱格式无效: {self.username}"
            print(f"❌ {error_msg}")
            return False
        
        try:
            # 创建邮件对象
            msg = MIMEMultipart()
            msg['From'] = self.username
            msg['To'] = to_email
            msg['Subject'] = Header(subject, 'utf-8')
            
            # 添加邮件正文
            text_part = MIMEText(content, 'plain', 'utf-8')
            msg.attach(text_part)
            
            # 添加附件
            if attachment_path and os.path.exists(attachment_path):
                print(f"添加附件: {attachment_path}")
                with open(attachment_path, 'rb') as file:
                    attach_part = MIMEApplication(file.read(), Name=os.path.basename(attachment_path))
                attach_part['Content-Disposition'] = f'attachment; filename="{os.path.basename(attachment_path)}"'
                msg.attach(attach_part)
            else:
                print("无附件或附件不存在")
            
            # 连接服务器并发送
            print("正在连接SMTP服务器...")
            
            if self.smtp_port == 465:
    #                     465端口使用SSL
                server = smtplib.SMTP_SSL(self.smtp_server, self.smtp_port, timeout=30)
            else:
                # 587端口使用TLS
                server = smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=30)   
                server.starttls()
              
           
        
            
            print("正在登录邮箱...")
            server.login(self.username, self.password)
            print("✅ 登录成功")
            
            print("正在发送邮件...")
            server.send_message(msg)
            server.quit()
            
            print(f"✅ 邮件发送成功: {to_email}")
            print("=== 发送完成 ===\n")
            return True
            
        except smtplib.SMTPAuthenticationError as e:
            error_msg = f"❌ 邮箱认证失败: {str(e)}"
            print(error_msg)
            print("请检查：")
            print(f"- 用户名: {self.username}")
            print(f"- 授权码是否正确（不是登录密码）")
            print(f"- 是否开启了SMTP服务")
            return False
        except smtplib.SMTPServerDisconnected as e:
            error_msg = f"❌ 服务器断开连接: {str(e)}"
            print(error_msg)
            return False
        except smtplib.SMTPException as e:
            error_msg = f"❌ SMTP协议错误: {str(e)}"
            print(error_msg)
            return False
        except Exception as e:
            error_msg = f"❌ 发送邮件失败: {str(e)}"
            print(error_msg)
            return False
    
    def _is_valid_email(self, email):
        """简单验证邮箱格式"""
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None

# 创建全局邮件发送器实例
email_sender = EmailSender()