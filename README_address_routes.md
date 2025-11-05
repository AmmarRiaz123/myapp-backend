# Address Routes Integration Guide

This guide explains how to integrate with the address endpoints for shipping information.

## Available Endpoints

### 1. Get Provinces List
```http
GET /provinces
```
Returns list of available provinces for dropdowns.

**Response:**
```json
{
    "success": true,
    "provinces": [
        {"id": 1, "name": "Punjab"},
        {"id": 2, "name": "Sindh"},
        // ...etc
    ]
}
```

### 2. Create Shipping Address
```http
POST /shipping-address
```

**Request Body:**
```json
{
    "province_id": 1,        // Required: ID from provinces endpoint
    "city": "Lahore",        // Required: City name
    "street_address": "123 Main Street, Block A", // Required: Full street address
    "postal_code": "54000"   // Optional: Postal/ZIP code
}
```

**Success Response:**
```json
{
    "success": true,
    "address_id": 123,
    "message": "Shipping address created successfully"
}
```

**Error Response:**
```json
{
    "success": false,
    "message": "Missing required fields"
}
```

## Integration Steps

1. When loading checkout form:
   ```javascript
   // Fetch provinces for dropdown
   const response = await fetch('/provinces');
   const { provinces } = await response.json();
   // Populate your province select/dropdown
   ```

2. When submitting shipping info:
   ```javascript
   // Create shipping address first
   const addressResponse = await fetch('/shipping-address', {
     method: 'POST',
     headers: { 'Content-Type': 'application/json' },
     body: JSON.stringify({
       province_id: selectedProvinceId,
       city: cityInput,
       street_address: streetInput,
       postal_code: postalCode
     })
   });
   
   const { address_id } = await addressResponse.json();
   
   // Use this address_id when creating the order
   // or initiating payment (pass as m_payment_id)
   ```

## Important Notes

- All province_id values must come from the /provinces endpoint
- Store address_id returned from /shipping-address to use in order creation
- Shipping address creation should happen before order creation
- All endpoints return consistent success/error format

## Error Handling

Handle these common scenarios:
- Missing required fields (400)
- Invalid province_id (400)
- Server errors (500)

## Example Frontend Flow

```javascript
async function handleCheckout() {
  try {
    // 1. Create shipping address
    const addressResponse = await createShippingAddress({
      province_id: form.provinceId,
      city: form.city,
      street_address: form.streetAddress,
      postal_code: form.postalCode
    });

    if (!addressResponse.success) {
      throw new Error(addressResponse.message);
    }

    // 2. Use the address_id for order creation
    const { address_id } = addressResponse;
    
    // 3. Continue with payment initiation
    // Include address_id in your order or payment flow
    
  } catch (error) {
    // Handle errors appropriately
    showError(error.message);
  }
}
```

## Common Pitfalls

- Not validating province_id exists before submission
- Not handling missing required fields
- Not using the returned address_id in subsequent order creation
