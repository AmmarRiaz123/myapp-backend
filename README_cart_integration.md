# Cart Integration Guide for Frontend

This guide explains how to integrate with the cart system that supports both guest users and authenticated users.

## Cart System Overview

The cart system automatically handles:
- **Guest users**: Session-based cart using browser sessions
- **Authenticated users**: User-based cart linked to their account
- **Cart merging**: When guests log in, their cart merges with their account cart

## Available Endpoints

### 1. Add Item to Cart
```http
POST /cart/add
```

**Request Body:**
```json
{
    "product_id": 123,           // Required: Product ID to add
    "quantity": 2,               // Optional: Default is 1
    "user_id": "optional_id"     // Optional: For backwards compatibility
}
```

**Response:**
```json
{
    "success": true,
    "message": "Item added to cart",
    "user_id": "guest_abc123",   // Cart identifier (guest ID or auth user ID)
    "user_type": "guest"         // "guest" or "authenticated"
}
```

### 2. Get Cart Items
```http
GET /cart?user_id=optional_id
```

**Query Parameters:**
- `user_id` (optional): For backwards compatibility

**Response:**
```json
{
    "success": true,
    "items": [
        {
            "cart_item_id": 1,
            "product_id": 123,
            "product_name": "Aluminum Container",
            "product_code": "ALU001",
            "quantity": 2,
            "price": 19.99
        }
    ]
}
```

### 3. Update Cart Item
```http
POST /cart/update
```
**Note**: Requires authentication (Authorization header)

**Request Body:**
```json
{
    "product_id": 123,
    "quantity": 5                // Set to 0 to remove item
}
```

## Frontend Integration Steps

### For Guest Users (No Login Required)

1. **Add items to cart** - Just call the API, no user management needed:
   ```javascript
   const addToCart = async (productId, quantity = 1) => {
     const response = await fetch('/cart/add', {
       method: 'POST',
       headers: { 'Content-Type': 'application/json' },
       body: JSON.stringify({
         product_id: productId,
         quantity: quantity
       })
     });
     
     const data = await response.json();
     if (data.success) {
       // Store the user_id for future reference (optional)
       localStorage.setItem('cart_user_id', data.user_id);
     }
     return data;
   };
   ```

2. **Get cart items**:
   ```javascript
   const getCart = async () => {
     const response = await fetch('/cart');
     return response.json();
   };
   ```

### For Authenticated Users

1. **Include Authorization header** in all requests:
   ```javascript
   const addToCart = async (productId, quantity = 1) => {
     const token = localStorage.getItem('access_token');
     
     const response = await fetch('/cart/add', {
       method: 'POST',
       headers: {
         'Content-Type': 'application/json',
         'Authorization': `Bearer ${token}`
       },
       body: JSON.stringify({
         product_id: productId,
         quantity: quantity
       })
     });
     return response.json();
   };
   ```

### Cart Merging (Guest → Authenticated)

When a guest user logs in, their cart automatically merges with their account. No additional frontend work needed.

**Optional**: Use the cart merge endpoint for explicit control:
```javascript
const mergeGuestCart = async (guestId, authToken) => {
  const response = await fetch('/checkout/cart-merge', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${authToken}`
    },
    body: JSON.stringify({ guest_id: guestId })
  });
  return response.json();
};
```

## Complete Cart Component Example (React)

```javascript
import { useState, useEffect } from 'react';

const Cart = ({ isAuthenticated, authToken }) => {
  const [cartItems, setCartItems] = useState([]);
  const [loading, setLoading] = useState(false);

  // Fetch cart items
  const fetchCart = async () => {
    setLoading(true);
    try {
      const headers = {
        'Content-Type': 'application/json'
      };
      
      if (isAuthenticated && authToken) {
        headers['Authorization'] = `Bearer ${authToken}`;
      }
      
      const response = await fetch('/cart', { headers });
      const data = await response.json();
      
      if (data.success) {
        setCartItems(data.items);
      }
    } catch (error) {
      console.error('Error fetching cart:', error);
    } finally {
      setLoading(false);
    }
  };

  // Add item to cart
  const addToCart = async (productId, quantity = 1) => {
    try {
      const headers = {
        'Content-Type': 'application/json'
      };
      
      if (isAuthenticated && authToken) {
        headers['Authorization'] = `Bearer ${authToken}`;
      }
      
      const response = await fetch('/cart/add', {
        method: 'POST',
        headers,
        body: JSON.stringify({
          product_id: productId,
          quantity: quantity
        })
      });
      
      const data = await response.json();
      if (data.success) {
        fetchCart(); // Refresh cart
      }
      return data;
    } catch (error) {
      console.error('Error adding to cart:', error);
    }
  };

  // Load cart on component mount
  useEffect(() => {
    fetchCart();
  }, [isAuthenticated]);

  if (loading) return <div>Loading cart...</div>;

  return (
    <div>
      <h2>Shopping Cart ({cartItems.length} items)</h2>
      {cartItems.map(item => (
        <div key={item.cart_item_id}>
          <h3>{item.product_name}</h3>
          <p>Code: {item.product_code}</p>
          <p>Quantity: {item.quantity}</p>
          <p>Price: ${item.price}</p>
          <p>Total: ${(item.quantity * item.price).toFixed(2)}</p>
        </div>
      ))}
    </div>
  );
};

export default Cart;
```

## Important Notes

1. **Session Handling**: For guest users, the cart uses browser sessions. Make sure your app supports cookies.

2. **No User Management Required**: The backend automatically handles guest vs authenticated users - you don't need to manage user IDs manually.

3. **Backwards Compatibility**: The old `user_id` parameter still works if you were using it before.

4. **Authentication**: For authenticated features (like cart updates), include the Authorization header.

5. **Error Handling**: Always check the `success` field in responses and handle errors appropriately.

6. **Cart Persistence**: 
   - Guest carts persist during browser session
   - Authenticated user carts persist across sessions
   - Cart merging happens automatically on login

## Testing the Integration

### Manual Testing Commands

```bash
# Add item to cart (guest)
curl -X POST http://localhost:5000/cart/add \
  -H "Content-Type: application/json" \
  -d '{"product_id": 1, "quantity": 2}'

# Get cart (guest)
curl -X GET http://localhost:5000/cart

# Add item to cart (authenticated)
curl -X POST http://localhost:5000/cart/add \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"product_id": 1, "quantity": 2}'
```

## Common Issues & Solutions

1. **Session not working**: Make sure your app supports cookies and sessions
2. **CORS issues**: The backend is configured for your domains, but verify origins
3. **Token expiry**: Handle 401 responses by refreshing the auth token
4. **Cart not persisting**: For guests, ensure cookies/sessions are enabled

## Next Steps

After implementing the cart:
1. Test both guest and authenticated flows
2. Test cart merging by adding items as guest, then logging in
3. Implement the checkout flow using `/checkout/initiate`
4. Add cart item removal/update functionality
