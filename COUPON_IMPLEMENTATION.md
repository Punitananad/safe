# Coupon System Implementation

This document describes the coupon functionality added to the CalculatenTrade subscription system.

## Overview

The coupon system allows users to apply discount codes during the checkout process to receive discounts on subscription plans. The implementation includes:

- ✅ Coupon entry in checkout/payment flow (pre-payment)
- ✅ Removed coupon fields from registration/login pages
- ✅ Server-side coupon validation API (`POST /api/apply-coupon`)
- ✅ Razorpay order creation with discounted amounts
- ✅ Coupon usage tracking and single-use enforcement
- ✅ Tamper-proof server-side validation

## Features

### 🎫 Coupon Validation
- **Case-insensitive** coupon codes
- **Expiry validation** (active/inactive status)
- **Single-use enforcement** per user
- **Minimum amount protection** (₹1 minimum)
- **Server-side validation** prevents tampering

### 💰 Discount Calculation
- **Percentage-based discounts** (configurable per coupon)
- **Real-time price updates** in the UI
- **Original vs final amount tracking**
- **Savings display** for user transparency

### 🔒 Security Features
- **Server-side amount calculation** (client cannot tamper)
- **Coupon usage tracking** in database
- **Payment verification** before coupon usage recording
- **Rollback protection** on payment failures

## Database Changes

### New Columns in `payments` table:
```sql
ALTER TABLE payments ADD COLUMN original_amount INTEGER NOT NULL DEFAULT 0;
ALTER TABLE payments ADD COLUMN discount_amount INTEGER NOT NULL DEFAULT 0;
ALTER TABLE payments ADD COLUMN coupon_code VARCHAR(50);
```

### New `coupon_usage` table:
```sql
CREATE TABLE coupon_usage (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    coupon_code VARCHAR(50) NOT NULL,
    payment_id INTEGER,
    discount_amount INTEGER NOT NULL,
    used_at DATETIME NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users (id),
    FOREIGN KEY (payment_id) REFERENCES payments (id)
);
```

## API Endpoints

### `POST /api/apply-coupon`
Validates coupon and returns discount metadata.

**Request:**
```json
{
    "coupon_code": "SAVE20",
    "plan_type": "monthly"
}
```

**Response (Success):**
```json
{
    "success": true,
    "coupon_code": "SAVE20",
    "discount_percent": 20,
    "original_amount": 2500,
    "discount_amount": 500,
    "final_amount": 2000,
    "savings": 500
}
```

**Response (Error):**
```json
{
    "success": false,
    "error": "Coupon code has already been used"
}
```

## User Flow

1. **Checkout Page**: User enters coupon code and clicks "Apply Coupon"
2. **Validation**: System validates coupon server-side via `/api/apply-coupon`
3. **Price Update**: UI shows original price (strikethrough) and discounted price
4. **Payment**: User proceeds with payment using discounted amount
5. **Order Creation**: Razorpay order created with final discounted amount
6. **Usage Tracking**: On successful payment, coupon usage is recorded

## Frontend Implementation

### Coupon Entry UI
```html
<div class="mb-3">
    <input type="text" id="monthly-coupon" class="form-control" placeholder="Enter coupon code (optional)">
    <button type="button" class="btn btn-outline-secondary btn-sm mt-2" onclick="applyCoupon('monthly')">
        Apply Coupon
    </button>
    <div id="monthly-coupon-result" class="mt-2"></div>
</div>
```

### JavaScript Functions
- `applyCoupon(planType)` - Validates and applies coupon
- `updatePriceDisplay(planType, finalAmount, discountAmount)` - Updates UI with discount
- `resetPriceDisplay(planType)` - Resets UI to original price

## Backend Implementation

### Key Functions
- `apply_coupon()` - API endpoint for coupon validation
- `create_order()` - Modified to handle coupon discounts
- `verify_payment()` - Records coupon usage on successful payment

### Validation Logic
1. Check coupon exists and is active
2. Verify user hasn't used this coupon before
3. Calculate discount amount
4. Apply minimum amount protection
5. Return discount metadata

## Testing

Run the test script to verify functionality:
```bash
python test_coupon_functionality.py
```

## Migration

Run the migration script to add required database fields:
```bash
python migrate_coupon_fields.py
```

## Admin Panel Integration

Coupons are managed through the existing admin panel:
- Navigate to `/admin/coupons`
- Create new coupons with discount percentages
- Toggle coupon active/inactive status
- View coupon usage statistics

## Security Considerations

1. **Server-side validation**: All coupon validation happens server-side
2. **Amount verification**: Client cannot manipulate final amounts
3. **Single-use enforcement**: Database constraints prevent multiple usage
4. **Payment verification**: Coupon usage only recorded after successful payment
5. **Rollback protection**: Failed payments don't consume coupon usage

## Error Handling

- Invalid coupon codes return appropriate error messages
- Expired/inactive coupons are rejected
- Already-used coupons show clear error messages
- Network errors are handled gracefully in the UI
- Database errors trigger rollbacks to maintain consistency

## Future Enhancements

Potential improvements for the coupon system:
- Usage count limits (instead of single-use only)
- Expiry date validation
- Minimum purchase amount requirements
- User-specific coupon assignments
- Bulk coupon generation
- Analytics and reporting dashboard