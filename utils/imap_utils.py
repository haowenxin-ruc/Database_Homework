# [file name]: utils/imap_utils.py
import imaplib
import email
from email.header import decode_header
import os
import re
from datetime import datetime, timedelta
from config import config

class EmailReceiver:
    def __init__(self):
        self.imap_server = 'imap.qq.com'
        self.imap_port = 993
        self.username = config.MAIL_USERNAME
        self.password = config.MAIL_PASSWORD
        self.mail = None
    
    def connect(self):
        """连接到IMAP服务器"""
        try:
            # print(f"🔌 连接IMAP服务器: {self.imap_server}:{self.imap_port}")
            self.mail = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
            self.mail.login(self.username, self.password)
            # print("✅ IMAP登录成功")
            return True
        except Exception as e:
            print(f"❌ IMAP连接失败: {str(e)}")
            return False
    
    def disconnect(self):
        """断开连接"""
        if self.mail:
            try:
                self.mail.close()
                self.mail.logout()
            except:
                pass

    def _get_imap_date_str(self, date_obj):
        """生成兼容IMAP协议的日期字符串 (格式: 05-Nov-2024)"""
        # 英文月份映射，防止系统locale导致生成中文月份
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", 
                  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        day = date_obj.day
        month = months[date_obj.month - 1]
        year = date_obj.year
        return f"{day}-{month}-{year}"

    def search_reply_emails(self, task_name, lookback_days=30):
        """
        搜索回复邮件 (高效版)
        :param task_name: 任务名称
        :param lookback_days: 向前回溯的天数，默认30天，避免扫描全量邮件
        """
        if not self.connect():
            return []
        
        try:
            self.mail.select('INBOX')
            
            # 1. 计算搜索起始时间 (极大地提高效率的关键)
            since_date = datetime.now() - timedelta(days=lookback_days)
            since_str = self._get_imap_date_str(since_date)
            
            # 2. 构建搜索命令
            # 策略：搜索 (主题包含"汇总") AND (时间晚于 X)
            # 我们不直接搜索完整任务名，因为任务名太长容易导致匹配失败
            # 我们先搜 "汇总"，拉回来后再精确匹配
            
            # 注意：SUBJECT 后面的关键字如果有空格，需要引号包裹
            # IMAP搜索格式: 'CHARSET UTF-8 (SINCE "01-Jan-2024" SUBJECT "keyword")'
            
            print(f"🔍 开始搜索: 最近 {lookback_days} 天, 主题包含 '汇总'...")
            
            # 构建查询语句
            # 使用 SUBJECT "汇总" 比较稳妥，因为任务名通常包含中文标点，IMAP搜索容易挂
            search_criteria = f'(SINCE "{since_str}" SUBJECT "汇总")'
            
            # 【核心修复】将查询字符串编码为 UTF-8 字节流
            typ, data = self.mail.search('UTF-8', search_criteria.encode('utf-8'))
            
            if typ != 'OK':
                print("❌ 服务器搜索响应错误")
                return []
                
            email_ids = data[0].split()
            print(f"✅ 服务器初筛找到 {len(email_ids)} 封邮件")
            
            if not email_ids:
                return []

            # 3. 获取详情并本地精确过滤
            results = []
            # 倒序遍历（先处理最新的）
            # 限制处理数量，防止卡死
            max_process = 50 
            
            for idx, e_id in enumerate(reversed(email_ids)):
                if idx >= max_process:
                    print(f"⚠️ 达到处理上限 ({max_process}封)，停止扫描")
                    break

                try:
                    # 只获取头信息来做二次筛选 (Body.PEEK[HEADER] 不会将邮件标记为已读)
                    typ, header_data = self.mail.fetch(e_id, '(BODY.PEEK[HEADER])')
                    if typ != 'OK': continue
                    
                    msg_header = email.message_from_bytes(header_data[0][1])
                    subject = self._decode_str(msg_header.get("Subject", ""))
                    
                    # === 本地精确匹配逻辑 ===
                    # 检查主题是否包含任务名（忽略空格）
                    clean_subject = subject.replace(" ", "")
                    clean_task_name = task_name.replace(" ", "")
                    
                    # 匹配逻辑：主题包含任务名 OR (包含"汇总"且包含部分任务关键字)
                    is_match = False
                    if clean_task_name in clean_subject:
                        is_match = True
                    elif "汇总" in clean_subject:
                        # 简单的模糊匹配：任务名前4个字匹配也算
                        if len(clean_task_name) > 4 and clean_task_name[:4] in clean_subject:
                            is_match = True
                    
                    if not is_match:
                        # print(f"  [跳过] 主题不匹配: {subject}")
                        continue
                        
                    print(f"  [命中] 发现相关邮件: {subject}")
                    
                    # 下载完整邮件内容
                    full_data = self.fetch_email(e_id)
                    if full_data:
                        results.append(full_data)
                        
                except Exception as e:
                    print(f"  [错误] 处理邮件ID {e_id} 失败: {e}")
                    continue
            
            return results
            
        except Exception as e:
            print(f"❌ 搜索流程异常: {str(e)}")
            import traceback
            traceback.print_exc()
            return []
        finally:
            self.disconnect()
    
    def _decode_str(self, s):
        """解码邮件头字符串"""
        if not s:
            return ""
        try:
            value, encoding = decode_header(s)[0]
            if isinstance(value, bytes):
                encoding = encoding if encoding else 'utf-8'
                # 某些垃圾邮件编码可能是 'unknown-8bit'，回退到 utf-8 或 gbk
                try:
                    return value.decode(encoding)
                except:
                    return value.decode('utf-8', errors='ignore')
            return value
        except:
            return str(s)

    def fetch_email(self, email_id):
        """获取单封邮件的详细信息（包含附件）"""
        try:
            status, msg_data = self.mail.fetch(email_id, '(RFC822)')
            if status != 'OK': return None
            
            msg = email.message_from_bytes(msg_data[0][1])
            subject = self._decode_str(msg.get("Subject"))
            from_email = self.extract_email(msg.get("From"))
            date_header = msg.get("Date")
            
            # 解析日期
            try:
                from email.utils import parsedate_to_datetime
                email_date = parsedate_to_datetime(date_header)
                # 转为不带时区的本地时间 (简化处理)
                if email_date.tzinfo is not None:
                    email_date = email_date.astimezone().replace(tzinfo=None)
            except:
                email_date = datetime.now()

            attachments = []
            
            if msg.is_multipart():
                for part in msg.walk():
                    content_disposition = str(part.get("Content-Disposition", ""))
                    
                    # 只要附件
                    if "attachment" in content_disposition:
                        filename = part.get_filename()
                        if filename:
                            filename = self._decode_str(filename)
                            file_data = part.get_payload(decode=True)
                            
                            attachments.append({
                                'filename': filename,
                                'data': file_data
                            })
            
            return {
                'id': email_id.decode() if isinstance(email_id, bytes) else email_id,
                'subject': subject,
                'from_email': from_email,
                'date': email_date,
                'attachments': attachments
            }
        except Exception as e:
            print(f"解析详情失败: {e}")
            return None

    def extract_email(self, from_header):
        """提取纯邮箱地址"""
        if not from_header: return ""
        match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', str(from_header))
        return match.group(0) if match else str(from_header)

# 创建全局实例
email_receiver = EmailReceiver()