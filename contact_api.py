import os
from flask import Blueprint, request, jsonify
import psycopg2
import smtplib
from email.message import EmailMessage

contact_bp = Blueprint('contact', __name__)

def get_db_connection():
    """Create and return a database connection using environment variables"""
    try:
        conn = psycopg2.connect(
            host=os.environ.get('DB_HOST'),
            database=os.environ.get('DB_NAME'),
            user=os.environ.get('DB_USER'),
            password=os.environ.get('DB_PASSWORD'),
            port=os.environ.get('DB_PORT', 5432),
            sslmode='require'
        )
        return conn
    except Exception as e:
        print(f"Error connecting to database: {e}")
        return None

def send_confirmation_email(user_email, user_name):
    """Send confirmation email to the user using admin Gmail"""
    admin_email = os.environ.get('ADMIN_GMAIL')
    admin_password = os.environ.get('ADMIN_GMAIL_PASSWORD')
    if not admin_email or not admin_password:
        print("Admin Gmail credentials not set in environment variables.")
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
    except Exception as e:
        print(f"Error sending confirmation email: {e}")
        return False

def send_admin_notification(user_email, user_name, phone, message):
    """Send notification email to admin with the user's contact details"""
    admin_email = os.environ.get('ADMIN_GMAIL')
    admin_password = os.environ.get('ADMIN_GMAIL_PASSWORD')
    if not admin_email or not admin_password:
        print("Admin Gmail credentials not set in environment variables.")
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
    except Exception as e:
        print(f"Error sending admin notification email: {e}")
        return False

@contact_bp.route('/contact', methods=['POST'])
def contact():
    data = request.get_json(force=True)
    name = data.get('name')
    email = data.get('email')
    phone = data.get('phone')
    message = data.get('message')

    if not all([name, email, phone, message]):
        return jsonify({'success': False, 'message': 'All fields are required'}), 400

    conn = None
    cur = None
    try:
        conn = get_db_connection()
        if conn is None:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        cur = conn.cursor()
        # Insert into customers table (created_at is auto-set by DB)
        cur.execute(
            "INSERT INTO customers (name, email, phone, message) VALUES (%s, %s, %s, %s)",
            (name, email, phone, message)
        )
        conn.commit()

        # Send confirmation email to user
        email_sent = send_confirmation_email(email, name)
        # Send notification email to admin
        admin_notified = send_admin_notification(email, name, phone, message)

        if not email_sent and not admin_notified:
            return jsonify({'success': True, 'message': 'Contact form submitted, but failed to send emails'}), 201
        elif not email_sent:
            return jsonify({'success': True, 'message': 'Contact form submitted, admin notified, but failed to send confirmation email to user'}), 201
        elif not admin_notified:
            return jsonify({'success': True, 'message': 'Contact form submitted, confirmation email sent to user, but failed to notify admin'}), 201

        return jsonify({'success': True, 'message': 'Contact form submitted successfully. Confirmation email sent to user and admin notified.'}), 201

    except Exception as e:
        print(f"Error inserting contact: {e}")
        return jsonify({'success': False, 'message': 'Failed to submit contact form', 'error': str(e)}), 500

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()
