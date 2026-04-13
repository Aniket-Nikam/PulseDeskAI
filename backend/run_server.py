#!/usr/bin/env python
"""
PulseDesk Backend Startup Script
Ensures proper Python path and runs uvicorn server
"""
import sys
import os

# Add backend directory to path
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_dir)

# Now run uvicorn
from uvicorn.main import main

if __name__ == "__main__":
    sys.argv = ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
    main()
