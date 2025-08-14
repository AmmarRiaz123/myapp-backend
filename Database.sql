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
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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

-- Index for faster cart lookups
CREATE INDEX idx_cart_user_id ON cart(user_id);


ALTER TABLE products
ADD COLUMN rating DECIMAL(2,1) CHECK (rating >= 0 AND rating <= 5),
ADD COLUMN heat_resistant BOOLEAN DEFAULT FALSE,
ADD COLUMN eco_friendly BOOLEAN DEFAULT TRUE;

ALTER TABLE products
ALTER COLUMN heat_resistant SET DEFAULT TRUE;

-- View for admin dashboard
CREATE VIEW admin_dashboard AS
SELECT 
    COUNT(DISTINCT o.id) as total_orders,
    COUNT(DISTINCT o.customer_id) as unique_customers,
    SUM(oi.quantity) as total_items_sold,
    SUM(oi.quantity * oi.price) as total_revenue,
    (SELECT COUNT(*) FROM products) as total_products,
    (SELECT COUNT(*) FROM inventory WHERE quantity < 10) as low_stock_items
FROM orders o
LEFT JOIN order_items oi ON o.id = oi.order_id
WHERE o.created_at >= NOW() - INTERVAL '30 days';



