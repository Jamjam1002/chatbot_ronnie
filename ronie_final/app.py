# WEB-BASED ALTERNATIVE MEDICINE RECOMMENDER USING GEN AI - Multimodal chat application with local models
# Copyright (C) 2024 Ronnie Perolino

import streamlit as st
from chat_api_handler import ChatAPIHandler
from streamlit_mic_recorder import mic_recorder
from utils import get_timestamp, load_config, get_avatar
from audio_handler import transcribe_audio
from pdf_handler import add_documents_to_db
from html_templates import css
from database_operations import save_text_message, save_image_message, save_audio_message, load_messages, get_all_chat_history_ids, delete_chat_history, load_last_k_text_messages_ollama
from utils import list_openai_models, list_ollama_models, command
import sqlite3

# Load configuration
config = load_config()

def toggle_pdf_chat():
    st.session_state.pdf_chat = True
    clear_cache()

def detoggle_pdf_chat():
    st.session_state.pdf_chat = False

def get_session_key():
    if st.session_state.session_key == "new_session":
        if st.session_state.new_session_key is None:
            st.session_state.new_session_key = get_timestamp()
        return st.session_state.new_session_key
    return st.session_state.session_key

def delete_chat_session_history():
    delete_chat_history(st.session_state.session_key)
    st.session_state.session_index_tracker = "new_session"

def clear_cache():
    st.cache_resource.clear()

def list_model_options():
    if st.session_state.endpoint_to_use == "ollama":
        ollama_options = list_ollama_models()
        if not ollama_options:
            st.warning("No ollama models available. Please pull a model from https://ollama.com/library.")
        return ollama_options
    elif st.session_state.endpoint_to_use == "openai":
        return list_openai_models()

def update_model_options():
    st.session_state.model_options = list_model_options()

def main():
    # Page configuration for title and favicon (page logo)
    st.set_page_config(
        page_title="REMEDYGEN Alternative Recommender",
        page_icon="C:/Users/Lenovo/ronnierecommender_december/chat_icons/bots_image.png"  # Replace with the actual path to your logo file
    )

    st.title("REMEDYGEN:ALTERNATIVE MEDICINE RECOMMENDER")
    st.write(css, unsafe_allow_html=True)

    # Initialize session state variables
    if "db_conn" not in st.session_state:
        st.session_state.session_key = "new_session"
        st.session_state.new_session_key = None
        st.session_state.session_index_tracker = "new_session"
        st.session_state.db_conn = sqlite3.connect(config["chat_sessions_database_path"], check_same_thread=False)
        st.session_state.audio_uploader_key = 0
        st.session_state.pdf_uploader_key = 1
        st.session_state.endpoint_to_use = "ollama"
        st.session_state.model_options = list_model_options()
        st.session_state.model_tracker = None

    # Ensure the session key is valid
    if st.session_state.session_key == "new_session" and st.session_state.new_session_key is not None:
        st.session_state.session_index_tracker = st.session_state.new_session_key

    # Sidebar Chat Sessions
    st.sidebar.image("C:/Users/Lenovo/ronnierecommender_december/chat_icons/bots_image.png", width=50)
    st.sidebar.title("Chat Sessions History")
    chat_sessions = ["new_session"]

    # Fetch all chat sessions with session names
    all_sessions = get_all_chat_history_ids()
    session_ids = []

    if all_sessions:
        chat_sessions += [session["name"] for session in all_sessions]
        session_ids = [session["id"] for session in all_sessions]
    else:
        st.sidebar.write("No chat history available.")

    # Ensure session_index_tracker is valid
    if "session_index_tracker" not in st.session_state:
        st.session_state.session_index_tracker = "new_session"

    if st.session_state.session_index_tracker in chat_sessions:
        index = chat_sessions.index(st.session_state.session_index_tracker)
    else:
        st.session_state.session_index_tracker = "new_session"
        index = 0  # Default to "new_session"

    # Sidebar session selector
    selected_session = st.sidebar.selectbox("Select a chat session", chat_sessions, index=index, key="session_selector")

    # Update session_key based on selection
    if selected_session == "new_session":
        st.session_state.session_key = "new_session"
    else:
        selected_index = chat_sessions.index(selected_session) - 1
        st.session_state.session_key = session_ids[selected_index]

    # Multi-selection deletion logic
    st.sidebar.write("Select sessions to delete:")
    sessions_to_delete = []
    for name in chat_sessions[1:]:  # Skip 'new_session'
        if st.sidebar.checkbox(name, key=f"delete_{name}"):
            sessions_to_delete.append(name)

    if st.sidebar.button("Delete Selected Sessions"):
        if sessions_to_delete:
            for session_name in sessions_to_delete:
                session_index = chat_sessions.index(session_name) - 1  # Align with session_ids
                session_id = session_ids[session_index]
                delete_chat_history(session_id)

            st.success("Selected sessions have been deleted.")
            st.rerun()
        else:
            st.warning("No sessions selected for deletion.")

    # Model and API selection
    api_col, model_col = st.sidebar.columns(2)
    api_col.selectbox("Select an API", ["ollama", "openai"], key="endpoint_to_use", on_change=update_model_options)
    model_col.selectbox("Select a Model", st.session_state.model_options, key="model_to_use")
    
    # File upload handling
    pdf_toggle_col, voice_rec_col = st.sidebar.columns(2)
    pdf_toggle_col.checkbox("PDF Chat", key="pdf_chat", value=False, on_change=clear_cache)
    with voice_rec_col:
        voice_recording = mic_recorder(start_prompt="Record Audio", stop_prompt="Stop recording", just_once=True)

    # Chat container and user input
    chat_container = st.container()
    user_input = st.chat_input("Please input your health concerns to get personalized suggestions", key="user_input")

    # Add uploaded files
    uploaded_pdf = st.sidebar.file_uploader("Upload a PDF file", accept_multiple_files=True,
                                            type=["pdf"], key=st.session_state.pdf_uploader_key, on_change=toggle_pdf_chat)
    uploaded_image = st.sidebar.file_uploader("Upload an image file", type=["jpg", "jpeg", "png"], on_change=detoggle_pdf_chat)
    uploaded_audio = st.sidebar.file_uploader("Upload an audio file", type=["wav", "mp3", "ogg"], key=st.session_state.audio_uploader_key)

    # PDF handling
    if uploaded_pdf:
        with st.spinner("Processing pdf..."):
            add_documents_to_db(uploaded_pdf)
            st.session_state.pdf_uploader_key += 2

    # Audio processing
    if voice_recording:
        transcribed_audio = transcribe_audio(voice_recording["bytes"])
        print(transcribed_audio)
        llm_answer = ChatAPIHandler.chat(user_input=transcribed_audio, 
                                        chat_history=load_last_k_text_messages_ollama(get_session_key(), config["chat_config"]["chat_memory_length"]))
        save_audio_message(get_session_key(), "user", voice_recording["bytes"])
        save_text_message(get_session_key(), "assistant", llm_answer)

    # Handle text input, image, and audio processing
    if user_input:
        # Process user text input
        llm_answer = ChatAPIHandler.chat(user_input=user_input,
                                         chat_history=load_last_k_text_messages_ollama(get_session_key(), config["chat_config"]["chat_memory_length"]))
        save_text_message(get_session_key(), "user", user_input)
        save_text_message(get_session_key(), "assistant", llm_answer)

        # Reset user input after processing
        user_input = None

    # Handle image upload processing
    if uploaded_image:
        with st.spinner("Processing image..."):
            llm_answer = ChatAPIHandler.chat(user_input=user_input, chat_history=[], image=uploaded_image.getvalue())
            save_text_message(get_session_key(), "user", "Image uploaded")
            save_image_message(get_session_key(), "user", uploaded_image.getvalue())
            save_text_message(get_session_key(), "assistant", llm_answer)

        uploaded_image = None  # Reset image after processing

    # Handle audio upload processing
    if uploaded_audio:
        transcribed_audio = transcribe_audio(uploaded_audio.getvalue())
        print(transcribed_audio)
        llm_answer = ChatAPIHandler.chat(user_input=transcribed_audio, chat_history=[])
        save_audio_message(get_session_key(), "user", uploaded_audio.getvalue())
        save_text_message(get_session_key(), "assistant", llm_answer)
        
        st.session_state.audio_uploader_key += 2
        uploaded_audio = None  # Reset audio after processing

    # Display chat history
    with chat_container:
        chat_history_messages = load_messages(get_session_key())
        for message in chat_history_messages:
            with st.chat_message(name=message["sender_type"], avatar=get_avatar(message["sender_type"])):
                if message["message_type"] == "text":
                    st.write(message["content"])
                elif message["message_type"] == "image":
                    st.image(message["content"])
                elif message["message_type"] == "audio":
                    st.audio(message["content"], format="audio/wav")

if __name__ == "__main__":
    main()
