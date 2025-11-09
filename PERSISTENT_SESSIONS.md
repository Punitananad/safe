# Persistent User Sessions Implementation

## Overview
This implementation provides persistent user sessions that keep users logged in for 30 days without requiring them to log in repeatedly. Sessions are automatically extended based on user activity and only expire when:

1. User manually logs out
2. Session expires after 30 days of inactivity
3. User clears browser data

## Key Features

### Backend Changes (app.py)

1. **Session Configuration**:
   - `SESSION_COOKIE_HTTPONLY=True` - Prevents XSS attacks
   - `PERMANENT_SESSION_LIFETIME=timedelta(days=30)` - 30-day session duration
   - `SESSION_COOKIE_NAME='calculatentrade_session'` - Custom session name

2. **Login Modifications**:
   - `login_user(user, remember=True)` - Enables persistent login cookies
   - `session.permanent = True` - Makes session permanent
   - Added session metadata (user_id, login_time)

3. **Enhanced Security**:
   - `login_manager.session_protection = "strong"` - Protects against session hijacking
   - Session refresh on user activity
   - Automatic session cleanup

4. **New API Endpoints**:
   - `/api/session/status` - Check current session status
   - `/api/session/extend` - Manually extend session

### Frontend Changes

1. **Session Manager (session-manager.js)**:
   - Automatic session monitoring every 15 minutes
   - Activity-based session extension
   - Non-intrusive session expiry notifications
   - Manual session extension capability

2. **UI Enhancements**:
   - Active session indicator in sidebar
   - Session info display
   - Toast notifications for session events

## How It Works

### Login Process
1. User logs in (email/password or Google OAuth)
2. Flask-Login creates persistent session cookie
3. Session data stored with 30-day expiration
4. User stays logged in across browser sessions

### Session Maintenance
1. JavaScript monitors session status every 15 minutes
2. User activity triggers session extension
3. Session automatically extends every 24 hours if active
4. Backend refreshes session data on each request

### Session Expiry
1. Sessions expire after 30 days of inactivity
2. Manual logout clears all session data
3. Expired sessions are automatically cleaned up

## Security Considerations

1. **HTTPS Required**: In production, sessions use secure cookies
2. **HttpOnly Cookies**: Prevents JavaScript access to session cookies
3. **Session Protection**: Strong protection against session hijacking
4. **Activity Tracking**: Sessions extend only on genuine user activity

## Configuration

### Environment Variables
```env
FLASK_SECRET=your-secret-key-here
SESSION_PERMANENT_LIFETIME=2592000  # 30 days in seconds
```

### Production Settings
- `SESSION_COOKIE_SECURE=True` - HTTPS only
- `SESSION_COOKIE_SAMESITE='None'` - Cross-site compatibility

## Usage

### For Users
- Log in once and stay logged in for 30 days
- Sessions automatically extend with activity
- Manual logout when needed
- Clear indication of session status

### For Developers
- Session status API for debugging
- Configurable session duration
- Activity-based extension logic
- Comprehensive logging

## Testing

1. **Login Persistence**: Close browser, reopen - should stay logged in
2. **Activity Extension**: Use app regularly - session should extend
3. **Manual Logout**: Logout button should clear all session data
4. **Expiry Handling**: After 30 days of inactivity, should require re-login

## Monitoring

Check session status programmatically:
```javascript
// Get current session info
const sessionInfo = await window.sessionManager.getSessionInfo();
console.log(sessionInfo);

// Manually extend session
await window.sessionManager.manualExtendSession();
```

## Benefits

1. **Better User Experience**: No repeated login prompts
2. **Increased Engagement**: Users more likely to return
3. **Secure**: Proper session management with security best practices
4. **Configurable**: Easy to adjust session duration
5. **Transparent**: Clear session status for users