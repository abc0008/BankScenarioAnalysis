import sys
print("Python version:", sys.version)
print("Python path:", sys.path)

try:
    import os
    print("os imported successfully")
    print("Current working directory:", os.getcwd())
except ImportError as e:
    print(f"Error importing os: {e}")

try:
    from flask import Flask
    print("Flask imported successfully")
except ImportError as e:
    print(f"Error importing Flask: {e}")

from importlib import util
print("os module:", util.find_spec("os"))
print("flask module:", util.find_spec("flask"))