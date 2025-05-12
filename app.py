from app import create_app
from config import Config
import os

# Get absolute paths
base_dir = os.path.abspath(os.path.dirname(__file__))
instance_dir = os.path.join(base_dir, 'instance')

# Ensure instance directory exists
os.makedirs(instance_dir, exist_ok=True)

# Update database path to use absolute path
Config.SQLALCHEMY_DATABASE_URI = f'sqlite:///{os.path.join(instance_dir, "app.db")}'

app = create_app(Config)

if __name__ == '__main__':
    app.run(debug=True)
