# CalculatenTrade - Trading Calculator & Journal

A comprehensive Flask-based web application for trading calculations, position management, and trade journaling.

## Features

### 🧮 Trading Calculators
- **Intraday Calculator** - Calculate positions with 5x leverage
- **Delivery Calculator** - Long-term equity positions
- **Swing Calculator** - Medium-term trading positions  
- **MTF Calculator** - Margin Trading Facility positions
- **F&O Calculator** - Futures & Options calculations

### 📊 Trade Management
- Save and manage trading positions
- Position splitting with multiple stop-losses and targets
- Real-time market data integration (Dhan API)
- Pivot point calculations (Fibonacci levels)
- Risk-reward ratio analysis

### 📝 Trading Journal
- Comprehensive trade logging
- Strategy management
- Performance analytics
- Mistake tracking and learning
- Rule-based trading system

### 🔐 Authentication
- Email/Password registration with OTP verification
- Google OAuth 2.0 integration
- Secure session management
- Password reset functionality

### 👥 Multi-User Support
- User management system
- Admin dashboard
- Employee access controls
- Role-based permissions

## Technology Stack

- **Backend**: Flask (Python)
- **Database**: SQLite (dev) / PostgreSQL (prod)
- **Frontend**: HTML, CSS, JavaScript, Bootstrap
- **Authentication**: Flask-Login, Google OAuth 2.0
- **APIs**: Dhan Trading API
- **Deployment**: Nginx

## Quick Start

### Prerequisites
- Python 3.8+
- pip
- Git

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/Punitanand/calculatentrade-frontend-byMac.git
   cd calculatentrade-frontend-byMac
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Environment Setup**
   Create a `.env` file with:
   ```env
   FLASK_SECRET=your-secret-key-here
   GOOGLE_CLIENT_ID=your-google-client-id
   GOOGLE_CLIENT_SECRET=your-google-client-secret
   MAIL_USERNAME=your-email@gmail.com
   MAIL_PASSWORD=your-app-password
   DHAN_ACCESS_TOKEN=your-dhan-token
   DHAN_CLIENT_ID=your-dhan-client-id
   ```

4. **Database Setup**
   ```bash
   flask db upgrade
   ```

5. **Run the application**
   ```bash
   python app.py
   ```

6. **Access the app**
   Open http://localhost:5000 in your browser

## Configuration

### Google OAuth Setup
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable Google+ API
4. Create OAuth 2.0 credentials
5. Add authorized redirect URIs:
   - `http://localhost:5000/auth/google/callback` (development)
   - `https://yourdomain.com/auth/google/callback` (production)

### Dhan API Setup
1. Register at [Dhan](https://dhan.co/)
2. Generate API credentials
3. Add tokens to `.env` file



## API Endpoints

### Authentication
- `POST /register` - User registration
- `POST /login` - User login
- `GET /oauth/login` - Google OAuth login
- `GET /auth/google/callback` - OAuth callback

### Calculators
- `GET|POST /intraday_calculator` - Intraday trading calculator
- `GET|POST /delivery_calculator` - Delivery trading calculator
- `GET|POST /swing_calculator` - Swing trading calculator
- `GET|POST /mtf_calculator` - MTF calculator
- `GET|POST /fo_calculator` - F&O calculator

### Trade Management
- `POST /save_{type}_result` - Save calculation results
- `GET /saved_{type}` - View saved trades
- `GET /detail_{type}/<id>` - Trade details
- `POST /close_{type}_position` - Close position
- `POST /delete_{type}/<id>` - Delete trade

### Market Data
- `GET /search-equity-symbols` - Search stock symbols
- `GET /get-price/<symbol>` - Get live price
- `GET /get-market-depth/<symbol>` - Market depth data
- `GET /api/pivots/fibo` - Fibonacci pivot points

## Features in Detail

### Position Splitting
- Split large positions into multiple parts
- Set different stop-losses and targets for each part
- Visual representation of risk-reward scenarios
- Template saving for repeated strategies

### Pivot Point Analysis
- Fibonacci retracement levels
- Support and resistance calculations
- Integration with position planning
- Real-time market data correlation

### Risk Management
- Automatic R:R ratio calculations
- Capital allocation optimization
- Position sizing recommendations
- Risk percentage controls

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

For support, email punitanand146@gmail.com or create an issue on GitHub.

## Changelog

### v2.0.0 (Latest)
- ✅ Fixed Google OAuth "Invalid state parameter" issue
- ✅ Added stable session management
- ✅ Improved error logging and debugging
- ✅ Enhanced security with ProxyFix middleware
- ✅ Added Redis session support for production
- ✅ Multiple calculator types (Intraday, Delivery, Swing, MTF, F&O)
- ✅ Comprehensive trade management system
- ✅ Real-time market data integration

### v1.0.0
- Initial release with basic calculator functionality
- User authentication system
- Basic trade saving and management

---

**Made with ❤️ for traders by traders**