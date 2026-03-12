"""Streamlit entrypoint wrapper for Community Cloud.

This executes the app located in app/streamlit_app.py so the
Streamlit "App file" can be set to streamlit_app.py at repo root.
"""
import runpy

runpy.run_path("app/streamlit_app.py", run_name="__main__")
