import os
from flask import Blueprint, request, jsonify
import psycopg2
from psycopg2 import OperationalError, DatabaseError
import logging
from dotenv import load_dotenv
import requests
from time import sleep

load_dotenv()

contact_bp = Blueprint('contact', __name__)
logging.basicConfig(level=logging.INFO)

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
    """Validate Resend API configuration."""
    if not os.getenv('RESEND_API_KEY'):
        logging.error("Missing RESEND_API_KEY environment variable")
        return False
    return True

def send_email_with_retry(to_email, subject, html_content, max_retries=3):
    """Send email using Resend API with retry mechanism."""
    api_key = os.getenv('RESEND_API_KEY')
    if not api_key:
        return False

    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    
    data = {
        'from': 'Peky PK <noreply@pekypk.com>',
        'to': [to_email],
        'subject': subject,
        'html': html_content
    }

    for attempt in range(max_retries):
        try:
            response = requests.post(
                'https://api.resend.com/emails',
                headers=headers,
                json=data
            )
            response.raise_for_status()
            logging.info(f"Email sent successfully to {to_email}")
            return True
        except requests.RequestException as e:
            logging.error(f"Failed to send email (attempt {attempt + 1}/{max_retries}): {str(e)}")
            if attempt < max_retries - 1:
                sleep(1)  # Simple delay between retries
    return False

def send_confirmation_email(user_email, user_name):
    """Send confirmation email using Resend."""
    if not validate_email_config():
        return False

    html_content = f"""
    <p>Dear {user_name},</p>
    <p>Thank you for contacting us. Your message has been received and our officer will get in touch with you soon.</p>
    <p>Best regards,<br>Admin Team</p>
    """

    return send_email_with_retry(
        user_email,
        'Contact Form Submission Confirmation',
        html_content
    )

def send_admin_notification(user_email, user_name, phone, message):
    """Send admin notification using Resend."""
    if not validate_email_config():
        return False

    admin_email = os.environ.get('ADMIN_EMAIL', 'admin@pekypk.com')
    html_content = f"""
    <h3>New Contact Form Submission</h3>
    <p><strong>Name:</strong> {user_name}</p>
    <p><strong>Email:</strong> {user_email}</p>
    <p><strong>Phone:</strong> {phone}</p>
    <p><strong>Message:</strong><br>{message}</p>
    """

    return send_email_with_retry(
        admin_email,
        'New Contact Form Submission',
        html_content
    )

@contact_bp.route('/contact', methods=['POST', 'OPTIONS'])
def contact():
    # Handle preflight requests
    if request.method == 'OPTIONS':
        response = jsonify({'success': True})
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        response.status_code = 200
        return response

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
