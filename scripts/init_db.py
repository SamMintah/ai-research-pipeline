#!/usr/bin/env python3
"""
Database initialization script
"""

from src.database import create_tables

if __name__ == "__main__":
    print("Creating database tables...")
    create_tables()
    print("Database tables created successfully!")