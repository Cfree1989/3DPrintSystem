import sys
import os

# Add the project root directory to sys.path to allow imports from the 'app' module
# This assumes conftest.py is in the 'tests' directory, and 'app.py' is in the parent directory
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root) 