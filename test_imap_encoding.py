import imaplib
import email
from email.header import decode_header
from config import config

def test_imap_encoding():
    """测试IMAP编码问题"""
    print("=== 测试IMAP编码处理 ===")
    
    try:
        # 连接QQ邮箱
        mail = imaplib.IMAP4_SSL('imap.qq.com', 993)
        mail.login(config.MAIL_USERNAME, config.MAIL_PASSWORD)
        print("✅ 登录成功")
        
        # 选择收件箱
        mail.select('INBOX')
        print("✅ 选择收件箱成功")
        
        # 测试不同的搜索方法
        search_tests = [
            ('直接搜索中文', 'SUBJECT "222汇总"'),
            ('搜索英文部分', 'SUBJECT "222"'),
            ('搜索汇总', 'SUBJECT "汇总"'),
            ('搜索所有', 'ALL')
        ]
        
        for test_name, criteria in search_tests:
            print(f"\n--- 测试: {test_name} ---")
            print(f"条件: {criteria}")
            
            try:
                status, messages = mail.search(None, criteria)
                if status == 'OK':
                    email_ids = messages[0].split()
                    print(f"✅ 成功，找到 {len(email_ids)} 封邮件")
                    
                    # 显示前几封邮件的主题
                    for i, email_id in enumerate(email_ids[:2]):
                        status, msg_data = mail.fetch(email_id, '(BODY[HEADER.FIELDS (SUBJECT)])')
                        if status == 'OK':
                            msg = email.message_from_bytes(msg_data[0][1])
                            subject = msg.get("Subject", "")
                            
                            # 解码主题
                            decoded_parts = decode_header(subject)
                            subject_text = ""
                            for part, encoding in decoded_parts:
                                if isinstance(part, bytes):
                                    subject_text += part.decode(encoding if encoding else 'utf-8')
                                else:
                                    subject_text += part
                            
                            print(f"  邮件 {i+1}: {subject_text}")
                else:
                    print(f"❌ 搜索失败: {status}")
                    
            except Exception as e:
                print(f"❌ 搜索出错: {e}")
        
        mail.close()
        mail.logout()
        
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")

if __name__ == "__main__":
    test_imap_encoding()