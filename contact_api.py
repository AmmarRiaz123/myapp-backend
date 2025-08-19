import os
import smtplib
from email.message import EmailMessage
from flask import Blueprint, request, jsonify
import psycopg2
from psycopg2 import OperationalError, DatabaseError
from psycopg2.extras import RealDictCursor
import logging
from dotenv import load_dotenv

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


def send_confirmation_email(user_email, user_name):
    """Send confirmation email to the user using admin Gmail."""
    admin_email = os.environ.get('ADMIN_GMAIL')
    admin_password = os.environ.get('ADMIN_GMAIL_PASSWORD')

    if not admin_email or not admin_password:
        logging.error("Admin Gmail credentials not set in environment variables.")
        return False

    msg = EmailMessage()
    msg['Subject'] = 'Contact Form Submission Confirmation'
    msg['From'] = admin_email
    msg['To'] = user_email
    msg.set_content(
        f"Dear {user_name},\n\n"
        "Thank you for contacting us. Your message has been received and our officer will get in touch with you soon.\n\n"
        "Best regards,\nAdmin Team"
    )

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(admin_email, admin_password)
            smtp.send_message(msg)
        return True
    except smtplib.SMTPAuthenticationError:
        logging.error("SMTP authentication failed. Check your Gmail credentials.")
    except smtplib.SMTPConnectError:
        logging.error("Unable to connect to Gmail SMTP server.")
    except Exception as e:
        logging.error(f"Unexpected error sending confirmation email: {e}")
    return False


def send_admin_notification(user_email, user_name, phone, message):
    """Send notification email to admin with the user's contact details."""
    admin_email = os.environ.get('ADMIN_GMAIL')
    admin_password = os.environ.get('ADMIN_GMAIL_PASSWORD')

    if not admin_email or not admin_password:
        logging.error("Admin Gmail credentials not set in environment variables.")
        return False

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

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(admin_email, admin_password)
            smtp.send_message(msg)
        return True
    except smtplib.SMTPAuthenticationError:
        logging.error("SMTP authentication failed. Check your Gmail credentials.")
    except smtplib.SMTPConnectError:
        logging.error("Unable to connect to Gmail SMTP server.")
    except Exception as e:
        logging.error(f"Unexpected error sending admin notification: {e}")
    return False


@contact_bp.route('/contact', methods=['POST'])
def contact():
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
