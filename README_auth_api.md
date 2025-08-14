# Auth API Endpoints & Authentication Guide

## Overview

This backend uses JWT authentication via AWS Cognito.  
**All protected API endpoints require a valid access token.**  
The frontend must handle login, token storage, and send the token with every API call.

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

All other endpoints (e.g., `/products`, `/product/<id>`, `/contact`, `/myip`) **require** the `Authorization: Bearer <access_token>` header.

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

## Summary

- Always send the `access_token` in the `Authorization` header for protected endpoints.
- Store tokens securely on the frontend.
- Use the refresh flow if the token expires.
- Only signup, verify, login, and password reset endpoints are public.

**All requests and responses use JSON format.**
