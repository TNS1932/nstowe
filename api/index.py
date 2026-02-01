# Simple Vercel serverless entry referencing the FastAPI app
# Vercel will import this module and use `app` as the ASGI entrypoint.
from main import app
