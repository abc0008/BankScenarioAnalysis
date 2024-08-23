import sys
print(sys.path)

try:
    import flask_cors
    print("flask_cors imported successfully")
    print(flask_cors.__file__)
except ImportError as e:
    print(f"Error importing flask_cors: {e}")

try:
    from flask_cors import CORS
    print("CORS imported successfully")
except ImportError as e:
    print(f"Error importing CORS: {e}")