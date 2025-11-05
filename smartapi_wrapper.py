"""
SmartApi wrapper to prevent network calls during import
"""
import os

# Check if we should disable network calls
DISABLE_NETWORK = os.environ.get('SMARTAPI_DISABLE_NETWORK', '0') == '1'

if DISABLE_NETWORK:
    # Mock SmartConnect class to prevent network calls during import
    class SmartConnect:
        def __init__(self, *args, **kwargs):
            self.api_key = kwargs.get('api_key', '')
            
        def generateSession(self, *args, **kwargs):
            return {"errorcode": "NETWORK_DISABLED", "message": "Network calls disabled during import"}
            
        def getfeedToken(self):
            return "mock_feed_token"
            
        def holding(self):
            return []
            
        def position(self):
            return []
            
        def orderBook(self):
            return []
            
        def tradeBook(self):
            return []
else:
    try:
        from SmartApi import SmartConnect
    except ImportError:
        SmartConnect = None
    except Exception as e:
        print(f"Warning: SmartApi import failed: {e}")
        SmartConnect = None