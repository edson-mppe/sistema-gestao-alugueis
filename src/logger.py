import sys

def _get_streamlit():
    """Safely attempts to import streamlit and checks if it's running."""
    try:
        import streamlit as st
        # This check might be insufficient in some versions, but combined with import it's a start.
        # Ideally we want to know if we are in a streamlit context.
        # st.runtime.exists() is available in newer streamlit versions.
        if hasattr(st, 'runtime') and hasattr(st.runtime, 'exists') and st.runtime.exists():
            return st
        elif hasattr(st, 'script_runner'): # Older versions
             return st
        return None
    except ImportError:
        return None

def log_error(msg):
    st = _get_streamlit()
    if st:
        st.error(msg)
    else:
        sys.stderr.write(f"[ERROR] {msg}\n")

def log_warning(msg):
    st = _get_streamlit()
    if st:
        st.warning(msg)
    else:
        sys.stderr.write(f"[WARNING] {msg}\n")

def log_info(msg):
    st = _get_streamlit()
    if st:
        st.info(msg)
    else:
        print(f"[INFO] {msg}")
