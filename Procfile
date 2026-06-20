api: uvicorn patchwork_assurance.api.main:app --reload --port 8000
ui: streamlit run src/patchwork_assurance/ui/app.py --server.port 8501 --server.headless true
site: python -m http.server 8080 --directory site
