#!/usr/bin/env sh
# Same reason as start-api.sh: run in a shell so $PORT expands. Railway injects PORT; 8501 is the
# local-default fallback. Streamlit binds 0.0.0.0 and runs headless (no "open a browser" prompt).
exec python -m streamlit run src/patchwork_assurance/ui/app.py \
  --server.port "${PORT:-8501}" --server.address 0.0.0.0 --server.headless true
