from utils import load_config
import streamlit as st
import sqlite3
config = load_config()

def get_db_connection():
    return st.session_state.db_conn

def get_db_cursor(db_connection):
    return db_connection.cursor()

def get_db_connection_and_cursor():
    conn = get_db_connection()
    return conn, conn.cursor()

def close_db_connection():
    if 'db_conn' in st.session_state and st.session_state.db_conn is not None:
        st.session_state.db_conn.close()
        st.session_state.db_conn = None


def save_text_message(chat_history_id, sender_type, text):
    conn, cursor = get_db_connection_and_cursor()
    
    # Check if this is the first user message in the session
    cursor.execute("SELECT COUNT(*) FROM messages WHERE chat_history_id = ?", (chat_history_id,))
    message_count = cursor.fetchone()[0]
    
    if message_count == 0:  # If it's the first message, update session name
        cursor.execute('INSERT INTO messages (chat_history_id, sender_type, message_type, text_content) VALUES (?, ?, ?, ?)',
                       (chat_history_id, sender_type, 'text', text))
        cursor.execute('INSERT OR REPLACE INTO chat_sessions (chat_history_id, session_name) VALUES (?, ?)',
                       (chat_history_id, text[:30]))  # Save first 30 characters of the message
    else:
        cursor.execute('INSERT INTO messages (chat_history_id, sender_type, message_type, text_content) VALUES (?, ?, ?, ?)',
                       (chat_history_id, sender_type, 'text', text))

    conn.commit()


def save_image_message(chat_history_id, sender_type, image_bytes):
    conn, cursor = get_db_connection_and_cursor()

    cursor.execute('INSERT INTO messages (chat_history_id, sender_type, message_type, blob_content) VALUES (?, ?, ?, ?)',
                   (chat_history_id, sender_type, 'image', sqlite3.Binary(image_bytes)))

    conn.commit()

def save_audio_message(chat_history_id, sender_type, audio_bytes):
    conn, cursor = get_db_connection_and_cursor()

    cursor.execute('INSERT INTO messages (chat_history_id, sender_type, message_type, blob_content) VALUES (?, ?, ?, ?)',
                   (chat_history_id, sender_type, 'audio', sqlite3.Binary(audio_bytes)))

    conn.commit()

def load_messages(chat_history_id):
    conn, cursor = get_db_connection_and_cursor()

    query = "SELECT message_id, sender_type, message_type, text_content, blob_content FROM messages WHERE chat_history_id = ?"
    cursor.execute(query, (chat_history_id,))

    messages = cursor.fetchall()
    chat_history = []
    for message in messages:
        message_id, sender_type, message_type, text_content, blob_content = message

        if message_type == 'text':
            chat_history.append({'message_id': message_id, 'sender_type': sender_type, 'message_type': message_type, 'content': text_content})
        else:
            chat_history.append({'message_id': message_id, 'sender_type': sender_type, 'message_type': message_type, 'content': blob_content})


    return chat_history

def load_last_k_text_messages(chat_history_id, k):
    conn, cursor = get_db_connection_and_cursor()

    query = """
    SELECT message_id, sender_type, message_type, text_content
    FROM messages
    WHERE chat_history_id = ? AND message_type = 'text'
    ORDER BY message_id DESC
    LIMIT ?
    """
    cursor.execute(query, (chat_history_id, k))

    messages = cursor.fetchall()
    chat_history = []
    for message in reversed(messages):
        message_id, sender_type, message_type, text_content = message

        chat_history.append({
            'message_id': message_id,
            'sender_type': sender_type,
            'message_type': message_type,
            'content': text_content
        })


    return chat_history

def get_all_chat_history_ids():
    conn, cursor = get_db_connection_and_cursor()

    # Fetch session names (user's first prompt) from the chat_sessions table
    query = "SELECT chat_history_id, session_name FROM chat_sessions ORDER BY chat_history_id ASC"
    cursor.execute(query)

    chat_sessions = cursor.fetchall()
    return [{"id": row[0], "name": row[1]} for row in chat_sessions]

def delete_chat_history(chat_history_id):
    conn, cursor = get_db_connection_and_cursor()

    # Delete from messages table
    cursor.execute("DELETE FROM messages WHERE chat_history_id = ?", (chat_history_id,))
    
    # Delete from chat_sessions table
    cursor.execute("DELETE FROM chat_sessions WHERE chat_history_id = ?", (chat_history_id,))
    
    conn.commit()
    print(f"All entries with chat_history_id {chat_history_id} have been deleted.")


def init_db():
    db_path = config["chat_sessions_database_path"]
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create the messages table
    create_messages_table = """
    CREATE TABLE IF NOT EXISTS messages (
        message_id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_history_id TEXT NOT NULL,
        sender_type TEXT NOT NULL,
        message_type TEXT NOT NULL,
        text_content TEXT,
        blob_content BLOB
    );
    """

    # Create the chat_sessions table to store session names
    create_chat_sessions_table = """
    CREATE TABLE IF NOT EXISTS chat_sessions (
        chat_history_id TEXT PRIMARY KEY,
        session_name TEXT NOT NULL
    );
    """

    cursor.execute(create_messages_table)
    cursor.execute(create_chat_sessions_table)
    conn.commit()
    conn.close()
    print("Database initialized successfully.")

def load_last_k_text_messages_ollama(chat_history_id, k):
    conn, cursor = get_db_connection_and_cursor()

    query = """
    SELECT message_id, sender_type, message_type, text_content, blob_content
    FROM messages
    WHERE chat_history_id = ? AND message_type = 'text' 
    ORDER BY message_id DESC
    LIMIT ?
    """
    #OR message_type = 'image'
    cursor.execute(query, (chat_history_id, k))

    messages = cursor.fetchall()
    chat_history = []
    for message in reversed(messages):
        message_id, sender_type, message_type, text_content, blob_content = message
        chat_history.append({
            'role': sender_type,
            'content': text_content
        })


    return chat_history

def verify_tables():
    conn = sqlite3.connect(config["chat_sessions_database_path"])
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print("Existing tables:", tables)
    conn.close()

    # Run verification
init_db()
verify_tables()

if __name__ == "__main__":
    print("Initializing database...")
    init_db()
