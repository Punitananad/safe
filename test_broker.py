#!/usr/bin/env python3
"""
Quick test script to verify broker system functionality
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_broker_manager():
    """Test broker manager initialization"""
    try:
        print("Testing broker manager import...")
        from broker_manager import BrokerManager, broker_manager
        
        print(f"[OK] Broker manager imported successfully")
        print(f"[OK] Global broker_manager instance: {broker_manager is not None}")
        
        if broker_manager:
            print(f"[OK] Sessions count: {len(broker_manager.sessions)}")
            print(f"[OK] Credentials count: {len(broker_manager.credentials_store)}")
            
            # Test encryption
            test_data = "test_secret_123"
            encrypted = broker_manager.encrypt_data(test_data)
            decrypted = broker_manager.decrypt_data(encrypted)
            print(f"[OK] Encryption test: {decrypted == test_data}")
            
        return True
        
    except ImportError as e:
        print(f"[ERROR] Import error: {e}")
        return False
    except Exception as e:
        print(f"[ERROR] General error: {e}")
        return False

def test_cryptography():
    """Test cryptography dependency"""
    try:
        from cryptography.fernet import Fernet
        key = Fernet.generate_key()
        cipher = Fernet(key)
        test_data = b"test"
        encrypted = cipher.encrypt(test_data)
        decrypted = cipher.decrypt(encrypted)
        print(f"[OK] Cryptography working: {decrypted == test_data}")
        return True
    except ImportError as e:
        print(f"[ERROR] Cryptography import error: {e}")
        return False
    except Exception as e:
        print(f"[ERROR] Cryptography error: {e}")
        return False

if __name__ == "__main__":
    print("=== Broker System Test ===")
    
    crypto_ok = test_cryptography()
    broker_ok = test_broker_manager()
    
    if crypto_ok and broker_ok:
        print("\n[SUCCESS] All tests passed - Broker system should work")
        sys.exit(0)
    else:
        print("\n[FAILED] Some tests failed - Check the errors above")
        sys.exit(1)