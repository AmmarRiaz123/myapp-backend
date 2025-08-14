# Auth API Endpoints

## 1. Sign Up
- **POST** `/signup`
- **Required fields (JSON):**
  - `email` (string)
  - `password` (string)
  - `username` (string)
  - `phone_number` (string)
  - `address` (string)
  - `name` (string)
- **Response:**
  - Success: `{ "success": true, "message": "Please check your email for verification code" }`
  - Error: `{ "success": false, "message": "..." }`

## 2. Verify Email
- **POST** `/verify`
- **Required fields (JSON):**
  - `email` (string)
  - `code` (string)
- **Response:**
  - Success: `{ "success": true, "message": "Email verified successfully" }`
  - Error: `{ "success": false, "message": "..." }`

## 3. Login
- **POST** `/login`
- **Required fields (JSON):**
  - `password` (string)
  - One of: `username` (string) **OR** `email` (string) **OR** `phone_number` (string)
- **Response:**
  - Success: 
    ```
    {
      "success": true,
      "tokens": {
        "access_token": "...",
        "refresh_token": "...",
        "id_token": "..."
      }
    }
    ```
  - Error: `{ "success": false, "message": "..." }`

## 4. Refresh Token
- **POST** `/refresh`
- **Required fields (JSON):**
  - `refresh_token` (string)
- **Response:**
  - Success: `{ "success": true, "tokens": { "access_token": "...", "id_token": "..." } }`
  - Error: `{ "success": false, "message": "..." }`

## 5. Logout
- **POST** `/logout`
- **Required fields (JSON):**
  - `access_token` (string)
- **Response:**
  - Success: `{ "success": true, "message": "Logged out successfully" }`
  - Error: `{ "success": false, "message": "..." }`

## 6. Forgot Password
- **POST** `/forgot-password`
- **Required fields (JSON):**
  - `email` (string)
- **Response:**
  - Success: `{ "success": true, "message": "Password reset code sent to email" }`
  - Error: `{ "success": false, "message": "..." }`

## 7. Confirm Forgot Password
- **POST** `/confirm-forgot-password`
- **Required fields (JSON):**
  - `email` (string)
  - `code` (string)
  - `new_password` (string)
- **Response:**
  - Success: `{ "success": true, "message": "Password has been reset" }`
  - Error: `{ "success": false, "message": "..." }`

---

**All requests and responses use JSON format.**
