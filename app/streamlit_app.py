# streamlit_app.py
import streamlit as st
import requests

API_URL = "http://fastapi:8000/notes"  # Use "http://localhost:8000/notes" if running locally

st.title("📓 Note App UI (Streamlit)")

# -----------------------
# Sidebar: Select Operation
# -----------------------
operation = st.sidebar.selectbox(
    "Choose an action",
    ["Create Note", "View All Notes", "View Single Note", "Update Note", "Delete Note"]
)

# -----------------------
# Create Note
# -----------------------
if operation == "Create Note":
    st.subheader("Create a New Note")
    note_id = st.text_input("Note ID")
    title = st.text_input("Title")
    content = st.text_area("Content")
    if st.button("Create"):
        data = {"id": note_id, "title": title, "content": content}
        response = requests.post(API_URL, json=data)
        if response.status_code == 200:
            st.success(response.json()["message"])
        else:
            st.error(response.json()["detail"])

# -----------------------
# View All Notes
# -----------------------
elif operation == "View All Notes":
    st.subheader("All Notes")
    response = requests.get(API_URL)
    if response.status_code == 200:
        notes = response.json()
        for note in notes:
            st.markdown(f"**ID:** {note['id']}  \n**Title:** {note['title']}  \n**Content:** {note['content']}")
            st.write("---")
    else:
        st.error("Failed to fetch notes.")

# -----------------------
# View Single Note
# -----------------------
elif operation == "View Single Note":
    st.subheader("Get a Note by ID")
    note_id = st.text_input("Enter Note ID")
    if st.button("Get Note"):
        response = requests.get(f"{API_URL}/{note_id}")
        if response.status_code == 200:
            note = response.json()
            st.write(f"**ID:** {note['id']}")
            st.write(f"**Title:** {note['title']}")
            st.write(f"**Content:** {note['content']}")
        else:
            st.error(response.json()["detail"])

# -----------------------
# Update Note
# -----------------------
elif operation == "Update Note":
    st.subheader("Update a Note")
    note_id = st.text_input("Note ID")
    title = st.text_input("New Title")
    content = st.text_area("New Content")
    if st.button("Update"):
        data = {"id": note_id, "title": title, "content": content}
        response = requests.put(f"{API_URL}/{note_id}", json=data)
        if response.status_code == 200:
            st.success(response.json()["message"])
        else:
            st.error(response.json()["detail"])

# -----------------------
# Delete Note
# -----------------------
elif operation == "Delete Note":
    st.subheader("Delete a Note")
    note_id = st.text_input("Enter Note ID to delete")
    if st.button("Delete"):
        response = requests.delete(f"{API_URL}/{note_id}")
        if response.status_code == 200:
            st.success(response.json()["message"])
        else:
            st.error(response.json()["detail"])