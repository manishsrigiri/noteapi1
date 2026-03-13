import base64
import json
import os
from datetime import datetime
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

auth_error_message = None
if "auth_token" in st.session_state and "user" not in st.session_state:
    me, me_error = auth_request("GET", "/auth/me")
    if me_error:
        auth_error_message = me_error
        st.session_state.pop("auth_token", None)
    else:
        st.session_state["user"] = me

theme = st.sidebar.selectbox("Theme", list(THEMES.keys()), index=1)
apply_theme(theme)
st.sidebar.title("Control Room")

if "user" not in st.session_state:
    render_login_page(auth_error_message)
    st.stop()

user_role = st.session_state["user"].get("role", "viewer")
can_edit = st.session_state["user"].get("is_admin", False) or user_role in {"editor", "admin"}

st.sidebar.success(f"Signed in as {st.session_state['user'].get('username', 'user')}")
if st.sidebar.button("Logout"):
    auth_request("POST", "/auth/logout")
    st.session_state.pop("auth_token", None)
    st.session_state.pop("user", None)
    st.warning("You have been logged out.")
    st.stop()

if st.session_state["user"].get("is_admin", False):
    session_stats, session_stats_error = auth_request("GET", "/auth/session-stats")
    if session_stats and not session_stats_error:
        st.sidebar.metric("Logged-in Users", session_stats.get("logged_in_users", 0))
        st.sidebar.metric("Active Sessions", session_stats.get("active_sessions", 0))

    with st.sidebar.expander("Session Details", expanded=False):
        sessions_payload, sessions_error = auth_request("GET", "/auth/sessions?include_inactive=true")
        if sessions_error:
            st.error(sessions_error)
        else:
            sessions = sessions_payload.get("sessions", [])
            for session in sessions:
                session["duration"] = _format_duration(session.get("duration_seconds"))
            search_user = st.text_input("Search user activity")
            if search_user.strip():
                needle = search_user.strip().lower()
                sessions = [s for s in sessions if needle in s.get("username", "").lower()]
            session_rows = [
                {
                    "logout": False,
                    "token": s.get("token", ""),
                    "username": s.get("username", ""),
                    "active": s.get("is_active", False),
                    "login_at": s.get("created_at", ""),
                    "last_seen": s.get("last_seen", ""),
                    "logout_at": s.get("logged_out_at", ""),
                    "duration": s.get("duration", ""),
                }
                for s in sessions
            ]
            edited = st.data_editor(
                session_rows,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "logout": st.column_config.CheckboxColumn("Logout"),
                    "token": st.column_config.TextColumn("Token"),
                },
                disabled=[
                    "token",
                    "username",
                    "active",
                    "login_at",
                    "last_seen",
                    "logout_at",
                    "duration",
                ],
            )

            logout_tokens = [row["token"] for row in edited if row.get("logout") and row.get("token")]
            if st.button("Logout Selected"):
                if not logout_tokens:
                    st.info("Select at least one session to logout.")
                else:
                    total_updated = 0
                    for token in logout_tokens:
                        result, error = auth_request(
                            "POST",
                            "/auth/sessions/logout",
                            payload={"token": token},
                        )
                        if error:
                            st.error(f"{token}: {error}")
                        else:
                            total_updated += result.get("updated", 0)
                    st.success(f"Logged out sessions: {total_updated}")
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
role_label = "Admin" if st.session_state["user"].get("is_admin", False) else user_role.title()
st.caption(f"Role: {role_label}")
st.caption("Presentation-ready notes dashboard with privacy controls, pinning, and analytics.")

if notes_error:
    st.error(notes_error)

tab_labels = ["Dashboard"]
if can_edit:
    tab_labels.append("Create")
tab_labels.append("Library")
tab_labels.append("Requests")
if can_edit:
    tab_labels.append("Manage")
if st.session_state["user"].get("is_admin", False):
    tab_labels.append("Admin")
tabs = st.tabs(tab_labels)
tab_map = dict(zip(tab_labels, tabs))

with tab_map["Dashboard"]:
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

if "Create" in tab_map:
    with tab_map["Create"]:
        st.subheader("Create a New Note")
        with st.form("create_note_form"):
            col1, col2 = st.columns(2)
            note_id = col1.text_input("Note ID")
            title = col2.text_input("Title")
            col3, col4 = st.columns(2)
            category = col3.text_input("Category", value="General")
            tags_raw = col4.text_input("Tags (comma separated)")
            content = st.text_area("Content", height=180)
            attachments = st.file_uploader("Attachments", accept_multiple_files=True)
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
                "attachments": _encode_attachments(attachments),
            }
            result, err = api_request("POST", "", payload=payload)
            if err:
                st.error(err)
            else:
                st.success(result.get("message", "Note created"))
                rerun()

with tab_map["Library"]:
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
        created_at = _format_timestamp(note.get("created_at"))
        st.markdown(
            f"""
            <div class="note-card">
                <h4>{note.get("title", "")}</h4>
                <p class="meta-text">ID: {note.get("id", "")} | {pin_label} | {visibility_label}</p>
                <p class="meta-text">Category: {note.get("category", "General")} | Tags: {tags}</p>
                <p class="meta-text">Created: {created_at}</p>
                <p>{content_preview}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        attachments = note.get("attachments", [])
        if attachments:
            with st.expander("Attachments"):
                for attachment in attachments:
                    filename = attachment.get("filename", "attachment")
                    content_type = attachment.get("content_type", "application/octet-stream")
                    data_b64 = attachment.get("data_b64", "")
                    try:
                        data = base64.b64decode(data_b64)
                    except (ValueError, TypeError):
                        data = b""
                    if content_type.startswith("image/") and data:
                        st.image(data, caption=filename)
                    st.download_button(
                        label=f"Download {filename}",
                        data=data,
                        file_name=filename,
                        mime=content_type,
                    )
        b1, b2 = st.columns(2)
        toggle_pin = not note.get("pinned", False)
        pin_text = "Pin" if toggle_pin else "Unpin"
        if b1.button(
            f"{pin_text} {note.get('id')}",
            key=f"pin_{note.get('id')}",
            disabled=not can_edit,
        ):
            _, err = api_request("PUT", f"{note.get('id')}/pin", payload={"pinned": toggle_pin})
            if err:
                st.error(err)
            else:
                rerun()
        if b2.button(
            f"Delete {note.get('id')}",
            key=f"delete_{note.get('id')}",
            disabled=not can_edit,
        ):
            _, err = api_request("DELETE", note.get("id"))
            if err:
                st.error(err)
            else:
                st.success("Note deleted")
                rerun()

if "Manage" in tab_map:
    with tab_map["Manage"]:
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

with tab_map["Requests"]:
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
                "id": note_id.strip(),
                "title": title.strip(),
                "content": content.strip(),
                "pinned": pinned,
                "is_private": is_private,
                "category": category.strip() or "General",
                "tags": parse_tags(tags_raw),
                "attachments": _encode_attachments(attachments),
            }
            result, err = auth_request(
                "POST",
                "/notes/requests",
                payload={"action": "create", "payload": payload, "reason": reason.strip() or None},
            )
            if err:
                st.error(err)
            else:
                st.success(result.get("message", "Request submitted"))
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

if "Admin" in tab_map:
    with tab_map["Admin"]:
        st.subheader("All Notes (Admin)")
        if notes_error:
            st.error(notes_error)
        else:
            st.download_button(
                label="Export Notes (JSON)",
                data=json.dumps(notes, indent=2),
                file_name="notes_admin_export.json",
                mime="application/json",
            )
            st.dataframe(notes, use_container_width=True)

        st.subheader("User Directory")
        users_payload, users_error = auth_request("GET", "/auth/admin/users")
        if users_error:
            st.error(users_error)
        else:
            users = users_payload.get("users", [])
            st.download_button(
                label="Export Users (JSON)",
                data=json.dumps(users, indent=2),
                file_name="users_admin_export.json",
                mime="application/json",
            )
            st.dataframe(users, use_container_width=True)

            with st.form("admin_update_user"):
                target_username = st.selectbox("User", [u.get("username", "") for u in users])
                new_display_name = st.text_input("New display name")
                new_role = st.selectbox("New role", ["", "viewer", "editor", "admin"])
                update_submit = st.form_submit_button("Update User")
            if update_submit:
                payload = {}
                if new_display_name.strip():
                    payload["display_name"] = new_display_name.strip()
                if new_role:
                    payload["role"] = new_role
                result, error = auth_request(
                    "PATCH",
                    f"/auth/admin/users/{target_username}",
                    payload=payload,
                )
                if error:
                    st.error(error)
                else:
                    st.success(result.get("message", "User updated"))
                    rerun()

            st.markdown("### Admin Actions")
            with st.form("admin_reset_password"):
                reset_username = st.selectbox("Reset password for", [u.get("username", "") for u in users])
                reset_password = st.text_input("New password", type="password")
                reset_submit = st.form_submit_button("Reset Password")
            if reset_submit:
                result, error = auth_request(
                    "POST",
                    f"/auth/admin/users/{reset_username}/reset-password",
                    payload={"password": reset_password},
                )
                if error:
                    st.error(error)
                else:
                    st.success(result.get("message", "Password reset"))
                    rerun()

            with st.form("admin_delete_user"):
                delete_username = st.selectbox("Delete user", [u.get("username", "") for u in users])
                delete_submit = st.form_submit_button("Delete User")
            if delete_submit:
                result, error = auth_request(
                    "DELETE",
                    f"/auth/admin/users/{delete_username}",
                )
                if error:
                    st.error(error)
                else:
                    st.success(result.get("message", "User deleted"))
                    rerun()

        with st.form("admin_create_user_main"):
            st.subheader("Create User")
            new_username = st.text_input("Username")
            new_display_name = st.text_input("Display name")
            new_password = st.text_input("Password", type="password")
            new_role = st.selectbox("Role", ["viewer", "editor", "admin"])
            create_submit = st.form_submit_button("Create User")
        if create_submit:
            payload = {
                "username": new_username.strip(),
                "password": new_password,
                "display_name": new_display_name.strip() or None,
                "role": new_role,
            }
            result, error = auth_request("POST", "/auth/admin/users", payload=payload)
            if error:
                st.error(error)
            else:
                st.success(result.get("message", "User created"))
                rerun()

        st.subheader("Change Requests")
        requests_payload, requests_error = auth_request("GET", "/notes/requests?status=pending")
        if requests_error:
            st.error(requests_error)
        else:
            pending_requests = requests_payload.get("requests", [])
            st.dataframe(pending_requests, use_container_width=True)

            request_ids = [r.get("_id", "") for r in pending_requests if r.get("_id")]
            if request_ids:
                with st.form("admin_resolve_request"):
                    selected_request = st.selectbox("Request ID", request_ids)
                    decline_reason = st.text_input("Decline reason (optional)")
                    approve = st.form_submit_button("Approve")
                    decline = st.form_submit_button("Decline")
                if approve:
                    result, error = auth_request(
                        "POST",
                        f"/notes/requests/{selected_request}/approve",
                    )
                    if error:
                        st.error(error)
                    else:
                        st.success(result.get("message", "Request approved"))
                        rerun()
                if decline:
                    result, error = auth_request(
                        "POST",
                        f"/notes/requests/{selected_request}/decline",
                        payload={"reason": decline_reason.strip() or None},
                    )
                    if error:
                        st.error(error)
                    else:
                        st.success(result.get("message", "Request declined"))
                        rerun()
            else:
                st.info("No pending requests.")
