#!/usr/bin/env python3
"""
FastAPI Server Startup Script

This script starts the FastAPI authentication server with proper configuration.
"""
import subprocess
import sys
import uvicorn
from app.core.config import settings


def check_system_dependencies():
    """Check and install system dependencies"""
    print("🔧 Checking system dependencies...")
    
    # Check if pdftoppm (poppler-utils) is available
    try:
        result = subprocess.run(
            ["pdftoppm", "-h"],
            capture_output=True,
            text=True,
            check=True
        )
        print("✅ poppler-utils is already installed")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("⚠️  poppler-utils not found. Attempting to install...")
        return install_poppler()


def install_poppler():
    """Install poppler-utils system dependency"""
    try:
        # Try to install poppler-utils
        print("📦 Installing poppler-utils...")
        result = subprocess.run(
            ["sudo", "apt-get", "update"],
            capture_output=True,
            text=True,
            check=True
        )
        
        result = subprocess.run(
            ["sudo", "apt-get", "install", "-y", "poppler-utils"],
            capture_output=True,
            text=True,
            check=True
        )
        print("✅ poppler-utils installed successfully!")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install poppler-utils: {e}")
        print("Please install manually:")
        print("   sudo apt-get update")
        print("   sudo apt-get install -y poppler-utils")
        return False
    except FileNotFoundError:
        print("⚠️  sudo/apt-get not available. Please install poppler-utils manually:")
        print("   Ubuntu/Debian: sudo apt-get install poppler-utils")
        print("   macOS: brew install poppler")
        print("   Windows: Download poppler binaries and add to PATH")
        return False


def install_dependencies():
    """Install dependencies using uv pip"""
    print("📦 Installing Python dependencies with uv...")
    try:
        result = subprocess.run(
            ["uv", "pip", "install", "-r", "requirements.txt"],
            capture_output=True,
            text=True,
            check=True
        )
        print("✅ Python dependencies installed successfully!")
        if result.stdout:
            print(f"Output: {result.stdout}")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install Python dependencies: {e}")
        print(f"Error output: {e.stderr}")
        print("🔄 Trying to continue anyway...")
    except FileNotFoundError:
        print("⚠️  uv not found. Please install dependencies manually:")
        print("   pip install -r requirements.txt")
        print("🔄 Continuing with server startup...")


def start_server():
    """Start the FastAPI server with configuration from settings"""
    print("🚀 Starting FastAPI Authentication Server...")
    print(f"📡 Server will be available at: http://{settings.server_host}:{settings.server_port}")
    print(f"📚 API Documentation: http://{settings.server_host}:{settings.server_port}/docs")
    print(f"🔄 Alternative docs: http://{settings.server_host}:{settings.server_port}/redoc")
    print(f"🔗 Database: {settings.database_name}")
    print("─" * 60)
    
    uvicorn.run(
        "app.main:app",
        host=settings.server_host,
        port=settings.server_port,
        reload=True,  # Enable auto-reload during development
        log_level="info",
        access_log=True
    )


if __name__ == "__main__":
    # Check system dependencies first
    system_deps_ok = check_system_dependencies()
    if not system_deps_ok:
        print("⚠️  Some system dependencies are missing. PDF processing may not work.")
    
    # Install Python dependencies
    install_dependencies()
    
    # Start the server
    start_server() 