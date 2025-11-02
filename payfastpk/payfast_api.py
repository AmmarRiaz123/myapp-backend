import os
from flask import Blueprint, request, jsonify
import requests
import logging
from urllib.parse import urlencode
import hashlib
import uuid

payfast_bp = Blueprint('payfast', __name__)

DEFAULT_RETURN_URL = 'https://pekypk.com/payment-success'
DEFAULT_CANCEL_URL = 'https://pekypk.com/payment-cancel'

logging.basicConfig(level=logging.INFO)

def format_amount(amount):
    """Ensure amount is formatted to two decimal places as string."""
    try:
        return "{:.2f}".format(float(amount))
    except Exception as e:
        logging.error(f"Invalid amount format: {amount} ({e})")
        return "0.00"

def load_payfast_config():
    """
    Read PayFast configuration from environment at call time.
    Priority:
      1. PAYFAST_URL (explicit)
      2. PAYFAST_USE_SANDBOX (truthy) -> sandbox URL
      3. default to live URL
    Merchant credentials fall back to provided integration defaults if env vars are not set.
    """
    explicit_url = os.getenv('PAYFAST_URL')
    use_sandbox = os.getenv('PAYFAST_USE_SANDBOX', '').lower() in ('1', 'true', 'yes')
    sandbox_url = os.getenv('PAYFAST_SANDBOX_URL', 'https://sandbox.payfast.co.za/eng/process')
    live_url = 'https://www.payfast.co.za/eng/process'

    if explicit_url:
        url = explicit_url
    elif use_sandbox:
        url = sandbox_url
    else:
        url = os.getenv('PAYFAST_URL', live_url)

    merchant_id = os.getenv('PAYFAST_MERCHANT_ID') 
    merchant_key = os.getenv('PAYFAST_MERCHANT_KEY') 
    passphrase = os.getenv('PAYFAST_PASSPHRASE', '')

    # Log non-sensitive config for debugging
    if 'sandbox.payfast' in url:
        logging.info("Using PayFast SANDBOX environment for payments")
    else:
        logging.info("Using PayFast LIVE environment for payments")

    return {
        'merchant_id': merchant_id,
        'merchant_key': merchant_key,
        'url': url,
        'passphrase': passphrase
    }

def generate_signature(data, passphrase=''):
    """
    Generate PayFast signature:
    - Exclude 'signature' key.
    - Sort keys alphabetically.
    - URL encode key=value pairs (values stringified).
    - Append passphrase if provided.
    - MD5 hash the final string.
    """
    try:
        params = {k: v for k, v in data.items() if k != 'signature'}
        # ensure deterministic string conversion of values
        sorted_items = sorted((k, "" if v is None else str(v)) for k, v in params.items())
        param_str = urlencode(sorted_items)
        if passphrase:
            param_str += f"&passphrase={passphrase}"
        return hashlib.md5(param_str.encode('utf-8')).hexdigest()
    except Exception as e:
        logging.error(f"Error generating signature: {e}")
        return ""

def user_friendly_error(message, details=None):
    """Return a user-friendly error response and log details."""
    logging.error(f"PayFast error: {message}" + (f" Details: {details}" if details else ""))
    return jsonify({'success': False, 'message': message}), 400

@payfast_bp.route('/payfast/initiate', methods=['POST'])
def initiate_payment():
    try:
        data = request.get_json(force=True)
    except Exception as e:
        return user_friendly_error("Invalid JSON data provided.", str(e))

    try:
        cfg = load_payfast_config()

        amount_raw = data.get('amount')
        if amount_raw is None:
            return user_friendly_error("Amount is required for payment.")
        amount = format_amount(amount_raw)
        # ensure amount is positive and not zero
        try:
            if float(amount) <= 0:
                return user_friendly_error("Amount must be greater than zero.")
        except Exception:
            return user_friendly_error("Invalid amount provided.")

        item_name = data.get('item_name', 'Order Payment')
        return_url = data.get('return_url', DEFAULT_RETURN_URL)
        cancel_url = data.get('cancel_url', DEFAULT_CANCEL_URL)

        if not cfg['merchant_id'] or not cfg['merchant_key']:
            return user_friendly_error("Payment gateway is not configured. Please contact support.")

        # Build payfast payload; include optional fields if provided
        payfast_data = {
            'merchant_id': cfg['merchant_id'],
            'merchant_key': cfg['merchant_key'],
            'amount': amount,
            'item_name': item_name,
            'return_url': return_url,
            'cancel_url': cancel_url,
        }

        # include m_payment_id if supplied; otherwise generate one
        m_payment_id = data.get('m_payment_id') or str(uuid.uuid4())
        payfast_data['m_payment_id'] = m_payment_id

        # include optional customer email if provided
        email = data.get('email_address')
        if email:
            payfast_data['email_address'] = email

        signature = generate_signature(payfast_data, cfg['passphrase'])
        if not signature:
            return user_friendly_error("Failed to generate payment signature. Please try again.")

        payfast_data['signature'] = signature
        payment_url = f"{cfg['url']}?{urlencode(payfast_data)}"

        # Avoid logging secrets: log non-sensitive information only
        logging.info(f"Initiating PayFast payment: merchant_id={cfg['merchant_id']}, m_payment_id={m_payment_id}, amount={amount}, item_name={item_name}")

        return jsonify({'success': True, 'payment_url': payment_url})
    except Exception as e:
        return user_friendly_error("Failed to initiate payment. Please try again later.", str(e))

@payfast_bp.route('/payfast/callback', methods=['POST'])
def payfast_callback():
    try:
        post_data = request.form.to_dict()
        logging.info(f"PayFast callback received: keys={list(post_data.keys())}")

        if not post_data:
            return user_friendly_error("No callback data received from PayFast.")

        cfg = load_payfast_config()
        received_signature = post_data.get('signature', '')
        valid_signature = generate_signature(post_data, cfg['passphrase'])
        if not received_signature:
            return user_friendly_error("No signature received in callback.")
        if received_signature != valid_signature:
            logging.warning(f"Signature mismatch on callback: received!=expected")
            return user_friendly_error("Payment verification failed. Invalid signature received.")

        # TODO: Update order status in your database here
        # Example:
        # order_id = post_data.get('m_payment_id')
        # payment_status = post_data.get('payment_status')
        # logging.info(f"Update order {order_id} status to {payment_status}")
        # ...update order in DB...

        return jsonify({'success': True, 'message': 'Callback received and signature validated'}), 200
    except Exception as e:
        return user_friendly_error("Failed to process payment callback. Please contact support.", str(e))
