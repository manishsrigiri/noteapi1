import json
import os
from urllib.parse import quote_plus

import requests
import streamlit as st

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
}

st.set_page_config(page_title="NoteAPI Studio", layout="wide", initial_sidebar_state="expanded")


def rerun() -> None:
    if hasattr(st, "rerun"):
        st.rerun()
    else:
        st.experimental_rerun()


def apply_theme(theme_name: str) -> None:
    t = THEMES[theme_name]
    st.markdown(
        f"""
        <style>
            .stApp {{
                background: radial-gradient(circle at top right, {t["accent_soft"]}, {t["bg"]} 40%);
                color: {t["ink"]};
            }}
            section[data-testid="stSidebar"] {{
                background: linear-gradient(180deg, {t["surface"]} 0%, {t["accent_soft"]} 100%);
                border-right: 1px solid {t["border"]};
            }}
            h1, h2, h3 {{ color: {t["ink"]}; }}
            .stMetric {{
                background-color: {t["surface"]};
                border: 1px solid {t["border"]};
                border-radius: 12px;
                padding: 8px;
            }}
            .note-card {{
                background: {t["surface"]};
                border: 1px solid {t["border"]};
                border-radius: 12px;
                padding: 14px;
                margin-bottom: 12px;
            }}
            .meta-text {{ color: {t["muted"]}; font-size: 0.90rem; }}
            div.stButton > button {{
                border-radius: 9px;
                border: 1px solid {t["border"]};
            }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def api_request(method: str, path: str = "", payload=None):
    url = API_URL if not path else f"{API_URL}/{path.lstrip('/')}"
    headers = {}
    auth_token = st.session_state.get("auth_token")
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"
    try:
        response = requests.request(method, url, json=payload, headers=headers, timeout=8)
    except requests.RequestException as exc:
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
    try:
        response = requests.request(method, url, json=payload, headers=headers, timeout=8)
    except requests.RequestException as exc:
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


query_params = st.query_params
if "auth_token" in query_params and query_params["auth_token"]:
    st.session_state["auth_token"] = query_params["auth_token"]
    st.query_params.clear()
    rerun()

if "auth_token" in st.session_state and "user" not in st.session_state:
    me, me_error = auth_request("GET", "/auth/me")
    if me_error:
        st.session_state.pop("auth_token", None)
    else:
        st.session_state["user"] = me

theme = st.sidebar.selectbox("Theme", list(THEMES.keys()))
apply_theme(theme)
st.sidebar.title("Control Room")

if "user" not in st.session_state:
    st.title("NoteAPI Studio")
    st.subheader("Sign in required")
    st.write("Use OAuth to access your notes securely.")
    encoded_next = quote_plus(PUBLIC_STREAMLIT_URL)
    login_github_url = f"{PUBLIC_API_BASE_URL}/auth/github/login?next_url={encoded_next}"
    login_google_url = f"{PUBLIC_API_BASE_URL}/auth/google/login?next_url={encoded_next}"
    st.link_button("Login with GitHub", login_github_url, use_container_width=True)
    st.link_button("Login with Google", login_google_url, use_container_width=True)
    st.stop()

st.sidebar.success(f"Signed in as {st.session_state['user'].get('username', 'user')}")
if st.sidebar.button("Logout"):
    auth_request("POST", "/auth/logout")
    st.session_state.pop("auth_token", None)
    st.session_state.pop("user", None)
    rerun()

stats, stats_error = api_request("GET", "stats")
notes, notes_error = api_request("GET")
if notes_error:
    notes = []

if st.sidebar.button("Refresh Data"):
    rerun()

if stats and not stats_error:
    st.sidebar.metric("Total IDs", stats.get("total_ids", 0))
    st.sidebar.metric("Pinned IDs", stats.get("pinned_ids", 0))
    st.sidebar.metric("Private IDs", stats.get("private_ids", 0))
    st.sidebar.metric("Public IDs", stats.get("public_ids", 0))
else:
    st.sidebar.warning(stats_error or "Could not load stats")

st.title("NoteAPI Studio")
st.caption("Presentation-ready notes dashboard with privacy controls, pinning, and analytics.")

if notes_error:
    st.error(notes_error)

tabs = st.tabs(["Dashboard", "Create", "Library", "Manage"])

with tabs[0]:
    st.subheader("Live Overview")
    total = len(notes)
    pinned = sum(1 for note in notes if note.get("pinned"))
    private = sum(1 for note in notes if note.get("is_private"))
    public = total - private
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Notes", total)
    col2.metric("Pinned", pinned)
    col3.metric("Private", private)
    col4.metric("Public", public)

    category_data = {}
    for note in notes:
        category = note.get("category", "General") or "General"
        category_data[category] = category_data.get(category, 0) + 1
    if category_data:
        st.subheader("Category Distribution")
        st.bar_chart(category_data)

    st.subheader("Export Snapshot")
    st.download_button(
        label="Download Notes JSON",
        data=json.dumps(notes, indent=2),
        file_name="notes_snapshot.json",
        mime="application/json",
    )

with tabs[1]:
    st.subheader("Create a New Note")
    with st.form("create_note_form"):
        col1, col2 = st.columns(2)
        note_id = col1.text_input("Note ID")
        title = col2.text_input("Title")
        col3, col4 = st.columns(2)
        category = col3.text_input("Category", value="General")
        tags_raw = col4.text_input("Tags (comma separated)")
        content = st.text_area("Content", height=180)
        c1, c2 = st.columns(2)
        pinned = c1.checkbox("Pin this note")
        is_private = c2.checkbox("Mark as private")
        submitted = st.form_submit_button("Create Note")

    if submitted:
        payload = {
            "id": note_id.strip(),
            "title": title.strip(),
            "content": content.strip(),
            "pinned": pinned,
            "is_private": is_private,
            "category": category.strip() or "General",
            "tags": parse_tags(tags_raw),
        }
        result, err = api_request("POST", "", payload=payload)
        if err:
            st.error(err)
        else:
            st.success(result.get("message", "Note created"))
            rerun()

with tabs[2]:
    st.subheader("Notes Library")
    c1, c2, c3, c4 = st.columns(4)
    search_text = c1.text_input("Search")
    visibility = c2.selectbox("Visibility", ["All", "Public", "Private"])
    categories = sorted({(n.get("category", "General") or "General") for n in notes})
    category_filter = c3.selectbox("Category", ["All"] + categories)
    sort_mode = c4.selectbox("Sort", ["Pinned First", "Recently Updated", "Title A-Z"])
    show_private_content = st.checkbox("Reveal private content", value=False)

    filtered = []
    search_text = search_text.strip().lower()
    for note in notes:
        if visibility == "Public" and note.get("is_private"):
            continue
        if visibility == "Private" and not note.get("is_private"):
            continue
        note_category = note.get("category", "General") or "General"
        if category_filter != "All" and note_category != category_filter:
            continue
        if search_text:
            haystack = (
                f"{note.get('id', '')} {note.get('title', '')} "
                f"{note.get('content', '')} {note_category} {' '.join(note.get('tags', []))}"
            ).lower()
            if search_text not in haystack:
                continue
        filtered.append(note)

    filtered = sort_notes(filtered, sort_mode)
    st.caption(f"Showing {len(filtered)} of {len(notes)} notes")

    for note in filtered:
        visibility_label = "PRIVATE" if note.get("is_private") else "PUBLIC"
        pin_label = "PINNED" if note.get("pinned") else "UNPINNED"
        tags = ", ".join(note.get("tags", [])) or "None"
        content_preview = format_content(note, reveal_private=show_private_content)
        st.markdown(
            f"""
            <div class="note-card">
                <h4>{note.get("title", "")}</h4>
                <p class="meta-text">ID: {note.get("id", "")} | {pin_label} | {visibility_label}</p>
                <p class="meta-text">Category: {note.get("category", "General")} | Tags: {tags}</p>
                <p>{content_preview}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        b1, b2 = st.columns(2)
        toggle_pin = not note.get("pinned", False)
        pin_text = "Pin" if toggle_pin else "Unpin"
        if b1.button(f"{pin_text} {note.get('id')}", key=f"pin_{note.get('id')}"):
            _, err = api_request("PUT", f"{note.get('id')}/pin", payload={"pinned": toggle_pin})
            if err:
                st.error(err)
            else:
                rerun()
        if b2.button(f"Delete {note.get('id')}", key=f"delete_{note.get('id')}"):
            _, err = api_request("DELETE", note.get("id"))
            if err:
                st.error(err)
            else:
                st.success("Note deleted")
                rerun()

with tabs[3]:
    st.subheader("Update Existing Note")
    ids = [note.get("id", "") for note in notes]
    if not ids:
        st.info("No notes available. Create one first.")
    else:
        selected_id = st.selectbox("Select Note ID", ids)
        selected = next((note for note in notes if note.get("id") == selected_id), None)
        if selected:
            with st.form("update_note_form"):
                u_title = st.text_input("Title", value=selected.get("title", ""))
                u_content = st.text_area("Content", value=selected.get("content", ""), height=180)
                col1, col2 = st.columns(2)
                u_category = col1.text_input("Category", value=selected.get("category", "General"))
                u_tags = col2.text_input("Tags (comma separated)", value=", ".join(selected.get("tags", [])))
                col3, col4 = st.columns(2)
                u_pinned = col3.checkbox("Pinned", value=selected.get("pinned", False))
                u_private = col4.checkbox("Private", value=selected.get("is_private", False))
                submitted = st.form_submit_button("Update Note")

            if submitted:
                payload = {
                    "id": selected_id,
                    "title": u_title.strip(),
                    "content": u_content.strip(),
                    "pinned": u_pinned,
                    "is_private": u_private,
                    "category": u_category.strip() or "General",
                    "tags": parse_tags(u_tags),
                }
                result, err = api_request("PUT", selected_id, payload=payload)
                if err:
                    st.error(err)
                else:
                    st.success(result.get("message", "Note updated"))
                    rerun()
