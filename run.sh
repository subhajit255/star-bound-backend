#!/bin/bash
# Activate the project-specific virtual environment
source venv/bin/activate

# Run Uvicorn through Python to ensure it uses the venv packages and not global ones
exec python -m uvicorn app.main:app --reload
