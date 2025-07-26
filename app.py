import streamlit as st
import google.generativeai as genai
import os
import random

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Read the Gemini API key from environment
api_key = st.secrets["GEMINI_API_KEY"]
genai.configure(api_key=api_key)


if not api_key:
    st.error("GEMINI_API_KEY not found in environment variables.")
    st.stop()

# Configure Gemini
genai.configure(api_key=api_key)

# Mood options
MOODS = [
    "clingy but trying to act cool",
    "lowkey sarcastic and savage",
    "super chatty and oversharing",
    "detached and mysterious",
    "randomly deep and poetic",
    "chill and nonchalant"
]

# Randomly pick one mood
current_mood = random.choice(MOODS)

# Character persona prompt
with open("prompt.txt", "r") as f:
    base_prompt = f.read()

personality_prompt = base_prompt.format(current_mood=current_mood)
# Load Gemini model
model = genai.GenerativeModel("models/gemini-1.5-pro-latest")

# Streamlit UI setup
st.set_page_config(page_title="AI GF", page_icon="💬")
st.title("Your AI GF")

# Session state for chat
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# Display previous chats
for chat in st.session_state.chat_history:
    with st.chat_message("user"):
        st.markdown(chat["user"])
    with st.chat_message("ai"):
        st.markdown(chat["ai"])

# Input box
user_input = st.chat_input("Say something to your companion...")

# Handle new input
if user_input:
    with st.chat_message("user"):
        st.markdown(user_input)

    # Prepare chat history string
    if st.session_state.chat_history:
        chat_history_text = "\n".join(
            [f"You: {msg['user']}\nHer: {msg['ai']}" for msg in st.session_state.chat_history]
        )
    else:
        chat_history_text = "No prior chat history."

    # Full prompt for model
    prompt = f"""
{personality_prompt}

Here's your recent chat history:
{chat_history_text}

Now respond to this:
You: {user_input}
Her:"""

    try:
        response = model.generate_content(prompt).text.strip()
    except Exception as e:
        response = f"Error generating response: {str(e)}"

    with st.chat_message("ai"):
        st.markdown(response)

    st.session_state.chat_history.append({"user": user_input, "ai": response})
