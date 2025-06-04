import logging
import os
import smtplib
import requests
import re
from docx import Document
from datetime import datetime
import time
import requests, base64
import os
from werkzeug.security import generate_password_hash

from models import User

#from docx.shared import Pt

# Функция для отправки SMS-сообщения через API корпоративной PBX
def send_sms(phone_number, user_full_name):
    """
    Отправляет SMS-сообщение через Playmobile API.
    
    Args:
        phone_number (str): Номер телефона получателя (формат +998XXXXXXXXX).
        user_full_name (str): Полное имя пользователя, который рекомендует.
    """
    # Clean the phone number - remove spaces and ensure it starts with "+998"
    clean_phone = phone_number.replace(" ", "")
    clean_phone = clean_phone.replace("+" , "")
    if not clean_phone.startswith("998"):
        print(f"Invalid phone number format: {phone_number}")
        return False
        
    # Ensure user_full_name is properly decoded from Base64 if needed
    # (This is handled in routes.py, but added here for robustness)
    if isinstance(user_full_name, bytes):
        try:
            user_full_name = user_full_name.decode('utf-8')
        except UnicodeDecodeError:
            # Try to decode base64
            try:
                user_full_name = base64.b64decode(user_full_name).decode('utf-8')
            except:
                pass  # Keep as is if all decoding attempts fail
    
    # SMS text with recommendation
    sms_text = f"Вы были рекомендованы {user_full_name}. Вам предоставлена персональная скидка. Уточните удобное место и время встречи по номеру {os.getenv('GH_PHONE_NUMBER')}"
    
    # Playmobile API configuration
    api_url = os.getenv('SMS_API_URL')

    # Your Playmobile credentials
    username = os.getenv('SMS_API_USERNAME')
    password = os.getenv('SMS_API_PASSWORD')
    originator = os.getenv('SMS_API_ORIGINATOR')
    message_id = (datetime.now().strftime("%Y%m%d%H%M%S").encode('utf-8')).decode('utf-8')  # Unique message ID
    # Format payload according to Playmobile's requirements
    payload = {
        "messages": [
            {
                "recipient": clean_phone,  # Correctly formatted
                "message-id": message_id,
                "sms": {
                    "originator": originator,  # Ensure this is a string
                    "content": {
                        "text": sms_text
                    }
                }
            }
        ]
    }
    
    # # Set up authentication
    # auth = (username, password)
    
    # headers = {
    #     'Content-Type': 'application/json'
    # }
    
    try:
        userpass = username + ':' + password
        b64Val = base64.b64encode(userpass.encode('utf-8')).decode('utf-8')

        headers = {
            "Authorization": "Basic %s" % b64Val,
            "Content-Type": "application/json",
            "charset": "UTF-8"  # Explicitly set charset as mentioned in docs
        }

        # Print debug info
        #print(f"Sending to: {api_url}")
        #print(f"Headers: {headers}")
        #print(f"Payload: {payload}")

        response = requests.post(api_url, headers=headers, json=payload, timeout=30)

        print(f"Response status: {response.status_code}")
        print(f"Response text: {response.text}")

        if response.status_code == 200:
            print(f"SMS sent successfully to {phone_number}")
            return True
        else:
            print(f"Failed to send SMS: {response.status_code} - {response.text}")
            return False
        
    except requests.exceptions.RequestException as e:
        print(f"Error connecting to Playmobile: {e}")
        return False
    
def month_name_genitive(date):
    """Возвращает название месяца в родительном падеже"""
    # Create a fixed mapping instead of relying on system locales
    month_mapping = {
        1: 'Января', 2: 'Февраля', 3: 'Марта',
        4: 'Апреля', 5: 'Мая', 6: 'Июня',
        7: 'Июля', 8: 'Августа', 9: 'Сентября',
        10: 'Октября', 11: 'Ноября', 12: 'Декабря'
    }
    
    try:
        # Handle integer month number
        if isinstance(date, int) and 1 <= date <= 12:
            return month_mapping.get(date)
        # Handle datetime object
        elif hasattr(date, 'month'):
            return month_mapping.get(date.month)
        # Handle string month name (convert to corresponding number)
        else:
            # Simple mapping of Russian month names to numbers
            month_to_num = {
                'Январь': 1, 'Февраль': 2, 'Март': 3, 'Апрель': 4,
                'Май': 5, 'Июнь': 6, 'Июль': 7, 'Август': 8,
                'Сентябрь': 9, 'Октябрь': 10, 'Ноябрь': 11, 'Декабрь': 12
            }
            # Try to find the month number and then get the genitive form
            for name, num in month_to_num.items():
                if name in str(date):
                    return month_mapping.get(num)
            
            # If nothing matched, return as is
            return str(date)
    except Exception as e:
        print(f"Error in month_name_genitive: {e}")
        # Fallback - return the original value
        return str(date)
def get_document(type=None, **kwargs):
    if type is None:
        raise ValueError("Document type must be specified")
        
    template_path = os.path.join(os.path.dirname(__file__), 'documents', f"{type}.docx")

    try:
        doc = Document(template_path)
        
        # Function to replace placeholders in any paragraph
        def replace_placeholders_in_paragraph(paragraph):
            if not paragraph.runs:
                return
                
            # Combine all runs to reconstruct the entire paragraph text
            paragraph_text = ''.join([run.text for run in paragraph.runs])
            
            # Check if the paragraph contains any placeholders
            has_placeholders = False
            for key in kwargs.keys():
                placeholder = f"${{{key}}}"
                if placeholder in paragraph_text:
                    has_placeholders = True
                    paragraph_text = paragraph_text.replace(placeholder, str(kwargs[key]))
            
            # If placeholders were found, update all runs
            if has_placeholders:
                # Set the first run to the entire updated text
                paragraph.runs[0].text = paragraph_text
                
                # Clear the text from all other runs
                for run in paragraph.runs[1:]:
                    run.text = ""
        
        # Process paragraphs in the main document
        for paragraph in doc.paragraphs:
            replace_placeholders_in_paragraph(paragraph)
        
        # Process paragraphs in tables
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for paragraph in cell.paragraphs:
                        replace_placeholders_in_paragraph(paragraph)
        
        # Create filename for download
        output_filename = f'{type}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.docx'
        
        # Save to BytesIO
        from io import BytesIO
        doc_bytes = BytesIO()
        doc.save(doc_bytes)
        doc_bytes.seek(0)
        
        return doc_bytes, output_filename
    except Exception as e:
        print(f"Error generating document: {e}")
        return None, None

# def send_email(recipient_email, subject, body):
    """
    Отправляет email сообщение с использованием SMTP.
    """
    from email.mime.text import MIMEText
    import socket
    import time
    
    # Get email server settings from environment variables
    email_server = os.getenv('EMAIL_SERVER')
    email_port = os.getenv('EMAIL_SERVER_PORT')
    sender_email = os.getenv('SEND_FROM_EMAIL')
    sender_password = os.getenv('SEND_FROM_EMAIL_PASSWORD')
    
    # Try to get IP address from environment if available (bypass DNS)
    email_server_ip = os.getenv('EMAIL_SERVER_IP')
    
    # Configure basic logging
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO)
    
    # Log all configuration to help debug
    logging.info(f"Sending email to: {recipient_email}")
    logging.info(f"Email server: {email_server}:{email_port}")
    
    # Check if all required environment variables are set
    if not all([email_server, email_port, sender_email, sender_password]):
        error_msg = "Missing email configuration environment variables"
        logging.error(error_msg)
        return False
    
    # Prepare message
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = sender_email
    msg['To'] = recipient_email
    
    # List of servers to try (original server name + IP if provided)
    servers_to_try = [email_server]
    if email_server_ip:
        servers_to_try.insert(0, email_server_ip)  # Try IP address first if provided
    
    # Hard-coded IP fallbacks for common mail servers (as a last resort)
    mail_server_fallbacks = {
        'smtp.gmail.com': ['74.125.20.108', '74.125.20.109'],
        'mail.gh.uz': []  # Replace with actual IPs if known
    }
    
    if email_server in mail_server_fallbacks:
        servers_to_try.extend(mail_server_fallbacks[email_server])
    
    # Try to send with retries
    max_retries = 3
    retry_delay = 2  # seconds
    
    for attempt in range(max_retries):
        for server in servers_to_try:
            try:
                logging.info(f"Email sending attempt {attempt+1}/{max_retries} using server {server}")
                
                with smtplib.SMTP(server, int(email_port), timeout=10) as smtp:
                    try:
                        logging.info("Starting TLS")
                        smtp.starttls()
                        logging.info(f"Logging in as {sender_email}")
                        smtp.login(sender_email, sender_password)
                        logging.info(f"Sending email to {recipient_email}")
                        smtp.sendmail(sender_email, recipient_email, msg.as_string())
                        logging.info(f"Email sent successfully to {recipient_email}")
                        return True
                    except Exception as e:
                        logging.error(f"SMTP operation failed: {str(e)}")
                        continue
                        
            except (socket.gaierror, socket.timeout) as e:
                logging.warning(f"Network error with server {server}: {str(e)}")
                continue
            except Exception as e:
                logging.error(f"Unexpected error with server {server}: {str(e)}")
                continue
        
        # If we reach here, none of the servers worked in this attempt
        if attempt < max_retries - 1:
            logging.info(f"All servers failed. Retrying in {retry_delay} seconds...")
            time.sleep(retry_delay)
            retry_delay *= 2  # Exponential backoff
    
    logging.error("All email sending attempts failed")
    return False

def send_email(recipient_email, subject, body):
    """
    Отправляет email сообщение с использованием SMTP.
    """
    from email.mime.text import MIMEText
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = os.getenv('SEND_FROM_EMAIL') 
    msg['To'] = recipient_email

    try:
        with smtplib.SMTP(os.getenv('EMAIL_SERVER'), os.getenv('EMAIL_SERVER_PORT')) as server:
            server.starttls()
            server.login(os.getenv('SEND_FROM_EMAIL') , os.getenv('SEND_FROM_EMAIL_PASSWORD'))
            server.sendmail(os.getenv('SEND_FROM_EMAIL'), recipient_email, msg.as_string())
            logging.info("Email sent successfully")
    except Exception as e:
        logging.error(f"Failed to send email: {e}")
        time.sleep(10)
        send_email(recipient_email, subject, body)
        raise e

def format_phone_number(phone_number):
    match = re.match(r'^\+(\d{3}|\d{1})\.(\d{2})(\d{3})(\d{2})(\d{2})$', phone_number)
    if match:
        country_code = match.group(1)
        formatted_number = f'+{country_code} {match.group(2)} {match.group(3)} {match.group(4)} {match.group(5)}'
        return formatted_number
    return None
