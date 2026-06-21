#!/usr/bin/env sh
# Railway exec's the service start command directly (no shell), so $PORT would arrive as the literal
# string "$PORT". Running through this script means a shell expands it. Railway injects PORT at runtime;
# 8000 is the local-default fallback.
exec python -m uvicorn patchwork_assurance.api.main:app --host 0.0.0.0 --port "${PORT:-8000}"
