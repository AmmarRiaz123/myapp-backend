# Auth API Endpoints & Authentication Guide

## How to Get Tokens

After a successful login **(POST `/login` to your backend API)**, the backend returns a JSON response containing:
- `access_token` (used for all protected and admin API calls)
- `refresh_token` (used to get a new access token when the current one expires)
- `id_token` (optional, contains user info)

**You do NOT get this JSON from the Cognito callback route (`/callback`).**  
The `/callback` route is used for OAuth flows (like social login or hosted UI), not for direct API login.

**For direct API login (username/email/phone + password):**
- Send a POST request to `/login` on your backend.
- The backend will handle Cognito authentication and return the tokens in the JSON response.

**Example login request:**
```http
POST /login
Content-Type: application/json

{
  "username": "your_username", // or "email" or "phone_number"
  "password": "your_password"
}
```

**The response JSON is received from the `/login` route on your backend:**
```json
{
  "success": true,
  "tokens": {
    "access_token": "eyJraWQiOiJr...",
    "refresh_token": "eyJjdHkiOiJ...",
    "id_token": "eyJhbGciOiJSUzI1..."
  }
}
```

If you use Cognito's hosted UI or OAuth, the tokens are returned to your frontend at the callback URL (e.g., `/callback`), and you must extract them from the URL fragment or query parameters.

For most backend API login flows, use the `/login` route as described above.

**How to use the token:**
- Store the `access_token` securely on the frontend (e.g., in memory, localStorage, or cookies).
- For every protected or admin API call, include the token in the HTTP header:
  ```
  Authorization: Bearer <access_token>
  ```

**How to refresh the token:**
- When the `access_token` expires, use the `refresh_token` with the `/refresh` endpoint to get a new access token.

---

## Overview

This backend uses JWT authentication via AWS Cognito.  
**Some API endpoints are public, some require authentication, and some require admin privileges.**  
The frontend must handle login, token storage, and send the token with every API call to protected/admin endpoints.

---

## Route Access Levels

### Public Routes (No Authentication Required)
- `POST /signup`
- `POST /verify`
- `POST /login`
- `POST /forgot-password`
- `POST /confirm-forgot-password`
- `GET /products`
- `GET /product/<id>`
- `GET /product/code/<product_code>`
- `POST /contact`
- `GET /myip`

### Protected Routes (Require Auth: Any Logged-In User)
- `POST /cart/add`
- `GET /cart`
- `POST /checkout`
- `GET /orders`
- `POST /refresh`
- `POST /logout`

### Admin Routes (Require Auth: User Must Be Admin)
- `GET /admin/dashboard`
- `PUT /admin/inventory/<product_id>`
- `GET /admin/orders`
- `PUT /admin/orders/<order_id>`
- `GET /admin/products`
- `POST /admin/products`
- `GET /admin/users`
- `POST /admin/products` (create product)
- (Any other route under `/admin/...`)

---

## Authentication Flow

1. **Sign Up:**  
   User registers via `/signup`.  
   Backend sends a verification code to the user's email.

2. **Verify Email:**  
   User verifies their email via `/verify`.

3. **Login:**  
   User logs in via `/login` using username, email, or phone number and password.  
   Backend returns:
   - `access_token` (used for API calls)
   - `id_token` (optional, for user info)
   - `refresh_token` (used to get new access tokens)

4. **Token Storage:**  
   The frontend should securely store the `access_token` (e.g., in memory, localStorage, or cookies).

5. **Making Protected API Calls:**  
   For every API call to a protected endpoint, send the token in the HTTP header:
   ```
   Authorization: Bearer <access_token>
   ```
   Example (JavaScript/fetch):
   ```js
   fetch('/products', {
     method: 'GET',
     headers: {
       'Authorization': 'Bearer <access_token>',
       'Content-Type': 'application/json'
     }
   })
   ```

6. **Token Expiry & Refresh:**  
   If the access token expires, use `/refresh` with the `refresh_token` to get a new access token.  
   Always send the current `access_token` in the header for `/refresh`.

7. **Logout:**  
   Call `/logout` with the `access_token` to log out the user.

---

## Endpoints

### 1. Sign Up
- **POST** `/signup`
- **Body:**  
  ```json
  {
    "email": "string",
    "password": "string",
    "username": "string",
    "phone_number": "string",
    "address": "string",
    "name": "string"
  }
  ```
- **Response:**  
  - Success: `{ "success": true, "message": "Please check your email for verification code" }`
  - Error: `{ "success": false, "message": "..." }`
- **Auth Required:** No

### 2. Verify Email
- **POST** `/verify`
- **Body:**  
  ```json
  {
    "email": "string",
    "code": "string"
  }
  ```
- **Response:**  
  - Success: `{ "success": true, "message": "Email verified successfully" }`
  - Error: `{ "success": false, "message": "..." }`
- **Auth Required:** No

### 3. Login
- **POST** `/login`
- **Body:**  
  ```json
  {
    "password": "string",
    "username": "string" // OR "email": "string" OR "phone_number": "string"
  }
  ```
- **Response:**  
  ```json
  {
    "success": true,
    "tokens": {
      "access_token": "...",
      "refresh_token": "...",
      "id_token": "..."
    }
  }
  ```
- **Auth Required:** No

### 4. Refresh Token
- **POST** `/refresh`
- **Headers:**  
  `Authorization: Bearer <access_token>`
- **Body:**  
  ```json
  {
    "refresh_token": "string"
  }
  ```
- **Response:**  
  `{ "success": true, "tokens": { "access_token": "...", "id_token": "..." } }`
- **Auth Required:** Yes

### 5. Logout
- **POST** `/logout`
- **Headers:**  
  `Authorization: Bearer <access_token>`
- **Body:**  
  ```json
  {
    "access_token": "string"
  }
  ```
- **Response:**  
  `{ "success": true, "message": "Logged out successfully" }`
- **Auth Required:** Yes

### 6. Forgot Password
- **POST** `/forgot-password`
- **Body:**  
  ```json
  {
    "email": "string"
  }
  ```
- **Response:**  
  `{ "success": true, "message": "Password reset code sent to email" }`
- **Auth Required:** No

### 7. Confirm Forgot Password
- **POST** `/confirm-forgot-password`
- **Body:**  
  ```json
  {
    "email": "string",
    "code": "string",
    "new_password": "string"
  }
  ```
- **Response:**  
  `{ "success": true, "message": "Password has been reset" }`
- **Auth Required:** No

---

## Protected Endpoints

All endpoints listed under "Protected Routes" require the `Authorization: Bearer <access_token>` header.  
All endpoints listed under "Admin Routes" require the `Authorization: Bearer <access_token>` header and the user must belong to the `admin` group in Cognito.

---

## Error Handling

- If the token is missing or invalid, backend returns:
  ```json
  { "success": false, "message": "Token is missing" }
  ```
  or
  ```json
  { "success": false, "message": "Invalid token" }
  ```
  with HTTP status `401 Unauthorized`.

---

# Cognito App Client Callback URL

If you are using Cognito's **Hosted UI** or OAuth flows (social login, etc.), set your app client callback URL to the frontend route that will handle the authentication response and extract tokens.

**Example:**  
If your frontend is running at `http://localhost:3000`, set the callback URL in Cognito App Client settings to:
```
http://localhost:3000/callback
```
or any route in your frontend that is designed to handle the login response.

- For direct API login (username/email/phone + password via `/login`), **the callback URL is not used**.
- For Hosted UI/OAuth, the callback URL is where Cognito will redirect the user after login, with tokens in the URL.

**Summary:**  
- **Hosted UI/OAuth:** Set callback URL to your frontend handler (e.g., `/callback`).
- **Direct API login:** No callback URL needed; tokens are returned by your backend `/login` route.

---

## Summary

- **Public routes:** No token required.
- **Protected routes:** Require valid access token.
- **Admin routes:** Require valid access token and admin privileges.
- Always send the `access_token` in the `Authorization` header for protected/admin endpoints.
- Store tokens securely on the frontend.
- Use the refresh flow if the token expires.
- Only signup, verify, login, password reset, and product listing/details endpoints are public.

**All requests and responses use JSON format.**
