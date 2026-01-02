#!/usr/bin/env python3
"""Test that user-imported modules are auto-excluded"""

import sys
sys.path.insert(0, '/home/khemadeva/hari/dev/code/remotegits/inkmcp/inkmcp')

from inkmcpcli import serialize_context_variables
import random
import json as json_module

# Simulate local environment with user imports
local_env = {
    'random': random,         # User import (should be auto-skipped)
    'json': json_module,      # System module (should be auto-skipped)
    'points': [(10, 20), (30, 40)],  # User data (should be included)
    'count': 5,               # User data (should be included)
}

# Don't manually exclude anything - test auto-detection
try:
    serializable = serialize_context_variables(local_env, exclude_names=set())
    print("✅ Serialization successful!")
    print(f"Serializable variables: {list(serializable.keys())}")
    print(f"Values: {serializable}")
    
    if 'random' in serializable or 'json' in serializable:
        print("❌ ERROR: Modules were not auto-excluded!")
    else:
        print("✅ Modules auto-excluded correctly")
        
    if 'points' in serializable and 'count' in serializable:
        print("✅ User data correctly included")
    else:
        print("❌ ERROR: User data was excluded!")
        
except Exception as e:
    print(f"❌ ERROR: {e}")
