#!/usr/bin/env python3
"""
Test script to demonstrate WhatsApp functionality for mentor coupons
"""

def generate_whatsapp_message(coupon_code, discount_percent, base_url="http://localhost:5000"):
    """Generate WhatsApp message with auto-applied coupon link"""
    subscription_url = f"{base_url}/subscription?coupon={coupon_code}&auto_apply=true"
    
    message = f"""Exclusive {discount_percent}% OFF on Calculate N Trade Premium!

Use coupon code: {coupon_code}
Click here to get discount: {subscription_url}

- Advanced trading calculators
- Real-time market data
- Trade journal & analytics
- Risk management tools

Upgrade now and save {discount_percent}%!"""
    
    return message, subscription_url

def generate_whatsapp_url(message):
    """Generate WhatsApp sharing URL"""
    import urllib.parse
    encoded_message = urllib.parse.quote(message)
    return f"https://wa.me/?text={encoded_message}"

def test_whatsapp_functionality():
    """Test the WhatsApp functionality"""
    print("=== WhatsApp Coupon Sharing Test ===\n")
    
    # Test data
    test_coupons = [
        {"code": "SAV30", "discount": 30},
        {"code": "MENTOR20", "discount": 20},
        {"code": "SPECIAL50", "discount": 50}
    ]
    
    for coupon in test_coupons:
        print(f"Testing coupon: {coupon['code']} ({coupon['discount']}% OFF)")
        print("-" * 50)
        
        # Generate message and URL
        message, subscription_url = generate_whatsapp_message(
            coupon['code'], 
            coupon['discount']
        )
        
        whatsapp_url = generate_whatsapp_url(message)
        
        print("Generated Message:")
        print(message)
        print(f"\nDirect Subscription URL: {subscription_url}")
        print(f"\nWhatsApp Share URL: {whatsapp_url}")
        print("\n" + "="*70 + "\n")

def test_url_parameters():
    """Test URL parameter parsing"""
    print("=== URL Parameter Test ===\n")
    
    test_urls = [
        "http://localhost:5000/subscription?coupon=SAV30&auto_apply=true",
        "http://localhost:5000/subscription?coupon=MENTOR20&auto_apply=true",
        "http://localhost:5000/subscription?coupon=SPECIAL50&auto_apply=false"
    ]
    
    for url in test_urls:
        print(f"URL: {url}")
        
        # Parse URL parameters
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        
        coupon = params.get('coupon', [None])[0]
        auto_apply = params.get('auto_apply', [None])[0]
        
        print(f"  Coupon: {coupon}")
        print(f"  Auto Apply: {auto_apply}")
        print(f"  Should auto-apply: {'Yes' if auto_apply == 'true' else 'No'}")
        print()

if __name__ == "__main__":
    test_whatsapp_functionality()
    test_url_parameters()
    
    print("All tests completed!")
    print("\nTo test the functionality:")
    print("1. Start your Flask app: python app.py")
    print("2. Login as a mentor")
    print("3. Go to /mentor/coupons")
    print("4. Click the WhatsApp button next to any coupon")
    print("5. The WhatsApp message will be generated with auto-apply link")
    print("6. When users click the link, the coupon will be automatically applied")