"""
Production Gunicorn Configuration for Dak Sahayak AI Backend.
Configured with multi-threaded gthread workers for non-blocking streaming AI & TTS endpoints.
"""

import os
import multiprocessing

# Network binding
bind = f"0.0.0.0:{os.environ.get('PORT', '5000')}"

# Concurrency & Worker Model
# For I/O bound streaming (SSE chat tokens & Edge-TTS audio), gthread allows multiple concurrent streams per worker
workers = int(os.environ.get("GUNICORN_WORKERS", 2))
threads = int(os.environ.get("GUNICORN_THREADS", 8))
worker_class = "gthread"

# Timeouts: Keepalive & long timeout for AI streaming generation and file synthesis
timeout = int(os.environ.get("GUNICORN_TIMEOUT", 120))
keepalive = 5

# Memory management & worker recycling
max_requests = 1000
max_requests_jitter = 100

# Logging
accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("LOG_LEVEL", "info")

# Graceful restarts
graceful_timeout = 30

