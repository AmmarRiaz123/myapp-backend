# API Routes Reference

This document lists all API routes in the codebase, their methods, required request fields, and response structure.

---

## Auth Routes

### POST `/signup`
- **Body:**  
  - `email`, `password`, `username`, `phone_number`, `address`, `name`
- **Response:**  
  - Success: `{ "success": true, "message": "Please check your email for verification code" }`
  - Error: `{ "success": false, "message": "..." }`

### POST `/verify`
- **Body:**  
  - `email`, `code`
- **Response:**  
  - Success: `{ "success": true, "message": "Email verified successfully" }`
  - Error: `{ "success": false, "message": "..." }`

### POST `/login`
- **Body:**  
  - `password` and one of `username`, `email`, or `phone_number`
- **Response:**  
  - Success: `{ "success": true, "tokens": { "access_token": "...", "refresh_token": "...", "id_token": "..." } }`
  - Error: `{ "success": false, "message": "..." }`

### POST `/refresh`
- **Headers:**  
  - `Authorization: Bearer <access_token>`
- **Body:**  
  - `refresh_token`
- **Response:**  
  - Success: `{ "success": true, "tokens": { "access_token": "...", "id_token": "..." } }`
  - Error: `{ "success": false, "message": "..." }`

### POST `/logout`
- **Headers:**  
  - `Authorization: Bearer <access_token>`
- **Body:**  
  - `access_token`
- **Response:**  
  - Success: `{ "success": true, "message": "Logged out successfully" }`
  - Error: `{ "success": false, "message": "..." }`

### POST `/forgot-password`
- **Body:**  
  - `email`
- **Response:**  
  - Success: `{ "success": true, "message": "Password reset code sent to email" }`
  - Error: `{ "success": false, "message": "..." }`

### POST `/confirm-forgot-password`
- **Body:**  
  - `email`, `code`, `new_password`
- **Response:**  
  - Success: `{ "success": true, "message": "Password has been reset" }`
  - Error: `{ "success": false, "message": "..." }`

---

## Product Routes

### GET `/products`
- **Response:**  
  - Array of products:  
    `{ id, title, price, description, image, code, stock, type }`

### GET `/product/<id>`
- **Response:**  
  - `{ success, product, type_details, images, inventory }`

### GET `/product/code/<product_code>`
- **Response:**  
  - Same as `/product/<id>`

---

## Cart Routes

### POST `/cart/add`
- **Headers:**  
  - `Authorization: Bearer <access_token>`
- **Body:**  
  - `product_id`, `quantity` (default 1)
- **Response:**  
  - Success: `{ "success": true, "message": "Item added to cart" }`
  - Error: `{ "success": false, "message": "..." }`

### GET `/cart`
- **Headers:**  
  - `Authorization: Bearer <access_token>`
- **Response:**  
  - `{ "success": true, "items": [...] }`

---

## Order Routes

### POST `/checkout`
- **Headers:**  
  - `Authorization: Bearer <access_token>`
- **Response:**  
  - Success: `{ "success": true, "order_id": ... }`
  - Error: `{ "success": false, "message": "..." }`

### GET `/orders`
- **Headers:**  
  - `Authorization: Bearer <access_token>`
- **Response:**  
  - `{ "success": true, "orders": [...] }`

---

## Contact Route

### POST `/contact`
- **Body:**  
  - `name`, `email`, `phone`, `message`
- **Response:**  
  - Success: `{ "success": true, "message": "Form submitted successfully. Confirmation email sent and admin notified." }`
  - Error: `{ "success": false, "message": "..." }`

---

## Utility Route

### GET `/myip`
- **Response:**  
  - `{ "ipv4": "...", "ipv6": "..." }`
  - Error: `{ "error": "..." }`

---

## Admin Routes (Require Admin Token)

### GET `/admin/dashboard`
- **Headers:**  
  - `Authorization: Bearer <access_token>`
- **Response:**  
  - `{ "success": true, "summary": {...}, "low_stock_items": [...] }`

### PUT `/admin/inventory/<product_id>`
- **Headers:**  
  - `Authorization: Bearer <access_token>`
- **Body:**  
  - `quantity`
- **Response:**  
  - Success: `{ "success": true, "new_quantity": ... }`
  - Error: `{ "success": false, "message": "..." }`

### GET `/admin/orders`
- **Headers:**  
  - `Authorization: Bearer <access_token>`
- **Response:**  
  - `{ "success": true, "orders": [...] }`

### PUT `/admin/orders/<order_id>`
- **Headers:**  
  - `Authorization: Bearer <access_token>`
- **Body:**  
  - `status`
- **Response:**  
  - Success: `{ "success": true, "message": "Order status updated to ..." }`
  - Error: `{ "success": false, "message": "..." }`

### GET `/admin/products`
- **Headers:**  
  - `Authorization: Bearer <access_token>`
- **Response:**  
  - `{ "success": true, "products": [...] }`

### POST `/admin/products`
- **Headers:**  
  - `Authorization: Bearer <access_token>`
- **Body:**  
  - Product details (see code for fields)
- **Response:**  
  - Success: `{ "success": true, "product_id": ... }`
  - Error: `{ "success": false, "error": "..." }`

### GET `/admin/users`
- **Headers:**  
  - `Authorization: Bearer <access_token>`
- **Response:**  
  - `{ "success": true, "users": [...] }`

---

**All requests and responses use JSON format.**
**Protected and admin routes require the `Authorization: Bearer <access_token>` header.**
