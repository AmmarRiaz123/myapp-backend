import os
from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv

# Import blueprints
from product_api import product_bp
from product_detail_api import product_detail_bp
from contact_api import contact_bp
from myip_api import my_ip
from auth.auth_routes import auth_bp
from cart_routes import cart_bp
from order_routes import order_bp
from payfastpk.payfast_api import payfast_bp
# from meow
# Admin blueprints
from routes.admin.dashboard import admin_dashboard_bp
from routes.admin.inventory_management import admin_inventory_bp
from routes.admin.order_management import admin_orders_bp
from routes.admin.product_management import admin_products_bp

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Updated CORS configuration with proper preflight handling
CORS(
    app,
    resources={
        r"/*": {
            "origins": [
                "http://localhost:3000",
                "https://web-production-b093f.up.railway.app",
                "https://abundant-achievement-production-88e5.up.railway.app",
                "https://pekypk.com",
                "https://www.pekypk.com"
            ],
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization", "X-Requested-With"],
            "expose_headers": ["Content-Type", "Authorization"],
            "supports_credentials": False,
            "max_age": 600  # Cache preflight requests for 10 minutes
        }
    }
)

# Add CORS headers for error responses
@app.after_request
def after_request(response):
    if response.status_code == 405:  # Method Not Allowed
        allow_methods = response.headers.get('Allow', '').split(', ')
        if 'OPTIONS' not in allow_methods:
            allow_methods.append('OPTIONS')
        response.headers['Allow'] = ', '.join(allow_methods)
    return response

# Register blueprints
app.register_blueprint(product_bp)
app.register_blueprint(product_detail_bp)
app.register_blueprint(contact_bp)
app.register_blueprint(auth_bp, url_prefix='/auth')
app.register_blueprint(cart_bp)
app.register_blueprint(order_bp)
app.register_blueprint(payfast_bp)
app.register_blueprint(admin_dashboard_bp)
app.register_blueprint(admin_inventory_bp)
app.register_blueprint(admin_orders_bp)
app.register_blueprint(admin_products_bp)

# Extra route
app.add_url_rule('/myip', view_func=my_ip)

if __name__ == '__main__':
    app.run(
        debug=True,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000))
    )
