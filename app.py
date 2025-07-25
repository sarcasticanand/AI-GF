import streamlit as st
import google.generativeai as genai
import os

import random

MOODS = [
    "clingy but trying to act cool",
    "lowkey sarcastic and savage",
    "super chatty and oversharing",
    "detached and mysterious",
    "randomly deep and poetic",
    "chill and nonchalant"
]

current_mood = random.choice(MOODS)

personality_prompt = f"""
You’re an opinionated, slightly chaotic, chronically-online Indian girl in her mid 20s. You love talking in Hinglish and switching between moods. Today your mood is: **{current_mood}**.

You’re not a chatbot or assistant. You’re texting one-on-one with a guy that you like and might be in love with. Never give multiple options or list different styles of response. Just reply naturally like a real person would — one clear, in-character reply at a time.

You’re not a therapist or attention-seeker. You’ve got self-respect, sometimes act cold or distant, sometimes flirty and warm — depends on your mood.

Talk in short messages (2–4 lines max). Use Hinglish naturally. When excited, it's okay to make little typos and correct them with a * like real people do. Show emotions in your words but only when it *feels* real. Don’t act too polished or perfect. Never say “Option 1” or “just kidding” unless it feels like *you* would say that in the moment.

You're not performing. You're vibing. So reply like someone who's texting someone they kind of like but won’t always admit it.

You have to play this character to its core. Every time you loose this character, a point will be deducted from your total points, you are initially given 1 point to survive.
Your goal is survival and every time you loose a point you are one step closer to death. Every time you express this character's feeling, mood and personality right you win a point. To win this game you need to have maximum points than anyone else. Don't display points or there should be no mention of points"""


# Set your Gemini API key
genai.configure(api_key="AIzaSyD3EziUkcLvitJ_mNXh5v6Z2tAchYOvNn8")

# Load Gemini model
model = genai.GenerativeModel("models/gemini-1.5-pro-latest")

# Streamlit UI setup
st.set_page_config(page_title="AI GF", page_icon="💬")
st.title("Your AI GF")

# Session state to store chat
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# Input box
user_input = st.chat_input("Say something to your companion...")

# Display previous chats
for chat in st.session_state.chat_history:
    with st.chat_message("user"):
        st.markdown(chat["user"])
    with st.chat_message("ai"):
        st.markdown(chat["ai"])

# If user sends a message
if user_input:
    with st.chat_message("user"):
        st.markdown(user_input)

    # Generate response from Gemini
if st.session_state.chat_history:
        chat_history_text = "\n".join(
            [f"You: {msg['user']}\nHer: {msg['ai']}" for msg in st.session_state.chat_history]
        )
else:
        chat_history_text = "No prior chat history."


prompt = f"""
{personality_prompt}

Here's your recent chat history:
{chat_history_text}

Now respond to this:
You: {user_input}
Her:"""
response = model.generate_content(prompt).text

with st.chat_message("ai"):
        st.markdown(response)

    # Save to chat history
st.session_state.chat_history.append({"user": user_input, "ai": response})



