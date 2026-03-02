import requests
import streamlit as st

API_URL = "http://fastapi:8000/notes"  # Use "http://localhost:8000/notes" if running locally


def apply_theme(theme: str) -> None:
    if theme == "Dark":
        st.markdown(
            """
            <style>
            .stApp { background-color: #0f172a; color: #e2e8f0; }
            section[data-testid="stSidebar"] { background-color: #111827; }
            </style>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            """
            <style>
            .stApp { background-color: #f8fafc; color: #0f172a; }
            section[data-testid="stSidebar"] { background-color: #e2e8f0; }
            </style>
            """,
            unsafe_allow_html=True,
        )


st.title("📓 Note App UI (Streamlit)")
theme = st.sidebar.radio("Theme", ["Light", "Dark"], index=0)
apply_theme(theme)

stats_response = requests.get(f"{API_URL}/stats")
if stats_response.status_code == 200:
    stats = stats_response.json()
    st.sidebar.metric("Total IDs", stats.get("total_ids", 0))
    st.sidebar.caption(
        f"Pinned IDs: {stats.get('pinned_ids', 0)} | Private IDs: {stats.get('private_ids', 0)}"
    )
else:
    st.sidebar.warning("Could not load note stats")

operation = st.sidebar.selectbox(
    "Choose an action",
    [
        "Create Note",
        "View All Notes",
        "View Single Note",
        "Update Note",
        "Pin/Unpin Note",
        "Delete Note",
    ],
)

if operation == "Create Note":
    st.subheader("Create a New Note")
    note_id = st.text_input("Note ID")
    title = st.text_input("Title")
    content = st.text_area("Content")
    is_private = st.checkbox("Make this note private")
    if st.button("Create"):
        data = {
            "id": note_id,
            "title": title,
            "content": content,
            "pinned": False,
            "is_private": is_private,
        }
        response = requests.post(API_URL, json=data)
        if response.status_code == 200:
            st.success(response.json()["message"])
        else:
            st.error(response.json().get("detail", "Request failed"))

elif operation == "View All Notes":
    st.subheader("All Notes")
    show_private = st.checkbox("Show private note content", value=False)
    response = requests.get(API_URL)
    if response.status_code == 200:
        notes = response.json()
        notes = sorted(notes, key=lambda n: n.get("pinned", False), reverse=True)
        for note in notes:
            pin_marker = "[PINNED] " if note.get("pinned", False) else ""
            private_marker = "PRIVATE" if note.get("is_private", False) else "PUBLIC"
            displayed_content = note["content"]
            if note.get("is_private", False) and not show_private:
                displayed_content = "[Hidden private content]"
            st.markdown(
                f"**ID:** {note['id']}  \n"
                f"**Title:** {pin_marker}{note['title']}  \n"
                f"**Visibility:** {private_marker}  \n"
                f"**Content:** {displayed_content}"
            )
            st.write("---")
    else:
        st.error("Failed to fetch notes.")

elif operation == "View Single Note":
    st.subheader("Get a Note by ID")
    note_id = st.text_input("Enter Note ID")
    reveal_private = st.checkbox("Reveal private content", value=False)
    if st.button("Get Note"):
        response = requests.get(f"{API_URL}/{note_id}")
        if response.status_code == 200:
            note = response.json()
            st.write(f"**ID:** {note['id']}")
            st.write(f"**Title:** {note['title']}")
            st.write(f"**Pinned:** {'Yes' if note.get('pinned', False) else 'No'}")
            st.write(f"**Private:** {'Yes' if note.get('is_private', False) else 'No'}")
            if note.get("is_private", False) and not reveal_private:
                st.write("**Content:** [Hidden private content]")
            else:
                st.write(f"**Content:** {note['content']}")
        else:
            st.error(response.json().get("detail", "Request failed"))

elif operation == "Update Note":
    st.subheader("Update a Note")
    note_id = st.text_input("Note ID")
    title = st.text_input("New Title")
    content = st.text_area("New Content")
    pinned = st.checkbox("Pinned", value=False)
    is_private = st.checkbox("Private", value=False)
    if st.button("Update"):
        data = {
            "id": note_id,
            "title": title,
            "content": content,
            "pinned": pinned,
            "is_private": is_private,
        }
        response = requests.put(f"{API_URL}/{note_id}", json=data)
        if response.status_code == 200:
            st.success(response.json()["message"])
        else:
            st.error(response.json().get("detail", "Request failed"))

elif operation == "Pin/Unpin Note":
    st.subheader("Pin or Unpin by ID")
    note_id = st.text_input("Note ID to pin/unpin")
    pin_value = st.checkbox("Pin this note", value=True)
    if st.button("Save Pin Setting"):
        response = requests.put(f"{API_URL}/{note_id}/pin", json={"pinned": pin_value})
        if response.status_code == 200:
            st.success(response.json()["message"])
        else:
            st.error(response.json().get("detail", "Request failed"))

elif operation == "Delete Note":
    st.subheader("Delete a Note")
    note_id = st.text_input("Enter Note ID to delete")
    if st.button("Delete"):
        response = requests.delete(f"{API_URL}/{note_id}")
        if response.status_code == 200:
            st.success(response.json()["message"])
        else:
            st.error(response.json().get("detail", "Request failed"))
