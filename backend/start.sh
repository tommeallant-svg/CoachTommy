#!/bin/sh

# Seed the database if requested
if [ "$SEED_DB" = "true" ]; then
    echo "Seeding database..."
    python seed.py
fi

uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
