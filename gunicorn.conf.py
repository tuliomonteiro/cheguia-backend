import multiprocessing

bind = "0.0.0.0:8000"

# 2 workers per CPU core is a safe starting point for I/O-bound Django apps.
# Keep low initially; tune upward once you profile under real load.
workers = min(multiprocessing.cpu_count() * 2 + 1, 9)
worker_class = "sync"

# Must exceed the longest expected AI response time (OpenAI timeout = 30s)
timeout = 120
keepalive = 5
graceful_timeout = 30

# Log to stdout/stderr so Docker captures everything
accesslog = "-"
errorlog = "-"
loglevel = "info"
access_log_format = '%(h)s "%(r)s" %(s)s %(b)s %(D)sµs'
