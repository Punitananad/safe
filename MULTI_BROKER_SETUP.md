# Multi-Broker System Setup Guide

This guide will help you set up real broker connections for Kite (Zerodha), Dhan, and Angel One in your CalculatenTrade application.

## 🚀 Quick Start

1. **Install Dependencies**
   ```bash
   pip install -r requirements_multi_broker.txt
   ```

2. **Access Multi-Broker Page**
   - Navigate to: `http://localhost:5000/multi_broker_connect`
   - Or add a link in your navigation menu

## 🔧 Broker Setup Instructions

### 1. Kite (Zerodha) Setup

**Prerequisites:**
- Zerodha trading account
- Kite Connect app subscription (₹2000/month)

**Steps:**
1. Visit [Kite Connect](https://kite.trade/)
2. Create a new app and get:
   - API Key
   - API Secret
3. In the multi-broker page:
   - Enter your Kite User ID
   - Enter API Key and Secret
   - Click "Register Kite"
   - Click "Connect Kite" (will redirect to Zerodha login)

**Flow:**
- OAuth-based authentication
- Redirects to Zerodha login page
- Returns with access token after successful login

### 2. Dhan Setup

**Prerequisites:**
- Dhan trading account
- Dhan API access

**Steps:**
1. Login to [Dhan](https://dhan.co/)
2. Go to API section and generate:
   - Client ID
   - Access Token
3. In the multi-broker page:
   - Enter Client ID
   - Enter Access Token
   - Click "Register Dhan"
   - Click "Connect Dhan" (direct connection)

**Flow:**
- Direct token-based authentication
- Immediate connection with valid credentials

### 3. Angel One Setup

**Prerequisites:**
- Angel One trading account
- SmartAPI access enabled

**Steps:**
1. Visit [Angel One SmartAPI](https://smartapi.angelbroking.com/)
2. Register and get:
   - API Key
   - API Secret
3. Set up TOTP authenticator app
4. In the multi-broker page:
   - Enter your Angel User ID
   - Enter API Key and Secret
   - Optionally enter TOTP Secret for auto-generation
   - Click "Register Angel"
   - Click "Connect Angel" (will open login form)

**Flow:**
- Form-based authentication with TOTP
- Requires client code, password, and TOTP
- Returns JWT token for API access

## 📊 Available Data

Once connected, you can fetch:

### Orders
- Order book with all orders
- Order status and details
- Order history

### Trades
- Trade book with executed trades
- Trade details and timestamps
- P&L information

### Positions
- Current positions
- Position details and P&L
- Day and net positions

## 🔒 Security Features

- **Encrypted Storage**: All credentials are encrypted using Fernet encryption
- **Session Management**: Secure session handling with expiration
- **Token Refresh**: Automatic token refresh where supported
- **Local Storage**: Credentials stored locally with encryption

## 🛠️ Technical Implementation

### File Structure
```
CNT/
├── multi_broker_system.py          # Main broker system
├── templates/
│   ├── multi_broker_connect.html   # Connection interface
│   └── angel_login.html            # Angel One login form
├── requirements_multi_broker.txt   # Dependencies
└── MULTI_BROKER_SETUP.md          # This guide
```

### Key Components

1. **Multi-Broker System** (`multi_broker_system.py`)
   - Handles all three brokers
   - Real API connections
   - Session management
   - Data fetching

2. **Connection Interface** (`multi_broker_connect.html`)
   - Modern UI for broker management
   - Real-time status updates
   - Data fetching controls

3. **Integration** (in `app.py`)
   - Seamless integration with existing app
   - Route registration
   - Session handling

## 🔄 API Endpoints

### Registration
- `POST /api/multi_broker/register_app/{broker}` - Register credentials

### Authentication
- `GET /api/multi_broker/kite/login` - Kite OAuth login
- `GET /api/multi_broker/dhan/login` - Dhan direct login
- `GET /api/multi_broker/angel/login` - Angel login form

### Data Fetching
- `GET /api/multi_broker/{broker}/orders` - Get orders
- `GET /api/multi_broker/{broker}/trades` - Get trades
- `GET /api/multi_broker/{broker}/positions` - Get positions

### Status
- `GET /api/multi_broker/{broker}/status` - Connection status

## 🚨 Important Notes

### Kite (Zerodha)
- Requires paid Kite Connect subscription
- OAuth flow requires redirect URL setup
- Session expires daily, requires re-login

### Dhan
- Free API access available
- Direct token connection
- Long-lived access tokens

### Angel One
- Free SmartAPI access
- Requires TOTP authentication
- Session management with JWT tokens

## 🔧 Environment Variables

Add to your `.env` file:

```env
# Optional: Angel One API key for headers
ANGEL_API_KEY=your_angel_api_key

# App base URL for redirects
APP_BASE_URL=http://localhost:5000
```

## 🐛 Troubleshooting

### Common Issues

1. **Import Errors**
   ```bash
   pip install kiteconnect dhanhq smartapi-python pyotp
   ```

2. **Kite OAuth Issues**
   - Check redirect URL in Kite Connect app settings
   - Ensure API key is correct

3. **Dhan Connection Issues**
   - Verify Client ID and Access Token
   - Check token expiration

4. **Angel One Login Issues**
   - Ensure TOTP is correct and current
   - Check client code format

### Debug Mode

Enable debug logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 📈 Usage Examples

### Basic Connection Flow
1. Register credentials for desired broker
2. Click connect button
3. Complete authentication (varies by broker)
4. Fetch trading data using the interface

### Integration with Existing Features
- Use fetched data in your calculators
- Import positions for analysis
- Sync trades with journal

## 🔄 Updates and Maintenance

### Regular Tasks
- Monitor token expiration
- Update API credentials as needed
- Check for SDK updates

### Backup
- Export credentials before major updates
- Keep backup of encryption keys

## 📞 Support

For issues with:
- **Kite**: Contact Zerodha support
- **Dhan**: Contact Dhan support  
- **Angel One**: Contact Angel One support
- **Integration**: Check application logs

## 🎯 Next Steps

1. Install dependencies
2. Set up broker accounts and API access
3. Test connections with demo credentials
4. Integrate with your trading workflow
5. Monitor and maintain connections

---

**Made with ❤️ for real trading connections**