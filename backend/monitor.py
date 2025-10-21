#!/usr/bin/env python3
"""
Connection Pool Monitor
Monitors your Flask app's database connection health
"""

import requests
import time
import json
from datetime import datetime

API_URL = "https://jazzreference.onrender.com/api/health"
CHECK_INTERVAL = 60  # seconds

def check_health():
    """Check the health endpoint and return status"""
    try:
        response = requests.get(API_URL, timeout=10)
        data = response.json()
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        status = data.get('status', 'unknown')
        db_status = data.get('database', 'unknown')
        
        pool_stats = data.get('pool_stats', {})
        if pool_stats:
            pool_size = pool_stats.get('pool_size', 0)
            pool_available = pool_stats.get('pool_available', 0)
            requests_waiting = pool_stats.get('requests_waiting', 0)
            
            print(f"[{timestamp}] Status: {status} | DB: {db_status} | "
                  f"Pool: {pool_available}/{pool_size} available | "
                  f"Waiting: {requests_waiting}")
            
            # Alert if there are problems
            if status != 'healthy':
                print(f"  ⚠️  WARNING: App is unhealthy!")
            if pool_available == 0:
                print(f"  ⚠️  WARNING: No connections available in pool!")
            if requests_waiting > 0:
                print(f"  ⚠️  WARNING: {requests_waiting} requests waiting for connections!")
        else:
            print(f"[{timestamp}] Status: {status} | DB: {db_status} | Pool: not initialized")
        
        return True
        
    except requests.RequestException as e:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] ❌ ERROR: Failed to reach API - {e}")
        return False
    except Exception as e:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] ❌ ERROR: {e}")
        return False

def main():
    """Run continuous health monitoring"""
    print(f"Starting health monitoring for {API_URL}")
    print(f"Checking every {CHECK_INTERVAL} seconds...")
    print(f"Press Ctrl+C to stop\n")
    
    failures = 0
    
    try:
        while True:
            success = check_health()
            
            if not success:
                failures += 1
                if failures >= 3:
                    print(f"\n⚠️  ALERT: 3 consecutive failures detected!\n")
            else:
                failures = 0
            
            time.sleep(CHECK_INTERVAL)
            
    except KeyboardInterrupt:
        print("\n\nMonitoring stopped by user")

if __name__ == "__main__":
    main()