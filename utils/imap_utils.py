# [file name]: imap_utils.py
# [file content begin]
import imaplib
import email
from email.header import decode_header
import os
import re
from datetime import datetime
from config import config
import base64

# 修复IMAP UTF-8支持
class UTF8IMAP4(imaplib.IMAP4_SSL):
    """支持UTF-8编码的IMAP客户端"""
    
    def _encode(self, s):
        """重写编码方法，强制使用UTF-8"""
        if isinstance(s, str):
            return s.encode('utf-8')
        return s
    
    def search(self, charset, *criteria):
        """重写搜索方法，支持UTF-8"""
        if charset is None:
            charset = 'UTF-8'
        return super().search(charset, *criteria)

class EmailReceiver:
    def __init__(self):
        self.imap_server = config.IMAP_SERVER if hasattr(config, 'IMAP_SERVER') else 'imap.qq.com'
        self.imap_port = config.IMAP_PORT if hasattr(config, 'IMAP_PORT') else 993
        self.username = config.MAIL_USERNAME
        self.password = config.MAIL_PASSWORD
        self.mail = None
    
    def connect(self):
        """连接到IMAP服务器 - 使用UTF-8编码"""
        try:
            print(f"连接到IMAP服务器: {self.imap_server}:{self.imap_port}")
            self.mail = UTF8IMAP4(self.imap_server, self.imap_port)
            self.mail.login(self.username, self.password)
            print("✅ IMAP连接成功")
            return True
        except Exception as e:
            print(f"❌ IMAP连接失败: {str(e)}")
            return False
    
    def select_folder(self, folder_name='INBOX'):
        """选择邮箱文件夹"""
        try:
            print(f"选择文件夹: {folder_name}")
            status, data = self.mail.select(folder_name)
            if status == 'OK':
                print(f"✅ 选择文件夹成功: {folder_name}")
                return True
            else:
                print(f"❌ 选择文件夹失败: {status} - {data}")
                return False
        except Exception as e:
            print(f"❌ 选择文件夹时出错: {str(e)}")
            return False
    
    def disconnect(self):
        """断开连接"""
        if self.mail:
            try:
                self.mail.close()
                self.mail.logout()
            except:
                pass
    
    def search_reply_emails(self, task_name):
        """搜索特定任务的回复邮件 - 修复中文编码问题"""
        if not self.connect():
            return []
        
        try:
            # 选择收件箱
            if not self.select_folder('INBOX'):
                print("❌ 无法选择收件箱")
                return []
            
            # 方法1：使用UTF-8编码直接搜索中文
            search_criteria = f'SUBJECT "{task_name}汇总"'
            print(f"UTF-8搜索条件: {search_criteria}")
            
            try:
                # 明确指定UTF-8字符集
                status, messages = self.mail.search('UTF-8', search_criteria)
                
                if status == 'OK':
                    email_ids = messages[0].split()
                    print(f"✅ UTF-8搜索成功，找到 {len(email_ids)} 封相关邮件")
                    
                    emails = []
                    for email_id in email_ids:
                        email_data = self.fetch_email(email_id)
                        if email_data:
                            emails.append(email_data)
                    
                    return emails
                else:
                    print(f"UTF-8搜索失败: {status}")
                    
            except Exception as e:
                print(f"UTF-8搜索异常: {str(e)}")
            
            # 方法2：使用编码后的中文搜索
            print("尝试编码中文搜索...")
            try:
                # 将中文编码为MIME格式
                encoded_task_name = self.encode_chinese_to_mime(task_name)
                encoded_search = f'SUBJECT "{encoded_task_name}汇总"'
                print(f"编码搜索条件: {encoded_search}")
                
                status, messages = self.mail.search(None, encoded_search)
                
                if status == 'OK':
                    email_ids = messages[0].split()
                    print(f"通过编码搜索找到 {len(email_ids)} 封邮件")
                    
                    # 过滤出真正相关的邮件
                    emails = []
                    for email_id in email_ids:
                        email_data = self.fetch_email(email_id)
                        if email_data and self.is_task_reply(email_data, task_name):
                            emails.append(email_data)
                    
                    if emails:
                        print(f"✅ 编码搜索成功，找到 {len(emails)} 封相关邮件")
                        return emails
                        
            except Exception as e:
                print(f"编码搜索异常: {str(e)}")
            
            # 方法3：搜索所有包含"汇总"的邮件，然后过滤
            print("使用备用方法：搜索包含'汇总'的邮件并过滤")
            try:
                # 搜索所有包含"汇总"的邮件
                status, messages = self.mail.search(None, 'SUBJECT "汇总"')
                
                if status != 'OK':
                    print(f"❌ 搜索包含'汇总'的邮件失败: {status}")
                    return []
                
                email_ids = messages[0].split()
                print(f"找到 {len(email_ids)} 封包含'汇总'的邮件，开始过滤...")
                
                # 限制处理数量
                max_emails = min(100, len(email_ids))  # 只处理前100封，避免性能问题
                emails = []
                
                for i, email_id in enumerate(email_ids[:max_emails]):
                    if i % 10 == 0:  # 每处理10封邮件打印一次进度
                        print(f"过滤进度: {i+1}/{max_emails}")
                    
                    email_data = self.fetch_email(email_id)
                    if email_data and self.is_task_reply(email_data, task_name):
                        emails.append(email_data)
                
                print(f"过滤后找到 {len(emails)} 封相关邮件")
                return emails
                
            except Exception as e:
                print(f"备用方法搜索异常: {str(e)}")
            
            # 方法4：搜索所有邮件，然后过滤
            print("使用最终方法：搜索所有邮件并过滤")
            try:
                status, messages = self.mail.search(None, 'ALL')
                
                if status != 'OK':
                    print(f"❌ 搜索所有邮件失败: {status}")
                    return []
                
                email_ids = messages[0].split()
                print(f"找到 {len(email_ids)} 封邮件，开始过滤...")
                
                # 限制处理数量
                max_emails = min(200, len(email_ids))  # 只处理前200封，避免性能问题
                emails = []
                
                for i, email_id in enumerate(email_ids[:max_emails]):
                    if i % 20 == 0:  # 每处理20封邮件打印一次进度
                        print(f"过滤进度: {i+1}/{max_emails}")
                    
                    email_data = self.fetch_email(email_id)
                    if email_data and self.is_task_reply(email_data, task_name):
                        emails.append(email_data)
                
                print(f"过滤后找到 {len(emails)} 封相关邮件")
                return emails
                
            except Exception as e:
                print(f"最终方法搜索异常: {str(e)}")
            
            return []
            
        except Exception as e:
            print(f"❌ 搜索邮件时出错: {str(e)}")
            return []
        finally:
            self.disconnect()
    
    def encode_chinese_to_mime(self, text):
        """将中文文本编码为MIME格式"""
        try:
            # 使用email.header模块进行编码
            from email.header import Header
            encoded = Header(text, 'utf-8').encode()
            return encoded
        except Exception as e:
            print(f"编码中文失败: {str(e)}")
            return text
    
    def extract_ascii_part(self, text):
        """提取文本中的英文和数字部分"""
        import re
        # 匹配英文、数字和下划线
        ascii_pattern = r'[a-zA-Z0-9_]+'
        matches = re.findall(ascii_pattern, text)
        if matches:
            # 返回最长的ASCII部分
            return max(matches, key=len)
        return None
    
    def is_task_reply(self, email_data, task_name):
        """检查邮件是否是任务的回复"""
        if not email_data:
            return False
        
        subject = email_data.get('subject', '')
        from_email = email_data.get('from_email', '')
        
        # 打印调试信息
        print(f"检查邮件: 主题='{subject}', 发件人='{from_email}'")
        
        # 检查主题是否包含任务名称和"汇总"
        if task_name in subject and '汇总' in subject:
            print(f"✅ 主题匹配: {subject}")
            return True
        
        # 检查是否包含任务名称的部分（处理可能的编码问题）
        if any(part in subject for part in [task_name, task_name.replace(' ', ''), task_name[:4]]):
            if '汇总' in subject:
                print(f"✅ 部分匹配: {subject}")
                return True
        
        # 检查发件人是否是系统中的教师
        from app import app, db
        from models import Teacher
        
        with app.app_context():
            teacher = Teacher.query.filter_by(email=from_email).first()
            if teacher:
                # 如果是系统中的教师，且主题包含"汇总"，则认为是回复
                if '汇总' in subject:
                    print(f"✅ 教师匹配: {teacher.teacher_name}, 主题: {subject}")
                    return True
        
        # 检查邮件正文是否包含任务相关信息
        body = email_data.get('body', '')
        if task_name in body and '汇总' in body:
            print(f"✅ 正文匹配: {subject}")
            return True
        
        print(f"❌ 不匹配: {subject}")
        return False
    
    def fetch_email(self, email_id):
        """获取单封邮件的详细信息"""
        try:
            status, msg_data = self.mail.fetch(email_id, '(RFC822)')
            
            if status != 'OK':
                return None
            
            # 解析邮件
            msg = email.message_from_bytes(msg_data[0][1])
            
            # 解码主题
            subject, encoding = decode_header(msg["Subject"])[0]
            if isinstance(subject, bytes):
                subject = subject.decode(encoding if encoding else 'utf-8')
            
            # 获取发件人
            from_header = msg.get("From")
            sender_email = self.extract_email(from_header)
            
            # 获取日期
            date_header = msg.get("Date")
            email_date = self.parse_email_date(date_header)
            
            # 提取邮件正文和附件
            body = ""
            attachments = []
            
            if msg.is_multipart():
                for part in msg.walk():
                    content_type = part.get_content_type()
                    content_disposition = str(part.get("Content-Disposition"))
                    
                    # 提取正文
                    if content_type == "text/plain" and "attachment" not in content_disposition:
                        try:
                            body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                        except:
                            try:
                                body = part.get_payload(decode=True).decode('gbk', errors='ignore')
                            except:
                                body = "无法解码正文"
                    
                    # 提取附件
                    elif "attachment" in content_disposition:
                        filename = part.get_filename()
                        if filename:
                            # 解码文件名
                            decoded_filename = self.decode_filename(filename)
                            print(f"原始文件名: {filename}")
                            print(f"解码后文件名: {decoded_filename}")
                            
                            file_data = part.get_payload(decode=True)
                            attachments.append({
                                'filename': decoded_filename,
                                'data': file_data
                            })
            else:
                # 非多部分邮件
                try:
                    body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
                except:
                    try:
                        body = msg.get_payload(decode=True).decode('gbk', errors='ignore')
                    except:
                        body = "无法解码正文"
            
            return {
                'id': email_id.decode(),
                'subject': subject,
                'from_email': sender_email,
                'date': email_date,
                'body': body,
                'attachments': attachments
            }
            
        except Exception as e:
            print(f"❌ 解析邮件失败 (ID: {email_id}): {str(e)}")
            return None
    
    def extract_email(self, from_header):
        """从发件人头部信息中提取邮箱地址"""
        if not from_header:
            return ""
        
        # 使用正则表达式提取邮箱
        match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', from_header)
        if match:
            return match.group(0)
        return from_header
    
    def parse_email_date(self, date_header):
        """解析邮件日期"""
        if not date_header:
            return datetime.now()
        
        try:
            # 尝试解析各种日期格式
            from email.utils import parsedate_to_datetime
            return parsedate_to_datetime(date_header)
        except:
            return datetime.now()
    
    def decode_filename(self, filename):
        """解码MIME编码的文件名"""
        if not filename:
            return filename
            
        try:
            # 如果是MIME编码格式（如 =?UTF-8?B?...
            if filename.startswith('=?') and '?=' in filename:
                decoded_parts = decode_header(filename)
                decoded_name = ""
                for part, encoding in decoded_parts:
                    if isinstance(part, bytes):
                        if encoding:
                            decoded_name += part.decode(encoding)
                        else:
                            decoded_name += part.decode('utf-8', errors='ignore')
                    else:
                        decoded_name += part
                return decoded_name
            else:
                return filename
        except Exception as e:
            print(f"文件名解码失败: {filename}, 错误: {str(e)}")
            return filename

# 创建全局实例
email_receiver = EmailReceiver()
# [file content end]