# Email Verification System Setup

This document explains the dual email configuration system implemented for CalculatenTrade.

## Overview

The system uses two separate Gmail accounts for different purposes:

1. **Admin Email** (`punitanand146@gmail.com`) - For sending notifications TO admin
2. **User Email** (`calculatentrade@gmail.com`) - For sending verification emails TO users

## Email Configuration

### Environment Variables

The system uses the following environment variables from your `.env` file:

```env
# Admin Email Configuration (for sending TO admin)
MAIL_USERNAME=punitanand146@gmail.com
MAIL_PASSWORD=jimbaarhqpdrtopx
MAIL_SENDER_NAME=CalculatenTrade Support

# User Email Configuration (hardcoded in email_service.py)
# calculatentrade@gmail.com
# Password: bccpjnvzbbsqmkcf
```

## Features Implemented

### 1. Email Verification for New Users
- Users must verify their email before they can log in
- 6-digit OTP sent to user's email
- OTP expires in 10 minutes
- Maximum 5 attempts per OTP
- Beautiful HTML email templates

### 2. Forgot Password Functionality
- Users can reset password using email verification
- 6-digit OTP sent to user's email
- OTP expires in 10 minutes
- Maximum 5 attempts per OTP
- Secure password policy enforcement

### 3. Account Deletion Verification
- Users must verify via email before account deletion
- 6-digit OTP sent to user's email
- OTP expires in 10 minutes
- Maximum 3 attempts per OTP
- Warning about permanent data loss

## Database Tables

The system creates the following tables:

### `users`
- `verified` column (BOOLEAN) - tracks email verification status

### `email_verify_otp`
- Stores OTPs for email verification during registration
- Includes expiration time and attempt tracking

### `reset_otp`
- Stores OTPs for password reset
- Includes expiration time and attempt tracking

### `delete_account_otp`
- Stores OTPs for account deletion verification
- Includes expiration time and attempt tracking

## Setup Instructions

### 1. Run Database Migration

```bash
cd CNT
python setup_email_verification.py
```

This will:
- Create all necessary database tables
- Test email configurations
- Create a test user for verification

### 2. Start the Application

```bash
python app.py
```

### 3. Test the System

1. **Register a new user** - Email verification will be required
2. **Try forgot password** - Password reset via email
3. **Test account deletion** - Requires email verification

## Email Templates

The system includes beautiful HTML email templates for:

- **Welcome/Verification Email** - Green theme with welcome message
- **Password Reset Email** - Blue theme with security focus
- **Account Deletion Email** - Red theme with warnings

## Security Features

### OTP Security
- 6-digit random OTPs
- Salted SHA-256 hashing
- Automatic expiration (10 minutes)
- Attempt limiting (3-5 attempts)
- One-time use enforcement

### Password Policy
- Minimum 8 characters
- At least 1 uppercase letter
- At least 1 lowercase letter
- At least 1 digit
- At least 1 special character

## API Endpoints

### Email Verification
- `POST /register` - Creates unverified user, sends OTP
- `GET|POST /verify-email` - Verify email with OTP
- `POST /verify-email/resend` - Resend verification OTP

### Password Reset
- `GET|POST /forgot-password` - Request password reset
- `GET|POST /verify-otp` - Verify OTP and set new password

### Account Management
- `POST /delete_account` - Request account deletion with email verification

## Email Service Usage

### Send User Email (Verification, Password Reset)
```python
from email_service import email_service

email_service.send_user_email(
    to="user@example.com",
    subject="Verification Code",
    html="<p>Your code: 123456</p>"
)
```

### Send Admin Email (Notifications)
```python
from email_service import email_service

email_service.send_admin_email(
    to="admin@example.com", 
    subject="New User Registration",
    html="<p>New user registered</p>"
)
```

## Troubleshooting

### Email Not Sending
1. Check Gmail app passwords are correct
2. Verify Gmail accounts have 2FA enabled
3. Check firewall/network restrictions
4. Review application logs for errors

### Database Issues
1. Run migration: `python setup_email_verification.py`
2. Check PostgreSQL connection
3. Verify table creation in database

### OTP Issues
1. Check system time synchronization
2. Verify OTP expiration settings
3. Clear old/expired OTPs from database

## Testing

### Manual Testing
1. Register new user with your email
2. Check email for verification code
3. Test forgot password flow
4. Test account deletion flow

### Email Testing Endpoint
Visit `/test-email` (requires login) to test email functionality.

## Production Considerations

1. **Email Limits** - Gmail has daily sending limits
2. **Monitoring** - Set up email delivery monitoring
3. **Backup** - Consider backup email service
4. **Security** - Regularly rotate app passwords
5. **Compliance** - Ensure GDPR/privacy compliance

## Support

For issues or questions:
- Check application logs
- Review database tables
- Test email configurations
- Contact: punitanand146@gmail.com