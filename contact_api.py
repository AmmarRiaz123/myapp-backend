import os
import smtplib
from email.message import EmailMessage
from flask import Blueprint, request, jsonify
import psycopg2
from psycopg2 import OperationalError, DatabaseError
import logging
from dotenv import load_dotenv
import socket
from time import sleep

load_dotenv()

contact_bp = Blueprint('contact', __name__)

logging.basicConfig(level=logging.INFO)  # You can configure to file if needed

def get_db_connection():
    """Create and return a database connection using environment variables."""
    try:
        conn = psycopg2.connect(
            host=os.environ.get('DB_HOST'),
            database=os.environ.get('DB_NAME'),
            user=os.environ.get('DB_USER'),
            password=os.environ.get('DB_PASSWORD'),
            port=os.environ.get('DB_PORT', 5432),
            sslmode=os.getenv('DB_SSLMODE', 'require')  # allow override locally
        )
        return conn
    except OperationalError as e:
        logging.error(f"Database connection error: {e}")
        return None


def validate_email_config():
    """Validate email configuration on startup."""
    required = ['ADMIN_GMAIL', 'ADMIN_GMAIL_PASSWORD']
    missing = [var for var in required if not os.getenv(var)]
    if missing:
        logging.error(f"Missing required email configuration: {', '.join(missing)}")
        return False
    return True


def send_email_with_retry(msg, max_retries=3, delay_seconds=1):
    """Send email with retry mechanism."""
    admin_email = os.environ.get('ADMIN_GMAIL')
    admin_password = os.environ.get('ADMIN_GMAIL_PASSWORD')
    proxy_host = os.environ.get('SMTP_PROXY_HOST')
    proxy_port = os.environ.get('SMTP_PROXY_PORT')

    for attempt in range(max_retries):
        try:
            # Configure socket timeout
            socket.setdefaulttimeout(30)  # 30 seconds timeout
            
            smtp_kwargs = {}
            if proxy_host and proxy_port:
                smtp_kwargs['source_address'] = (proxy_host, int(proxy_port))

            with smtplib.SMTP_SSL('smtp.gmail.com', 465, **smtp_kwargs) as smtp:
                smtp.login(admin_email, admin_password)
                smtp.send_message(msg)
            return True
        except smtplib.SMTPAuthenticationError as e:
            logging.error(f"SMTP Authentication failed: {e}")
            break  # No retry for auth failures
        except (socket.timeout, smtplib.SMTPConnectError) as e:
            logging.error(f"SMTP Connection error (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                sleep(delay_seconds * (attempt + 1))  # Exponential backoff
            continue
        except Exception as e:
            logging.error(f"Unexpected email error (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                sleep(delay_seconds * (attempt + 1))
            continue
    return False


def send_confirmation_email(user_email, user_name):
    """Send confirmation email to the user using admin Gmail."""
    if not validate_email_config():
        return False

    msg = EmailMessage()
    msg['Subject'] = 'Contact Form Submission Confirmation'
    msg['From'] = os.environ.get('ADMIN_GMAIL')
    msg['To'] = user_email
    msg.set_content(
        f"Dear {user_name},\n\n"
        "Thank you for contacting us. Your message has been received and our officer will get in touch with you soon.\n\n"
        "Best regards,\nAdmin Team"
    )

    return send_email_with_retry(msg)


def send_admin_notification(user_email, user_name, phone, message):
    """Send notification email to admin with the user's contact details."""
    if not validate_email_config():
        return False

    admin_email = os.environ.get('ADMIN_GMAIL')
    msg = EmailMessage()
    msg['Subject'] = 'New Contact Form Submission'
    msg['From'] = admin_email
    msg['To'] = admin_email
    msg.set_content(
        f"New contact form submission:\n\n"
        f"Name: {user_name}\n"
        f"Email: {user_email}\n"
        f"Phone: {phone}\n"
        f"Message: {message}\n"
    )

    return send_email_with_retry(msg)


# Add a test endpoint for email configuration
@contact_bp.route('/contact/test-email', methods=['GET'])
def test_email():
    """Test email configuration."""
    if not validate_email_config():
        return jsonify({
            'success': False,
            'message': 'Email configuration incomplete. Check ADMIN_GMAIL and ADMIN_GMAIL_PASSWORD.'
        }), 500

    admin_email = os.environ.get('ADMIN_GMAIL')
    msg = EmailMessage()
    msg['Subject'] = 'Test Email'
    msg['From'] = admin_email
    msg['To'] = admin_email
    msg.set_content('This is a test email to verify SMTP configuration.')

    if send_email_with_retry(msg):
        return jsonify({
            'success': True,
            'message': 'Test email sent successfully'
        })
    return jsonify({
        'success': False,
        'message': 'Failed to send test email. Check logs for details.'
    }), 500


@contact_bp.route('/contact', methods=['POST', 'OPTIONS'])
def contact():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        data = request.get_json(force=True)
    except Exception as e:
        logging.error(f"Invalid JSON input: {e}")
        return jsonify({'success': False, 'message': 'Invalid JSON data'}), 400

    name = data.get('name')
    email = data.get('email')
    phone = data.get('phone')
    message = data.get('message')

    if not all([name, email, phone, message]):
        logging.warning("Missing required fields in contact form submission.")
        return jsonify({'success': False, 'message': 'All fields are required'}), 400

    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'message': 'Database connection failed'}), 500

    cur = None
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO customers (name, email, phone, message) VALUES (%s, %s, %s, %s)",
            (name, email, phone, message)
        )
        conn.commit()
    except DatabaseError as e:
        logging.error(f"Database error inserting contact: {e}")
        return jsonify({'success': False, 'message': 'Failed to save contact information'}), 500
    except Exception as e:
        logging.error(f"Unexpected error inserting contact: {e}")
        return jsonify({'success': False, 'message': 'An unexpected error occurred while saving your contact'}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

    # Email notifications
    email_sent = send_confirmation_email(email, name)
    admin_notified = send_admin_notification(email, name, phone, message)

    if not email_sent and not admin_notified:
        return jsonify({'success': True, 'message': 'Form saved, but failed to send any emails'}), 201
    elif not email_sent:
        return jsonify({'success': True, 'message': 'Form saved, admin notified, but failed to send confirmation email'}), 201
    elif not admin_notified:
        return jsonify({'success': True, 'message': 'Form saved, confirmation email sent, but failed to notify admin'}), 201

    return jsonify({'success': True, 'message': 'Form submitted successfully. Confirmation email sent and admin notified.'}), 201
