-- CUSTOMERS (form-submitted customers)
CREATE TABLE customers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100),
    email VARCHAR(255),
    phone VARCHAR(20),
    message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- PRODUCTS (base table)
CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    product_code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    type VARCHAR(50) NOT NULL,                    -- 'aluminum_shape', 'cardboard_lid', 'pack', 'complement'
    material VARCHAR(100),                        -- e.g. 'aluminum', 'cardboard'
    food_safe BOOLEAN DEFAULT TRUE,
    recyclable BOOLEAN DEFAULT TRUE,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE aluminum_shapes (
    product_id INT PRIMARY KEY REFERENCES products(id) ON DELETE CASCADE,
    diameter_mm INT,
    height_mm INT,
    volume_cm3 INT
);

CREATE TABLE cardboard_lids (
    product_id INT PRIMARY KEY REFERENCES products(id) ON DELETE CASCADE,
    width_mm INT,
    length_mm INT,
    fits_product_code VARCHAR(50)                 -- Optional: link to compatible container
);

CREATE TABLE product_packs (
    product_id INT PRIMARY KEY REFERENCES products(id) ON DELETE CASCADE,
    pack_size INT,                                -- e.g. 10 containers per pack
    includes TEXT                                  -- optional: list or summary of what's inside
);

CREATE TABLE complements (
    product_id INT PRIMARY KEY REFERENCES products(id) ON DELETE CASCADE,
    specs TEXT                                     -- general specs, can be JSON if needed
);


-- PRODUCT IMAGES (multiple images per product)
CREATE TABLE product_images (
    id SERIAL PRIMARY KEY,
    product_id INT REFERENCES products(id) ON DELETE CASCADE,
    image_url TEXT NOT NULL,                          -- URL or path to image
    is_primary BOOLEAN DEFAULT FALSE
);

-- INVENTORY (track stock levels)
CREATE TABLE inventory (
    product_id INT PRIMARY KEY REFERENCES products(id) ON DELETE CASCADE,
    quantity INT NOT NULL
);

-- ORDERS (linked to customer + delivery address)
CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    customer_id INT REFERENCES customers(id) ON DELETE CASCADE,
    status VARCHAR(50) DEFAULT 'pending',             -- pending, shipped, delivered, etc.
    total_price NUMERIC(10,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    payment_status BOOLEAN DEFAULT FALSE NOT NULL
);

-- ORDER ITEMS (individual items in each order)
CREATE TABLE order_items (
    id SERIAL PRIMARY KEY,
    order_id INT REFERENCES orders(id) ON DELETE CASCADE,
    product_id INT REFERENCES products(id),
    quantity INT NOT NULL,
    price NUMERIC(10,2) NOT NULL                      -- price per unit at time of order
);

-- SHOPPING CART
CREATE TABLE cart (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,  -- Cognito user ID
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);



CREATE TABLE cart_items (
    id SERIAL PRIMARY KEY,
    cart_id INT REFERENCES cart(id) ON DELETE CASCADE,
    product_id INT REFERENCES products(id),
    quantity INT NOT NULL,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Add unique constraint to cart_items to prevent duplicate product entries per cart
ALTER TABLE cart_items 
    ADD CONSTRAINT IF NOT EXISTS unique_cart_product 
    UNIQUE (cart_id, product_id);

-- Index for faster cart lookups
CREATE INDEX idx_cart_user_id ON cart(user_id);


ALTER TABLE products
ADD COLUMN rating DECIMAL(2,1) CHECK (rating >= 0 AND rating <= 5),
ADD COLUMN heat_resistant BOOLEAN DEFAULT FALSE,
ADD COLUMN eco_friendly BOOLEAN DEFAULT TRUE;

ALTER TABLE products
ALTER COLUMN heat_resistant SET DEFAULT TRUE;

-- Add columns to store external payment identifiers and payloads (idempotent)
ALTER TABLE orders
    ADD COLUMN IF NOT EXISTS m_payment_id VARCHAR(255),
    ADD COLUMN IF NOT EXISTS payment_provider VARCHAR(100),
    ADD COLUMN IF NOT EXISTS payment_payload JSONB,
    ADD COLUMN IF NOT EXISTS payment_updated_at TIMESTAMP;

-- Index to quickly find orders by external payment id (e.g., m_payment_id)
CREATE INDEX IF NOT EXISTS idx_orders_m_payment_id ON orders(m_payment_id);

-- Table to record incoming payment provider notifications (ITN / callbacks)
CREATE TABLE IF NOT EXISTS payment_notifications (
    id SERIAL PRIMARY KEY,
    order_id INT REFERENCES orders(id) ON DELETE SET NULL,
    provider VARCHAR(100) NOT NULL,
    notification_payload JSONB,
    payment_status VARCHAR(50),
    received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Valid provinces lookup table
CREATE TABLE IF NOT EXISTS provinces (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL
);

-- Insert common Pakistan provinces
INSERT INTO provinces (name) VALUES 
    ('Punjab'),
    ('Sindh'),
    ('Khyber Pakhtunkhwa'),
    ('Balochistan'),
    ('Islamabad Capital Territory'),
    ('Gilgit-Baltistan'),
    ('Azad Kashmir')
ON CONFLICT (name) DO NOTHING;

-- Shipping addresses
CREATE TABLE IF NOT EXISTS shipping_addresses (
    id SERIAL PRIMARY KEY,
    province_id INT REFERENCES provinces(id),
    city VARCHAR(100) NOT NULL,
    street_address TEXT NOT NULL,
    postal_code VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Add address fields to orders
ALTER TABLE orders 
    ADD COLUMN IF NOT EXISTS shipping_address_id INT REFERENCES shipping_addresses(id),
    ADD COLUMN IF NOT EXISTS billing_address_id INT REFERENCES shipping_addresses(id);

-- Index for faster address lookups
CREATE INDEX IF NOT EXISTS idx_orders_shipping_address ON orders(shipping_address_id);
CREATE INDEX IF NOT EXISTS idx_orders_province ON shipping_addresses(province_id);

-- View for admin dashboard
DROP VIEW IF EXISTS admin_dashboard;
CREATE VIEW admin_dashboard AS
SELECT 
    COUNT(DISTINCT o.id) as total_orders,
    COUNT(DISTINCT o.customer_id) as unique_customers,
    COALESCE(SUM(oi.quantity), 0) as total_items_sold,
    COALESCE(SUM(oi.quantity * oi.price), 0) as total_revenue,
    (SELECT COUNT(*) FROM products) as total_products,
    (SELECT COUNT(*) FROM inventory WHERE quantity < 10) as low_stock_items,
    COUNT(DISTINCT o.id) FILTER (WHERE o.payment_status = TRUE) as paid_orders,
    COUNT(DISTINCT sa.province_id) as provinces_served
FROM orders o
LEFT JOIN order_items oi ON o.id = oi.order_id
LEFT JOIN shipping_addresses sa ON o.shipping_address_id = sa.id
WHERE o.created_at >= NOW() - INTERVAL '30 days';




