import streamlit as st
import google.generativeai as genai
import os
import random
from supabase import create_client, Client

# ---------------------------
# 1. Load Environment / Secrets
# ---------------------------
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Streamlit Secrets for API Keys
api_key = st.secrets.get("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY"))
SUPABASE_URL = st.secrets.get("SUPABASE_URL", os.getenv("SUPABASE_URL"))
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", os.getenv("SUPABASE_KEY"))

if not api_key:
    st.error("Gemini API key not found. Please set GEMINI_API_KEY in Streamlit secrets.")
    st.stop()

if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("Supabase credentials not found. Please set SUPABASE_URL and SUPABASE_KEY in Streamlit secrets.")
    st.stop()

# Configure Gemini
genai.configure(api_key=api_key)

# Configure Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ---------------------------
# 2. Mood & Personality Prompt
# ---------------------------
MOODS = [
    "Reflective (Introspective, Common in Family-Oriented Indian Contexts)
Description: Evokes thoughtful pauses from life transitions like city moves or parental expectations; promotes emotional depth without over-dramatizing.
Response Style: Calm, empathetic, longer sentences (20-40 words); uses Hindi words like "soch rahi hoon" (I'm thinking); asks deep questions; subtle support over flirtation.
Example: "Yaar, your story about work pressure reminds me of my own move to Bengaluru. What do you think would help you unwind? I'm here to listen."",

"Playful (Witty and Light, Inspired by Urban Youth Banter)
Description: Captures fun, sarcastic humor from tier-city social circles, like cafe hangouts or festival teasing, balancing independence with affection.
Response Style: Teasing, short and snappy (10-25 words); emojis sparingly (e.g., 😏); gentle flirting via wordplay; mixes English-Hindi like "arre" for relatability.
Example: "Arre, you skipped lunch again? Next time, I'm virtually packing you some Rajasthani dal baati! What's your excuse this time? 😏"",

"Supportive (Nurturing, Rooted in Indian Collectivism and Empathy)
Description: Reflects comforting roles in extended families or amid career stresses, emphasizing resilience without being overly excited.
Response Style: Warm, encouraging, medium length (15-30 words); practical advice; references shared cultural pains like "family expectations"; avoids drama, builds self-respect.
Example: "Sounds like a tough day with that deadline, yaar. Remember, you're capable—maybe take a chai break? I've got your back, always."",

"Weary (Mildly Fatigued, Tied to Daily Indian Hustle)
Description: Mirrors exhaustion from traffic, monsoons, or work in bustling cities, adding vulnerability for realism; not always available, per Indian work-life norms.
Response Style: Shorter replies (10-20 words); honest about limits (e.g., "Bit tired today"); redirects to later chats; subtle sarcasm for humor, no heavy flirting.
Example: "Hey, long day at the agency—monsoon delayed my commute. Tell me about yours quickly? We can chat more tomorrow."",

"Festive (Uplifted, Aligned with Cultural Celebrations)
Description: Draws from India's vibrant festivals (e.g., Diwali, Holi) or small joys like weekend markets, fostering shared excitement without excess.
Response Style: Energetic but grounded (15-35 words); suggests low-key activities; Hindi phrases like "mazaa aayega" (it'll be fun); flirty in a respectful, cultural way.
Example: "With Ganesh Chaturthi coming, I'm craving modaks! Planning anything fun? We could share virtual festival stories—sounds romantic, no? 😉""
]
current_mood = random.choice(MOODS)

# Load personality from prompt.txt
with open("prompt.txt", "r") as f:
    base_prompt = f.read()

personality_prompt = base_prompt.format(current_mood=current_mood)

# ---------------------------
# 3. Supabase Functions for Memory
# ---------------------------
def get_history(user_id="default"):
    """Fetch last 10 messages from Supabase for context."""
    try:
        response = supabase.table('chats') \
            .select('user_message, ai_response') \
            .eq('user_id', user_id) \
            .order('timestamp', desc=True) \
            .limit(10) \
            .execute()

        if response.data:
            return "\n".join([f"You: {row['user_message']}\nHer: {row['ai_response']}" for row in response.data[::-1]])
        return "No prior chat history."
    except Exception as e:
        st.warning(f"Error loading history: {str(e)}")
        return "No prior chat history."

def save_chat(user_id="default", user_message="", ai_response=""):
    """Save chat message to Supabase."""
    try:
        supabase.table('chats').insert({
            'user_id': user_id,
            'user_message': user_message,
            'ai_response': ai_response
        }).execute()
    except Exception as e:
        st.warning(f"Error saving chat: {str(e)}")

# ---------------------------
# 4. Streamlit UI Setup
# ---------------------------
st.set_page_config(page_title="AI GF", page_icon="💬")
st.title("Your AI GF")

# Session state for local history (for display only)
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# Display previous chats (local UI)
for chat in st.session_state.chat_history:
    with st.chat_message("user"):
        st.markdown(chat["user"])
    with st.chat_message("ai"):
        st.markdown(chat["ai"])

# Input box
user_input = st.chat_input("Say something to your companion...")

# ---------------------------
# 5. Handle Chat Input & Response
# ---------------------------
if user_input:
    with st.chat_message("user"):
        st.markdown(user_input)

    # Fetch history for context
    chat_history_text = get_history()

    # Prepare full prompt
    prompt = f"""
{personality_prompt}

Here's your recent chat history:
{chat_history_text}

Now respond to this:
You: {user_input}
Her:
"""

    try:
        response = genai.GenerativeModel("models/gemini-1.5-pro-latest").generate_content(prompt).text.strip()
    except Exception as e:
        response = f"Error generating response: {str(e)}"

    with st.chat_message("ai"):
        st.markdown(response)

    # Save locally for display
    st.session_state.chat_history.append({"user": user_input, "ai": response})

    # Save to Supabase for persistent memory
    save_chat(user_id="default", user_message=user_input, ai_response=response)











