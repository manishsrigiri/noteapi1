import base64
import json
import os
import uuid
from datetime import datetime
from urllib.parse import quote_plus

import pandas as pd
import requests
import streamlit as st

def _load_local_env(path: str = ".env") -> None:
    if not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                os.environ.setdefault(key, value)
    except OSError:
        return


_load_local_env()

API_BASE_URL = os.getenv("API_BASE_URL", "http://fastapi:8000")
PUBLIC_API_BASE_URL = os.getenv("PUBLIC_API_BASE_URL", "http://localhost:8000")
PUBLIC_STREAMLIT_URL = os.getenv("PUBLIC_STREAMLIT_URL", "http://localhost:8501")
API_URL = f"{API_BASE_URL}/notes"

THEMES = {
    "Light": {
        "bg": "#f7f4ef",
        "surface": "#fffefb",
        "ink": "#1f2937",
        "muted": "#6b7280",
        "accent": "#c2410c",
        "accent_soft": "#ffedd5",
        "border": "#fed7aa",
    },
    "Dark": {
        "bg": "#0b1020",
        "surface": "#111827",
        "ink": "#e5e7eb",
        "muted": "#94a3b8",
        "accent": "#22d3ee",
        "accent_soft": "#083344",
        "border": "#155e75",
    },
    "Forest": {
        "bg": "#f1f5f2",
        "surface": "#fcfffd",
        "ink": "#1b4332",
        "muted": "#4f6f52",
        "accent": "#2d6a4f",
        "accent_soft": "#d8f3dc",
        "border": "#95d5b2",
    },
    "Modern": {
        "bg": "#f8fafc",
        "surface": "#ffffff",
        "ink": "#1e293b",
        "muted": "#64748b",
        "accent": "#2563eb",
        "accent_soft": "#eff6ff",
        "border": "#e2e8f0",
    },
}

st.set_page_config(page_title="NoteAPI Studio", layout="wide", initial_sidebar_state="expanded")


def rerun() -> None:
    if hasattr(st, "rerun"):
        st.rerun()
    else:
        st.experimental_rerun()


def apply_theme(theme_name: str) -> None:
    t = THEMES.get(theme_name, THEMES["Light"])
    st.markdown(
        f"""
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
            
            html, body, [data-testid="stAppViewContainer"] {{
                font-family: 'Inter', sans-serif !important;
                background-color: {t["bg"]} !important;
            }}
            
            .stApp {{
                background: {t["bg"]};
                color: {t["ink"]};
            }}
            
            /* Top Bar */
            .top-bar {{
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                height: 64px;
                background: {t["surface"]};
                border-bottom: 1px solid {t["border"]};
                z-index: 1000000;
                display: flex;
                align-items: center;
                padding: 0 24px;
                justify-content: space-between;
                box-shadow: 0 1px 3px rgba(0,0,0,0.05);
            }}
            
            .logo-section {{
                display: flex;
                align-items: center;
                gap: 10px;
                font-weight: 700;
                font-size: 1.25rem;
                color: {t["ink"]};
                padding-left: 60px; /* Space for the floating Menu button */
            }}
            
            .search-container {{
                flex: 1;
                max-width: 600px;
                position: absolute;
                left: 50%;
                transform: translateX(-50%);
            }}
            
            .search-input {{
                width: 100%;
                padding: 10px 16px 10px 42px;
                border-radius: 20px;
                border: 1px solid {t["border"]};
                background: {t["bg"]};
                outline: none;
                transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
                color: {t["ink"]};
                box-shadow: inset 0 2px 4px rgba(0,0,0,0.02);
            }}
            
            .search-input:focus {{
                border-color: {t["accent"]};
                box-shadow: 0 0 0 3px {t["accent_soft"]}, inset 0 2px 4px rgba(0,0,0,0.02);
            }}
            
            .nav-icons {{
                display: flex;
                align-items: center;
                gap: 20px;
                color: {t["muted"]};
            }}
            
            .profile-pic {{
                width: 36px;
                height: 36px;
                border-radius: 50%;
                background: #e2e8f0;
                object-fit: cover;
            }}

            /* Actions Bar */
            .actions-bar {{
                margin-top: 64px;
                padding: 16px 24px;
                display: flex;
                justify-content: flex-end;
                background: transparent;
            }}

            /* Sidebar Overhaul */
            section[data-testid="stSidebar"] {{
                background-color: {t["bg"]} !important;
                border-right: 1px solid {t["border"]} !important;
                padding-top: 80px !important;
            }}
            
            [data-testid="stSidebarNav"] {{
                display: none !important;
            }}
            
            .sidebar-item {{
                display: flex;
                align-items: center;
                gap: 12px;
                padding: 10px 16px;
                border-radius: 8px;
                color: {t["muted"]};
                font-weight: 500;
                cursor: pointer;
                transition: all 0.2s;
                margin-bottom: 4px;
            }}
            
            .sidebar-item:hover {{
                background-color: {t["accent_soft"]};
                color: {t["accent"]};
            }}
            
            .sidebar-item.active {{
                background-color: {t["accent_soft"]};
                color: {t["accent"]};
                border-left: 4px solid {t["accent"]};
                border-radius: 0 8px 8px 0;
            }}

            /* Force Sidebar Width and Visibility */
            section[data-testid="stSidebar"] {{
                min-width: 300px !important;
                max-width: 300px !important;
                width: 300px !important;
                transform: none !important;
                visibility: visible !important;
                display: flex !important;
            }}
            
            [data-testid="stSidebarCollapseButton"] {{
                display: none !important;
            }}

            /* Note Cards */
            .note-card {{
                background: {t["surface"]};
                border: 1px solid {t["border"]};
                border-radius: 12px;
                padding: 20px;
                margin-bottom: 16px;
                transition: box-shadow 0.2s;
                position: relative;
                cursor: pointer;
            }}
            
            .note-card:hover {{
                box-shadow: 0 4px 12px rgba(0,0,0,0.05);
            }}
            
            .note-card.active {{
                border-color: {t["accent"]};
                background-color: {t["accent_soft"]};
            }}
            
            .note-title {{ font-weight: 600; font-size: 1rem; color: {t["ink"]}; margin-bottom: 4px; }}
            .note-meta {{ font-size: 0.85rem; color: {t["muted"]}; display: flex; justify-content: space-between; align-items: center; }}
            .tag {{ 
                padding: 2px 8px; 
                border-radius: 4px; 
                font-size: 0.75rem; 
                font-weight: 600; 
                background: {t["bg"]}; 
                color: {t["muted"]};
            }}

            /* Editor Area */
            .editor-container {{
                background: {t["surface"]};
                border: 1px solid {t["border"]};
                border-radius: 12px;
                padding: 24px;
                height: 100%;
                display: flex;
                flex-direction: column;
            }}
            
            .editor-header {{ font-size: 1.5rem; font-weight: 700; color: {t["ink"]}; margin-bottom: 20px; }}
            
            /* Streamlit Overrides - Premium Polish */
            div.stButton > button {{
                border-radius: 10px;
                font-weight: 600;
                transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
                border: 1px solid {t["border"]};
                background-color: {t["surface"]};
                color: {t["ink"]};
            }}
            
            div.stButton > button:hover {{
                border-color: {t["accent"]};
                color: {t["accent"]};
                transform: translateY(-1px);
                box-shadow: 0 4px 12px rgba(0,0,0,0.05);
            }}
            
            .new-note-btn > div > button {{
                background-color: {t["accent"]} !important;
                color: white !important;
                border: none !important;
                padding: 10px 24px !important;
                box-shadow: 0 4px 14px {t["accent_soft"]} !important;
            }}
            
            .save-btn > div > button {{
                background-color: #10b981 !important; /* Emerald 500 */
                color: white !important;
                border: none !important;
                padding: 8px 24px !important;
            }}

            .save-btn > div > button:hover {{
                background-color: #059669 !important; /* Emerald 600 */
                box-shadow: 0 4px 14px rgba(16, 185, 129, 0.3) !important;
            }}
            
            .delete-btn > div > button {{
                background-color: #ef4444 !important; /* Red 500 */
                color: white !important;
                border: none !important;
                padding: 8px 24px !important;
            }}

            .delete-btn > div > button:hover {{
                background-color: #dc2626 !important; /* Red 600 */
                box-shadow: 0 4px 14px rgba(239, 68, 68, 0.3) !important;
            }}

            /* Better contrast for inputs */
            div[data-testid="stTextInput"] input, div[data-testid="stTextArea"] textarea {{
                background-color: {t["surface"]} !important;
                color: {t["ink"]} !important;
                border: 1px solid {t["border"]} !important;
                border-radius: 10px !important;
            }}

            /* Hide default streamlit elements */
            header, [data-testid="stHeader"] {{
                background: transparent !important;
            }}
            
            #MainMenu, footer, [data-testid="stToolbar"] {{
                visibility: hidden;
            }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def apply_background(
    mode: str,
    solid: str,
    grad_start: str,
    grad_end: str,
    grad_dir: str,
    image_b64: str | None,
    image_content_type: str | None,
    image_fit: str,
    image_scale: int,
    image_pos_x: int,
    image_pos_y: int,
) -> None:
    if mode == "Theme Default":
        return
    page_bg_css = ""
    overlay_css = ""
    if mode == "Solid":
        page_bg_css = f"background: {solid} !important;"
    elif mode == "Gradient":
        page_bg_css = f"background: linear-gradient({grad_dir}, {grad_start}, {grad_end}) !important;"
    elif mode == "Image" and image_b64:
        size_css = "cover"
        if image_fit == "Contain":
            size_css = "contain"
        elif image_fit == "Actual":
            size_css = f"{image_scale}% auto"
        content_type = image_content_type or "image/png"
        overlay_css = (
            "background-image: "
            f"url('data:{content_type};base64,{image_b64}') !important;"
            f"background-size: {size_css} !important;"
            f"background-position: {image_pos_x}% {image_pos_y}% !important;"
            "background-repeat: no-repeat !important;"
            "background-attachment: fixed !important;"
            "background-color: transparent !important;"
            "image-rendering: -webkit-optimize-contrast !important;"
            "image-rendering: crisp-edges !important;"
        )
    else:
        return

    extra_css = ""
    if mode == "Image":
        extra_css = """
            html, body, .stApp, .stAppViewContainer {
                background: transparent !important;
                min-height: 100%;
            }
            body::before {
                content: "";
                position: fixed;
                inset: 0;
                z-index: -1;
                pointer-events: none;
            }
            header, [data-testid="stToolbar"], [data-testid="stHeader"] {
                background: transparent !important;
                backdrop-filter: none !important;
            }
            .stApp {
                min-height: 100vh;
            }
            section[data-testid="stSidebar"] {
                background: rgba(10, 15, 30, 0.70) !important;
                backdrop-filter: blur(8px);
            }
            .note-card, .stMetric {
                background-color: rgba(17, 24, 39, 0.72) !important;
                backdrop-filter: blur(6px);
            }
        """

    st.markdown(
        f"""
        <style>
            html, body, .stApp, .stAppViewContainer, section.main {{
                {page_bg_css}
            }}
            body::before {{
                {overlay_css}
            }}
            {extra_css}
        </style>
        """,
        unsafe_allow_html=True,
    )


def _ensure_ui_defaults() -> None:
    st.session_state.setdefault("theme_name", "Dark")
    st.session_state.setdefault("bg_mode", "Theme Default")
    st.session_state.setdefault("bg_solid", "#0b1020")
    st.session_state.setdefault("bg_grad_start", "#0b1020")
    st.session_state.setdefault("bg_grad_end", "#1f2937")
    st.session_state.setdefault("bg_grad_dir", "to bottom right")
    st.session_state.setdefault("bg_gallery", [])
    st.session_state.setdefault("bg_image_id", None)
    st.session_state.setdefault("bg_image_fit", "Cover")
    st.session_state.setdefault("bg_image_scale", 100)
    st.session_state.setdefault("bg_image_pos_x", 50)
    st.session_state.setdefault("bg_image_pos_y", 50)
    st.session_state.setdefault("hide_sidebar", False)
    st.session_state.setdefault("focus_mode", False)
    st.session_state.setdefault("focus_tasks", [])
    st.session_state.setdefault("sidebar_manual_override", False)


def _apply_prefs_to_state(prefs: dict) -> None:
    if not isinstance(prefs, dict):
        return
    if prefs.get("theme"):
        st.session_state["theme_name"] = prefs.get("theme")
    if prefs.get("background_mode"):
        st.session_state["bg_mode"] = prefs.get("background_mode")
    if prefs.get("background_solid"):
        st.session_state["bg_solid"] = prefs.get("background_solid")
    if prefs.get("background_gradient_start"):
        st.session_state["bg_grad_start"] = prefs.get("background_gradient_start")
    if prefs.get("background_gradient_end"):
        st.session_state["bg_grad_end"] = prefs.get("background_gradient_end")
    if prefs.get("background_gradient_dir"):
        st.session_state["bg_grad_dir"] = prefs.get("background_gradient_dir")
    if isinstance(prefs.get("backgrounds"), list):
        st.session_state["bg_gallery"] = prefs.get("backgrounds")
    if prefs.get("background_image_id"):
        st.session_state["bg_image_id"] = prefs.get("background_image_id")
    if prefs.get("background_image_fit"):
        st.session_state["bg_image_fit"] = prefs.get("background_image_fit")
    if prefs.get("background_image_scale") is not None:
        st.session_state["bg_image_scale"] = prefs.get("background_image_scale")
    if prefs.get("background_image_pos_x") is not None:
        st.session_state["bg_image_pos_x"] = prefs.get("background_image_pos_x")
    if prefs.get("background_image_pos_y") is not None:
        st.session_state["bg_image_pos_y"] = prefs.get("background_image_pos_y")
    if prefs.get("hide_sidebar") is not None:
        if not st.session_state.get("sidebar_manual_override"):
            st.session_state["hide_sidebar"] = prefs.get("hide_sidebar")


def _default_prefs_payload() -> dict:
    return {
        "theme": "Dark",
        "background_mode": "Theme Default",
        "background_solid": "#0b1020",
        "background_gradient_start": "#0b1020",
        "background_gradient_end": "#1f2937",
        "background_gradient_dir": "to bottom right",
        "background_image_id": None,
        "background_image_fit": "Cover",
        "background_image_scale": 100,
        "background_image_pos_x": 50,
        "background_image_pos_y": 50,
        "backgrounds": [],
        "hide_sidebar": False,
    }


def _reset_preferences() -> None:
    defaults = _default_prefs_payload()
    _apply_prefs_to_state(defaults)
    st.session_state["bg_gallery"] = []
    st.session_state["bg_image_id"] = None
    st.session_state["hide_sidebar"] = False
    _, pref_error = auth_request("PUT", "/auth/preferences", payload=defaults)
    if pref_error:
        st.error(pref_error)


def _current_bg_image_b64() -> str | None:
    bg_id = st.session_state.get("bg_image_id")
    for item in st.session_state.get("bg_gallery", []):
        if item.get("id") == bg_id:
            return item.get("data_b64")
    return None


def _current_bg_content_type() -> str | None:
    bg_id = st.session_state.get("bg_image_id")
    for item in st.session_state.get("bg_gallery", []):
        if item.get("id") == bg_id:
            return item.get("content_type", "image/png")
    return None


def _encode_background_uploads(uploads) -> list[dict]:
    items = []
    for upload in uploads or []:
        raw = upload.read()
        if not raw:
            continue
        if len(raw) > 1_500_000:
            st.sidebar.warning(f"{upload.name} is too large. Keep images under 1.5MB.")
            continue
        items.append(
            {
                "id": uuid.uuid4().hex[:12],
                "name": upload.name,
                "content_type": upload.type or "image/png",
                "data_b64": base64.b64encode(raw).decode("ascii"),
            }
        )
    return items


def _set_bg_mode_image() -> None:
    st.session_state["bg_mode"] = "Image"


def _show_sidebar() -> None:
    st.session_state["hide_sidebar"] = False


def api_request(method: str, path: str = "", payload=None):
    url = API_URL if not path else f"{API_URL}/{path.lstrip('/')}"
    headers = {}
    auth_token = st.session_state.get("auth_token")
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"
    last_error = None
    for attempt in range(3):
        try:
            response = requests.request(method, url, json=payload, headers=headers, timeout=60)
            break
        except requests.RequestException as exc:
            last_error = exc
            if attempt < 2:
                continue
            return None, f"Network error: {exc}"

    if response.status_code >= 400:
        try:
            return None, response.json().get("detail", "Request failed")
        except ValueError:
            return None, f"Request failed ({response.status_code})"

    if not response.text.strip():
        return {}, None
    return response.json(), None


def auth_request(method: str, path: str, payload=None):
    url = f"{API_BASE_URL}{path}"
    headers = {}
    auth_token = st.session_state.get("auth_token")
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"
    last_error = None
    for attempt in range(3):
        try:
            response = requests.request(method, url, json=payload, headers=headers, timeout=60)
            break
        except requests.RequestException as exc:
            last_error = exc
            if attempt < 2:
                continue
            return None, f"Network error: {exc}"
    if response.status_code >= 400:
        try:
            return None, response.json().get("detail", "Request failed")
        except ValueError:
            return None, f"Request failed ({response.status_code})"
    if not response.text.strip():
        return {}, None
    return response.json(), None


def parse_tags(raw_tags: str):
    tags = []
    for tag in raw_tags.split(","):
        clean = tag.strip()
        if clean:
            tags.append(clean)
    return tags


def format_content(note: dict, reveal_private: bool) -> str:
    if note.get("is_private") and not reveal_private:
        return "[Hidden private content]"
    return note.get("content", "")


def sort_notes(notes: list[dict], mode: str) -> list[dict]:
    def safe_text(value) -> str:
        return value if isinstance(value, str) else ""

    if mode == "Pinned First":
        return sorted(
            notes,
            key=lambda n: (n.get("pinned", False), safe_text(n.get("updated_at"))),
            reverse=True,
        )
    if mode == "Title A-Z":
        return sorted(notes, key=lambda n: safe_text(n.get("title")).lower())
    return sorted(notes, key=lambda n: safe_text(n.get("updated_at")), reverse=True)


def _format_duration(seconds: int | None) -> str:
    if seconds is None:
        return "-"
    minutes, secs = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def _format_timestamp(value: str | None) -> str:
    if not value:
        return "unknown"
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime("%b %d, %Y %I:%M %p")
    except ValueError:
        return value


def _encode_attachments(files) -> list[dict]:
    attachments = []
    for f in files or []:
        attachments.append(
            {
                "filename": f.name,
                "content_type": f.type or "application/octet-stream",
                "data_b64": base64.b64encode(f.getvalue()).decode("utf-8"),
            }
        )
    return attachments


def render_login_page(auth_error: str | None = None) -> None:
    encoded_next = quote_plus(PUBLIC_STREAMLIT_URL)
    login_google_workspace_url = (
        f"{PUBLIC_API_BASE_URL}/auth/google-workspace/login?next_url={encoded_next}"
    )

    st.title("NoteAPI Studio")
    st.caption("Secure sign-in required before accessing your workspace.")
    if auth_error:
        st.error(f"Login session error: {auth_error}")

    col1, col2, col3 = st.columns([1, 1.8, 1])
    with col2:
        st.markdown("### Login")
        st.write("Login with username/password or create a new account.")

        login_tab, signup_tab = st.tabs(["Login", "Sign Up"])
        with login_tab:
            with st.form("basic_login_form"):
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                login_submit = st.form_submit_button("Login")

            if login_submit:
                payload = {"username": username.strip(), "password": password}
                result, error = auth_request("POST", "/auth/basic/login", payload=payload)
                if error:
                    st.error(error)
                else:
                    st.session_state["auth_token"] = result.get("auth_token")
                    st.session_state["user"] = result.get("user", {})
                    rerun()

        with signup_tab:
            with st.form("basic_signup_form"):
                new_username = st.text_input("New username")
                new_display_name = st.text_input("Display name (optional)")
                new_password = st.text_input("New password", type="password")
                confirm_password = st.text_input("Confirm password", type="password")
                signup_submit = st.form_submit_button("Create Account")

            if signup_submit:
                if new_password != confirm_password:
                    st.error("Passwords do not match")
                else:
                    payload = {
                        "username": new_username.strip(),
                        "password": new_password,
                        "display_name": new_display_name.strip() or None,
                    }
                    _, error = auth_request("POST", "/auth/basic/register", payload=payload)
                    if error:
                        st.error(error)
                    else:
                        st.success("Account created. Please login with your new credentials.")

        st.divider()
        st.write("Or continue with login:")
        st.link_button(
            "Continue with Google Workspace",
            login_google_workspace_url,
            use_container_width=True,
        )
        st.info(
            "You can sign up in this page. `.env` BASIC_AUTH_USERNAME/BASIC_AUTH_PASSWORD still work as fallback."
        )


query_params = st.query_params
if "auth_token" in query_params and query_params["auth_token"]:
    st.session_state["auth_token"] = query_params["auth_token"]
    st.query_params.clear()
    rerun()

if "tgl_sb" in query_params or "tgl_sb_on" in query_params or "tgl_sb_off" in query_params:
    if "tgl_sb" in query_params:
        st.session_state["hide_sidebar"] = not st.session_state.get("hide_sidebar", False)
        # If showing sidebar while in "Clear" view, switch to Dashboard
        if not st.session_state["hide_sidebar"] and st.session_state.get("current_view") == "Clear":
            st.session_state["current_view"] = "Dashboard"
    elif "tgl_sb_on" in query_params:
        st.session_state["hide_sidebar"] = True
    elif "tgl_sb_off" in query_params:
        st.session_state["hide_sidebar"] = False
        if st.session_state.get("current_view") == "Clear":
            st.session_state["current_view"] = "Dashboard"
    st.query_params.clear()
    rerun()


# ---------------------------------------------------------
# GLOBAL UI & THEME (Applied to login & dashboard)
# ---------------------------------------------------------
_ensure_ui_defaults()
theme = st.session_state.get("theme_name", "Dark")
apply_theme(theme)

# Force the search query state
st.session_state.setdefault("search_query", "")

# Premium Sidebar Toggle and Top Bar
st.markdown(
    f"""
    <div id="sb-toggle-btn">
        <span class="sb-icon">☰</span>
        <span class="sb-text">Menu</span>
    </div>
    <style>
    #sb-toggle-btn {{
        position: fixed;
        top: 18px;
        left: 18px;
        z-index: 99999999;
        background: {THEMES[theme]["surface"]};
        color: {THEMES[theme]["ink"]};
        border: 1px solid {THEMES[theme]["border"]};
        border-radius: 40px;
        padding: 0 16px;
        height: 44px;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 10px;
        cursor: pointer;
        font-size: 16px;
        font-weight: 600;
        backdrop-filter: blur(12px);
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.3);
        transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
        user-select: none;
    }}
    #sb-toggle-btn:hover {{
        transform: translateY(-2px);
        border-color: {THEMES[theme]["accent"]};
        box-shadow: 0 6px 20px rgba(0, 0, 0, 0.4);
    }}
    .sb-icon {{ font-size: 18px; }}
    
    /* Hide logic for Zen Mode / Hidden Sidebar */
    {'''
    .top-bar, [data-testid="stSidebar"], [data-testid="stHeader"], section.main > div:first-child {{
        display: none !important;
    }}
    section.main {{
        background: transparent !important;
    }}
    ''' if st.session_state.get("hide_sidebar") else ''}
    </style>
    <script>
        (function() {{
            const btn = document.getElementById('sb-toggle-btn');
            if (btn) {{
                btn.onclick = function() {{
                    const win = window.parent || window;
                    try {{
                        const url = new URL(win.location.href);
                        url.searchParams.set('tgl_sb', Date.now());
                        win.location.search = url.search;
                    }} catch(e) {{
                        const url2 = new URL(window.location.href);
                        url2.searchParams.set('tgl_sb', Date.now());
                        window.location.search = url2.search;
                    }}
                }};
                // Move to body to persist even when container is hidden
                if (btn.parentElement !== document.body) {{
                    const existing = document.body.querySelector('#sb-toggle-btn');
                    if (existing && existing !== btn) existing.remove();
                    document.body.appendChild(btn);
                }}
            }}
        }})();
    </script>
    <div class="top-bar">
        <div class="logo-section" style="padding-left: 90px;">
            <span style="font-size: 24px;">📋</span> NoteApp
        </div>
        <div class="search-container">
            <span style="position: absolute; left: 12px; top: 10px; color: #94a3b8;">🔍</span>
            <input type="text" id="top-search-input" class="search-input" placeholder="Search notes..." value="{st.session_state["search_query"]}">
        </div>
        <div class="nav-icons">
            <span style="font-size: 20px; cursor: pointer;">🔔</span>
            <span style="font-size: 20px; cursor: pointer;">💬</span>
            <img src="https://ui-avatars.com/api/?name={st.session_state.get('user', {}).get('display_name', 'User')}&background=random" class="profile-pic">
        </div>
    </div>
    <script>
        (function() {{
            const input = document.getElementById('top-search-input');
            if (input) {{
                input.addEventListener('keydown', function(e) {{
                    if (e.key === 'Enter') {{
                        const stInput = window.parent.document.querySelector('input[aria-label="hidden_search_input"]');
                        if (stInput) {{
                            stInput.value = this.value;
                            stInput.dispatchEvent(new Event('input', {{ bubbles: true }}));
                            stInput.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        }}
                    }}
                }});
            }}
        }})();
    </script>
    """,
    unsafe_allow_html=True,
)

# Hidden search for state sync
with st.container():
    st.markdown('<div style="display:none">', unsafe_allow_html=True)
    st.text_input("hidden_search_input", key="search_query", label_visibility="collapsed")
    st.markdown('</div>', unsafe_allow_html=True)

# Auth and Initialization
auth_error_message = None
if "auth_token" in st.session_state and "user" not in st.session_state:
    me, me_error = auth_request("GET", "/auth/me")
    if me_error:
        auth_error_message = me_error
        st.session_state.pop("auth_token", None)
    else:
        st.session_state["user"] = me

if "user" not in st.session_state:
    render_login_page(auth_error_message)
    st.stop()

# ---------------------------------------------------------
# LOGGED IN FLOW - LOAD PREFERENCES
# ---------------------------------------------------------
if "prefs_loaded" not in st.session_state:
    prefs_payload, prefs_error = auth_request("GET", "/auth/preferences")
    if prefs_payload and not prefs_error:
        _apply_prefs_to_state(prefs_payload)
    st.session_state["prefs_loaded"] = True

if st.session_state.pop("reset_ui", False):
    _reset_preferences()
    st.session_state["prefs_loaded"] = False
    rerun()
    rerun()
if "bg_mode_next" in st.session_state:
    st.session_state["bg_mode"] = st.session_state.pop("bg_mode_next")

theme_options = list(THEMES.keys())
theme = st.sidebar.selectbox("Theme", theme_options, key="theme_name")
# apply_theme(theme) # Already applied at top level

# Sidebar layout cleaned up - removed Focus/Sleep/Hide toggles
st.sidebar.markdown(f"### Welcome, {st.session_state['user'].get('display_name' or 'username', 'User')}!")
if st.session_state.get("hide_sidebar"):
    st.markdown(
        """
    <style>
        section[data-testid="stSidebar"] {{
            display: none !important;
            width: 0 !important;
        }}
        [data-testid="stSidebarContent"] {{
            display: none !important;
        }}
        section.main {{
            margin-left: 0 !important;
            width: 100% !important;
        }}
        [data-testid="stSidebarCollapseButton"] {{
            display: none !important;
        }}
    </style>
        """,
        unsafe_allow_html=True,
    )

auth_token = st.session_state.get("auth_token", "")
token_param = f"&auth_token={auth_token}" if auth_token else ""
show_sidebar_url = f"?show_sidebar=1{token_param}"
reset_ui_url = f"?reset_ui=1{token_param}"
tasks_json = json.dumps(st.session_state.get("focus_tasks", []))
focus_mode_enabled = str(bool(st.session_state.get("focus_mode"))).lower()
st.markdown(
    f"""
    <script>
        function ensureFocusOverlay(tasks) {{
                let overlay = document.getElementById("focus-overlay");
                if (!overlay) {{
                    overlay = document.createElement("div");
                    overlay.id = "focus-overlay";
                    overlay.style.position = "fixed";
                    overlay.style.inset = "0";
                    overlay.style.display = "flex";
                    overlay.style.alignItems = "center";
                    overlay.style.justifyContent = "center";
                    overlay.style.zIndex = "9998";
                    overlay.style.pointerEvents = "none";
                    overlay.innerHTML = `
                        <div style="background:rgba(15,23,42,0.55);border:1px solid rgba(148,163,184,0.4);border-radius:16px;padding:24px 28px;backdrop-filter:blur(8px);min-width:320px;color:#f8fafc;text-align:center;">
                            <div id="focus-clock" style="font-size:42px;font-weight:700;letter-spacing:1px;">--:--</div>
                            <div id="focus-date" style="margin-top:6px;font-size:14px;color:rgba(226,232,240,0.85);">--</div>
                            <ul id="focus-tasks" style="margin-top:14px;text-align:left;"></ul>
                        </div>
                    `;
                    document.body.appendChild(overlay);
                }}
                const list = overlay.querySelector("#focus-tasks");
                list.innerHTML = "";
                if (!tasks.length) {{
                    const li = document.createElement("li");
                    li.textContent = "No tasks yet";
                    list.appendChild(li);
                }} else {{
                    tasks.forEach(t => {{
                        const li = document.createElement("li");
                        li.textContent = t;
                        li.style.margin = "6px 0";
                        list.appendChild(li);
                    }});
                }}
            }}

            function updateFocusClock() {{
                const now = new Date();
                const hours = String(now.getHours()).padStart(2, "0");
                const minutes = String(now.getMinutes()).padStart(2, "0");
                const clock = document.getElementById("focus-clock");
                const date = document.getElementById("focus-date");
                if (clock) clock.textContent = `${{hours}}:${{minutes}}`;
                if (date) date.textContent = now.toDateString();
            }}

            const focusMode = {focus_mode_enabled};
            if (focusMode) {{
                ensureFocusOverlay({tasks_json});
                updateFocusClock();
                setInterval(updateFocusClock, 1000);
            }} else {{
                const overlay = document.getElementById("focus-overlay");
                if (overlay) overlay.remove();
            }}
        </script>
        """,
        unsafe_allow_html=True,
    )


# Background logic - kept global but controlled via Appearance view
bg_mode = st.session_state.get("bg_mode", "Theme Default")
bg_solid = st.session_state.get("bg_solid", "#f8fafc")
bg_grad_start = st.session_state.get("bg_grad_start", "#f8fafc")
bg_grad_end = st.session_state.get("bg_grad_end", "#e2e8f0")
bg_grad_dir = st.session_state.get("bg_grad_dir", "to bottom right")
bg_image_id = st.session_state.get("bg_image_id")
bg_image_fit = st.session_state.get("bg_image_fit", "Cover")
bg_image_scale = st.session_state.get("bg_image_scale", 100)
bg_image_pos_x = st.session_state.get("bg_image_pos_x", 50)
bg_image_pos_y = st.session_state.get("bg_image_pos_y", 50)

bg_image_b64 = _current_bg_image_b64() if bg_mode == "Image" else None
bg_image_type = _current_bg_content_type() if bg_mode == "Image" else None

apply_background(
    bg_mode,
    bg_solid,
    bg_grad_start,
    bg_grad_end,
    bg_grad_dir,
    bg_image_b64,
    bg_image_type,
    bg_image_fit,
    bg_image_scale,
    bg_image_pos_x,
    bg_image_pos_y,
)

user_role = st.session_state["user"].get("role", "client")
can_edit = st.session_state["user"].get("is_admin", False) or user_role in {"client", "editor", "admin", "viewer"}

st.sidebar.info(f"Role: {st.session_state['user'].get('role', 'user')}")
if st.sidebar.button("Logout", use_container_width=True):
    auth_request("POST", "/auth/logout")
    st.session_state.clear()
    rerun()
    st.stop()

# Main App Start (Cleaned sidebar items)
stats, stats_error = api_request("GET", "stats")
notes, notes_error = api_request("GET")
if notes_error:
    notes = []

if st.sidebar.button("Refresh Data", use_container_width=True):
    rerun()

if notes_error:
    st.error(notes_error)

if "current_view" not in st.session_state:
    st.session_state["current_view"] = "All Notes"

# Custom Sidebar Navigation
st.sidebar.markdown('<div style="padding-bottom: 20px;"></div>', unsafe_allow_html=True)

def sidebar_nav_item(label, icon, key):
    is_active = st.session_state["current_view"] == label
    active_class = "active" if is_active else ""
    if st.sidebar.button(f"{icon} {label}", key=f"nav_{key}", use_container_width=True):
        st.session_state["current_view"] = label
        if label == "Clear":
            st.session_state["hide_sidebar"] = True
        rerun()

sidebar_nav_item("Dashboard", "📊", "dash")
sidebar_nav_item("All Notes", "📑", "all")
sidebar_nav_item("Favorites", "⭐", "fav")
sidebar_nav_item("Archived", "📁", "arch")
sidebar_nav_item("Trash", "🗑️", "trash")
sidebar_nav_item("Appearance", "🎨", "appear")
sidebar_nav_item("Clear", "✨", "clear")

st.sidebar.markdown("---")
# Preserve existing secondary views
if st.session_state["user"].get("is_admin", False):
    sidebar_nav_item("Admin", "🛡️", "admin")
sidebar_nav_item("Requests", "✉️", "req")
if can_edit:
    sidebar_nav_item("Manage", "⚙️", "manage")

# Hidden native toggle for the custom header button
st.sidebar.markdown(
    '<div style="display:none;" id="native-toggle-wrapper">', 
    unsafe_allow_html=True
)
if st.sidebar.button("INTERNAL_TOGGLE", key="sidebar_internal_toggle_btn"):
    # Use query parameter to toggle state at the top of the script
    # This avoids StreamlitAPIException regarding modifying state after widget instantiation
    st.query_params["tgl_sb"] = str(datetime.now().timestamp())
    rerun()
st.sidebar.markdown('</div>', unsafe_allow_html=True)

current_view = st.session_state["current_view"]

# Handle specialized views
if current_view == "Favorites":
    notes = [n for n in notes if n.get("pinned")]
    current_view = "All Notes"
elif current_view == "Archived":
    notes = [n for n in notes if n.get("category") == "Archived"]
    current_view = "All Notes"
elif current_view == "Trash":
    notes = [n for n in notes if n.get("category") == "Trash"]
    current_view = "All Notes"

# Use custom search input
search_text = st.session_state.get("search_query", "").lower()

# View Switcher Main Logic
if current_view == "Clear":
    st.empty() 
elif current_view == "Dashboard":
    st.subheader("Dashboard Overview")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Notes", len(notes))
    m2.metric("Pinned", sum(1 for n in notes if n.get("pinned")))
    m3.metric("Private", sum(1 for n in notes if n.get("is_private")))
    m4.metric("Collections", len(set(n.get("category") for n in notes)))
    
    st.divider()
    st.subheader("Activity")
    # Simple bar chart of notes by category
    cat_counts = {}
    for n in notes:
        c = n.get("category", "General") or "General"
        cat_counts[c] = cat_counts.get(c, 0) + 1
    if cat_counts:
        st.bar_chart(cat_counts)
        st.dataframe(pd.DataFrame(list(cat_counts.items()), columns=["Category", "Count"]), hide_index=True)
    else:
        st.info("No categorical data to display.")

elif current_view == "Appearance":
    st.subheader("Appearance & Visual Settings")
    st.write("Customize your workspace look and feel.")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### Theme Selection")
        theme_options = list(THEMES.keys())
        theme_idx = theme_options.index(st.session_state.get("theme_name", "Dark"))
        new_theme = st.selectbox("Active Theme", theme_options, index=theme_idx)
        if new_theme != st.session_state.get("theme_name"):
            st.session_state["theme_name"] = new_theme
            rerun()
        
        st.markdown("### Background Mode")
        bg_options = ["Theme Default", "Solid", "Gradient", "Image"]
        new_bg_mode = st.selectbox("Background Style", bg_options, index=bg_options.index(st.session_state.get("bg_mode", "Theme Default")))
        if new_bg_mode != st.session_state.get("bg_mode"):
            st.session_state["bg_mode"] = new_bg_mode
            rerun()

    with col2:
        if st.session_state.get("bg_mode") == "Solid":
            st.color_picker("Pick a color", key="bg_solid")
        elif st.session_state.get("bg_mode") == "Gradient":
            st.color_picker("Start color", key="bg_grad_start")
            st.color_picker("End color", key="bg_grad_end")
            st.selectbox("Direction", ["to bottom right", "to bottom", "to right", "135deg"], key="bg_grad_dir")
        elif st.session_state.get("bg_mode") == "Image":
            st.markdown("### Image Gallery")
            uploads = st.file_uploader("Upload new backgrounds", type=["png", "jpg", "jpeg"], accept_multiple_files=True)
            if st.button("Update Gallery", use_container_width=True):
                gallery = list(st.session_state.get("bg_gallery", []))
                MAX_SIZE = 1.5 * 1024 * 1024
                for up in uploads or []:
                    if up.size > MAX_SIZE:
                        st.error(f"File {up.name} is too large (>{up.size/1024/1024:.2f}MB). Limit is 1.5MB.")
                        continue
                    raw = up.read()
                    b64 = base64.b64encode(raw).decode("ascii")
                    gallery.append({"id": uuid.uuid4().hex[:8], "name": up.name, "data_b64": b64, "content_type": up.type})
                st.session_state["bg_gallery"] = gallery[:8]
                rerun()
            
            items = st.session_state.get("bg_gallery", [])
            if items:
                img_ids = [i["id"] for i in items]
                sel_id = st.radio("Select Image", img_ids, format_func=lambda x: next(i["name"] for i in items if i["id"] == x))
                st.session_state["bg_image_id"] = sel_id
                
                st.markdown("### Image Controls")
                st.selectbox("Fit", ["Cover", "Contain", "Actual"], key="bg_image_fit")
                st.slider("Scale (%)", 50, 200, key="bg_image_scale")
                st.slider("X Position (%)", 0, 100, key="bg_image_pos_x")
                st.slider("Y Position (%)", 0, 100, key="bg_image_pos_y")

    st.divider()
    if st.button("Save Appearance Globally", type="primary", use_container_width=True):
        payload = {
            "theme": st.session_state.get("theme_name"),
            "background_mode": st.session_state.get("bg_mode"),
            "background_solid": st.session_state.get("bg_solid"),
            "background_gradient_start": st.session_state.get("bg_grad_start"),
            "background_gradient_end": st.session_state.get("bg_grad_end"),
            "background_gradient_dir": st.session_state.get("bg_grad_dir"),
            "background_image_id": st.session_state.get("bg_image_id"),
            "background_image_fit": st.session_state.get("bg_image_fit"),
            "background_image_scale": st.session_state.get("bg_image_scale"),
            "background_image_pos_x": st.session_state.get("bg_image_pos_x"),
            "background_image_pos_y": st.session_state.get("bg_image_pos_y"),
            "backgrounds": st.session_state.get("bg_gallery", []),
        }
        _, err = auth_request("PUT", "/auth/preferences", payload=payload)
        if err: st.error(err)
        else: st.success("Settings saved to your profile!")

elif current_view == "All Notes":
    # Three-Column Layout for Note List and Editor
    note_list_col, editor_col = st.columns([1, 1.5], gap="large")
    
    with note_list_col:
        st.subheader("All Notes")
        
        # Filtering notes based on search text
        filtered_notes = [
            n for n in notes 
            if search_text in n.get("title", "").lower() or search_text in n.get("content", "").lower()
        ]
        
        if not filtered_notes:
            st.info("No matching notes found.")
        else:
            for note in filtered_notes:
                is_selected = st.session_state.get("selected_note_id") == note.get("id")
                active_card = "active" if is_selected else ""
                
                st.markdown(
                    f"""
                    <div class="note-card {active_card}">
                        <div class="note-title">{note.get('title', 'Untitled')}</div>
                        <div class="note-meta">
                            <span class="tag">{note.get('category', 'General')}</span>
                            <span>{_format_timestamp(note.get('created_at'))}</span>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                if st.button("Open", key=f"open_{note.get('id')}", use_container_width=True):
                    st.session_state["selected_note_id"] = note.get("id")
                    st.session_state["show_create_form"] = False
                    rerun()

    with editor_col:
        selected_id = st.session_state.get("selected_note_id")
        show_create = st.session_state.get("show_create_form", False)
        
        if show_create:
            st.subheader("Create a New Note")
            with st.form("new_note_form_modern"):
                title = st.text_input("Title")
                content = st.text_area("Write your notes here...", height=300)
                category = st.text_input("Category (e.g. work, personal)")
                is_private = st.checkbox("Private note")
                
                cols = st.columns([1, 1])
                with cols[0]:
                    save = st.form_submit_button("Save Note", use_container_width=True)
                
                if save:
                    # Logic to save note
                    payload = {
                        "id": str(uuid.uuid4())[:8],
                        "title": title.strip() or "Untitled",
                        "content": content,
                        "category": category.strip() or "General",
                        "is_private": is_private,
                        "author": st.session_state["user"].get("username")
                    }
                    _, err = auth_request("POST", "/notes", payload=payload)
                    if err: st.error(err)
                    else:
                        st.success("Note created!")
                        st.session_state["show_create_form"] = False
                        rerun()
        
        elif selected_id:
            note = next((n for n in notes if n.get("id") == selected_id), None)
            if note:
                st.subheader(note.get("title", "Editing Note"))
                with st.form("edit_note_form_modern"):
                    title = st.text_input("Title", value=note.get("title", ""))
                    content = st.text_area("Content", value=note.get("content", ""), height=400)
                    
                    cols = st.columns([1, 1])
                    with cols[0]:
                        save = st.form_submit_button("Update", use_container_width=True)
                    with cols[1]:
                        delete = st.form_submit_button("Delete", use_container_width=True)
                    
                    if save:
                        # Logic to update
                        payload = note.copy()
                        payload["title"] = title
                        payload["content"] = content
                        _, err = auth_request("PUT", f"/notes/{selected_id}", payload=payload)
                        if err: st.error(err)
                        else: rerun()
                    
                    if delete:
                        _, err = auth_request("DELETE", f"/notes/{selected_id}")
                        if err: st.error(err)
                        else:
                            st.session_state["selected_note_id"] = None
                            rerun()
            else:
                st.info("Select a note to view/edit.")
        else:
            st.info("Select a note from the list or click '+ New Note' to begin.")



elif current_view == "Manage":
    st.subheader("Update Existing Note")
    ids = [note.get("id", "") for note in notes]
    if not ids:
        st.info("No notes available. Create one first.")
    else:
        selected_id = st.selectbox("Select Note ID", ids, key="manage_select_id")
        selected = next((note for note in notes if note.get("id") == selected_id), None)
        if selected:
            with st.form("update_note_form"):
                u_title = st.text_input("Title", value=selected.get("title", ""))
                u_content = st.text_area("Content", value=selected.get("content", ""), height=180)
                col1, col2 = st.columns(2)
                u_category = col1.text_input("Category", value=selected.get("category", "General"))
                u_tags = col2.text_input("Tags (comma separated)", value=", ".join(selected.get("tags", [])))
                keep_attachments = st.checkbox("Keep existing attachments", value=True)
                new_attachments = st.file_uploader(
                    "Add attachments",
                    accept_multiple_files=True,
                    key="update_attachments",
                )
                col3, col4 = st.columns(2)
                u_pinned = col3.checkbox("Pinned", value=selected.get("pinned", False))
                u_private = col4.checkbox("Private", value=selected.get("is_private", False))
                submitted = st.form_submit_button("Update Note")

            if submitted:
                attachments_payload = []
                if keep_attachments:
                    attachments_payload.extend(selected.get("attachments", []))
                attachments_payload.extend(_encode_attachments(new_attachments))
                payload = {
                    "id": selected_id,
                    "title": u_title.strip(),
                    "content": u_content.strip(),
                    "pinned": u_pinned,
                    "is_private": u_private,
                    "category": u_category.strip() or "General",
                    "tags": parse_tags(u_tags),
                    "attachments": attachments_payload,
                }
                result, err = api_request("PUT", selected_id, payload=payload)
                if err:
                    st.error(err)
                else:
                    st.success(result.get("message", "Note updated"))
                    rerun()

elif current_view == "Requests":
    st.subheader("Request Changes")
    action = st.selectbox("Action", ["Create", "Update", "Delete", "Pin/Unpin"])
    reason = st.text_input("Reason for change")

    if action == "Create":
        with st.form("request_create_note"):
            col1, col2 = st.columns(2)
            note_id = col1.text_input("Note ID")
            title = col2.text_input("Title")
            col3, col4 = st.columns(2)
            category = col3.text_input("Category", value="General")
            tags_raw = col4.text_input("Tags (comma separated)")
            content = st.text_area("Content", height=180)
            attachments = st.file_uploader(
                "Attach images/files",
                accept_multiple_files=True,
                key="request_create_attachments",
            )
            c1, c2 = st.columns(2)
            pinned = c1.checkbox("Pin this note")
            is_private = c2.checkbox("Mark as private")
            submit_request = st.form_submit_button("Submit Create Request")
        if submit_request:
            payload = {
                "action": "create",
                "reason": reason,
                "note_id": note_id,
                "payload": {
                    "id": note_id,
                    "title": title,
                    "content": content,
                    "category": category,
                    "tags": parse_tags(tags_raw),
                    "pinned": pinned,
                    "is_private": is_private,
                    "attachments": _encode_attachments(attachments)
                }
            }
            _, err = auth_request("POST", "/notes/requests", payload=payload)
            if err: st.error(err)
            else:
                st.success("Request submitted")
                rerun()

    if action in {"Update", "Delete", "Pin/Unpin"}:
        if not notes:
            st.info("No notes available.")
        else:
            note_ids = [note.get("id", "") for note in notes]
            selected_id = st.selectbox("Select Note ID", note_ids, key=f"request_{action}_id")
            selected = next((note for note in notes if note.get("id") == selected_id), None)

            if action == "Update" and selected:
                with st.form("request_update_note"):
                    u_title = st.text_input("Title", value=selected.get("title", ""))
                    u_content = st.text_area("Content", value=selected.get("content", ""), height=180)
                    col1, col2 = st.columns(2)
                    u_category = col1.text_input("Category", value=selected.get("category", "General"))
                    u_tags = col2.text_input(
                        "Tags (comma separated)",
                        value=", ".join(selected.get("tags", [])),
                    )
                    keep_attachments = st.checkbox("Keep existing attachments", value=True)
                    new_attachments = st.file_uploader(
                        "Add attachments",
                        accept_multiple_files=True,
                        key="request_update_attachments",
                    )
                    col3, col4 = st.columns(2)
                    u_pinned = col3.checkbox("Pinned", value=selected.get("pinned", False))
                    u_private = col4.checkbox("Private", value=selected.get("is_private", False))
                    submit_update = st.form_submit_button("Submit Update Request")
                if submit_update:
                    attachments_payload = []
                    if keep_attachments:
                        attachments_payload.extend(selected.get("attachments", []))
                    attachments_payload.extend(_encode_attachments(new_attachments))
                    payload = {
                        "id": selected_id,
                        "title": u_title.strip(),
                        "content": u_content.strip(),
                        "pinned": u_pinned,
                        "is_private": u_private,
                        "category": u_category.strip() or "General",
                        "tags": parse_tags(u_tags),
                        "attachments": attachments_payload,
                    }
                    result, err = auth_request(
                        "POST",
                        "/notes/requests",
                        payload={
                            "action": "update",
                            "note_id": selected_id,
                            "payload": payload,
                            "reason": reason.strip() or None,
                        },
                    )
                    if err:
                        st.error(err)
                    else:
                        st.success(result.get("message", "Request submitted"))
                        rerun()

            if action == "Delete" and selected:
                if st.button("Submit Delete Request"):
                    result, err = auth_request(
                        "POST",
                        "/notes/requests",
                        payload={
                            "action": "delete",
                            "note_id": selected_id,
                            "reason": reason.strip() or None,
                        },
                    )
                    if err:
                        st.error(err)
                    else:
                        st.success(result.get("message", "Request submitted"))
                        rerun()

            if action == "Pin/Unpin" and selected:
                toggle_pin = not selected.get("pinned", False)
                if st.button("Submit Pin/Unpin Request"):
                    result, err = auth_request(
                        "POST",
                        "/notes/requests",
                        payload={
                            "action": "pin",
                            "note_id": selected_id,
                            "payload": {"pinned": toggle_pin},
                            "reason": reason.strip() or None,
                        },
                    )
                    if err:
                        st.error(err)
                    else:
                        st.success(result.get("message", "Request submitted"))
                        rerun()

elif current_view == "Admin":
    st.subheader("Admin Control Center")
    admin_tabs = st.tabs(["Users", "Requests", "System"])
    
    with admin_tabs[0]:
        st.subheader("User Directory")
        users_payload, users_error = auth_request("GET", "/auth/admin/users")
        if users_error: st.error(users_error)
        else:
            users = users_payload.get("users", [])
            st.dataframe(users, use_container_width=True)
            
            with st.form("admin_user_form"):
                u = st.selectbox("Target User", [usr.get("username") for usr in users])
                role = st.selectbox("New Role", ["", "client", "editor", "admin"])
                submit = st.form_submit_button("Apply Changes")
                if submit and role:
                    _, err = auth_request("PATCH", f"/auth/admin/users/{u}", payload={"role": role})
                    if err: st.error(err)
                    else: st.success("User updated!"); rerun()

    with admin_tabs[1]:
        st.subheader("Pending Requests")
        req_payload, req_err = auth_request("GET", "/notes/requests?status=pending")
        if req_err: st.error(req_err)
        else:
            preqs = req_payload.get("requests", [])
            if not preqs: st.info("No pending requests.")
            else:
                st.dataframe(preqs, use_container_width=True)

    with admin_tabs[2]:
        st.subheader("System Information")
        st.write("Streamlit Version:", st.__version__)
        if st.button("Download System Logs"):
            st.info("Log download started...")

# Final Footer
st.markdown(
    """
    <div style="text-align: center; padding: 60px 20px; color: #94a3b8; font-size: 0.9rem; border-top: 1px solid #e2e8f0; margin-top: 80px;">
        <div style="margin-bottom: 10px;">Powered by FastAPI & Streamlit</div>
        <div style="font-size: 0.8rem; opacity: 0.7;">© 2026 NoteAPI Studio • Clean. Secure. Fast.</div>
    </div>
    """,
    unsafe_allow_html=True
)

