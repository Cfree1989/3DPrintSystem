import os

print("Attempting to read .env directly...")
try:
    with open(".env", "r") as f:
        print("File .env opened successfully.")
        for i in range(5): # Print first 5 lines
            line = f.readline()
            if not line:
                break
            print(f"Line {i+1}: {line.strip()}")
except FileNotFoundError:
    print("ERROR: .env file not found at path:", os.path.abspath(".env"))
except Exception as e:
    print(f"ERROR: Could not read .env file: {e}")
print("---------------------------------") 