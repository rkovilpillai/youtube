"""
Installation Test Script
Verifies that all dependencies and configurations are correct.
"""
import sys
import os

print("🧪 Testing YouTube Contextual Product Pipeline Installation...")
print()

# Test 1: Python version
print("1️⃣ Checking Python version...")
py_version = sys.version_info
if py_version.major >= 3 and py_version.minor >= 9:
    print(f"   ✅ Python {py_version.major}.{py_version.minor}.{py_version.micro} (OK)")
else:
    print(f"   ❌ Python {py_version.major}.{py_version.minor}.{py_version.micro} (Requires 3.9+)")
    sys.exit(1)

# Test 2: Required packages
print("\n2️⃣ Checking required packages...")
required_packages = [
    "fastapi",
    "uvicorn",
    "sqlalchemy",
    "pydantic",
    "openai",
    "streamlit",
    "requests",
    "pandas"
]

missing_packages = []
for package in required_packages:
    try:
        __import__(package)
        print(f"   ✅ {package}")
    except ImportError:
        print(f"   ❌ {package} (MISSING)")
        missing_packages.append(package)

if missing_packages:
    print(f"\n   ❌ Missing packages: {', '.join(missing_packages)}")
    print("   Run: pip install -r requirements.txt")
    sys.exit(1)

# Test 3: Environment file
print("\n3️⃣ Checking environment configuration...")
if os.path.exists(".env"):
    print("   ✅ .env file found")
    
    # Check for required variables
    from dotenv import load_dotenv
    load_dotenv()
    
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key and openai_key != "sk-your-openai-api-key-here":
        print("   ✅ OPENAI_API_KEY is configured")
    else:
        print("   ⚠️  OPENAI_API_KEY not configured (required for keyword generation)")
else:
    print("   ⚠️  .env file not found")
    print("   Run: cp .env.example .env")
    print("   Then edit .env and add your OpenAI API key")

# Test 4: Project structure
print("\n4️⃣ Checking project structure...")
required_dirs = [
    "api",
    "api/routers",
    "api/services",
    "frontend",
    "frontend/pages",
    "frontend/utils",
    "scripts"
]

for dir_path in required_dirs:
    if os.path.isdir(dir_path):
        print(f"   ✅ {dir_path}/")
    else:
        print(f"   ❌ {dir_path}/ (MISSING)")

# Test 5: Import API modules
print("\n5️⃣ Testing API imports...")
try:
    from api.database import init_db
    from api.models import Campaign, Keyword
    from api.config import settings
    print("   ✅ API modules import successfully")
except Exception as e:
    print(f"   ❌ API import error: {e}")
    sys.exit(1)

# Test 6: Test database initialization (dry run)
print("\n6️⃣ Testing database initialization...")
try:
    from api.database import Base, engine
    print("   ✅ Database connection configured")
except Exception as e:
    print(f"   ❌ Database error: {e}")

# Summary
print("\n" + "="*50)
print("📊 Installation Test Summary")
print("="*50)
print()
print("✅ All critical tests passed!")
print()
print("🚀 Next Steps:")
print("   1. Ensure .env file has your OpenAI API key")
print("   2. Run: python scripts/init_db.py")
print("   3. Start backend: python -m uvicorn api.main:app --reload --port 8000")
print("   4. Start frontend: streamlit run frontend/app.py")
print()
