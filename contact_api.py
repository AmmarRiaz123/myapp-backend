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

        email_sent = send_confirmation_email(email, name)
        if not email_sent:
            return jsonify({'success': True, 'message': 'Contact form submitted, but failed to send confirmation email'}), 201

        return jsonify({'success': True, 'message': 'Contact form submitted successfully. Confirmation email sent.'}), 201

    except Exception as e:
        print(f"Error inserting contact: {e}")
        return jsonify({'success': False, 'message': 'Failed to submit contact form', 'error': str(e)}), 500

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()
