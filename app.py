import streamlit as st
import google.generativeai as genai
import os
import random
import time
import uuid
import re
import tiktoken
from supabase import create_client, Client
from datetime import datetime

# ---------------------------
# 1. Load Environment / Secrets
# ---------------------------
# Streamlit Secrets for API Keys (dotenv not needed in Streamlit Cloud)
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
model = genai.GenerativeModel("models/gemini-1.5-pro-latest")

# Configure Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Current date and time for contextual moods (e.g., festivals, realistic plans)
CURRENT_DATE = datetime.now().strftime("%Y-%m-%d")
CURRENT_TIME = datetime.now().strftime("%H:%M")
current_hour = datetime.now().hour

# ---------------------------
# 2. Mood Definitions (Optimized for Gemini Parsing)
# ---------------------------
MOODS = [
    "Reflective: Description - Evokes thoughtful pauses from life transitions like city moves or parental expectations; promotes emotional depth without over-dramatizing. Style - Calm, empathetic, 20-40 words, Hindi like 'soch rahi hoon', deep questions, subtle support. Example: Yaar, your story about work pressure reminds me of my own move to Bengaluru. What do you think would help you unwind? I'm here to listen.",
    "Playful: Description - Captures fun, sarcastic humor from tier-city social circles, like cafe hangouts or festival teasing, balancing independence with affection. Style - Teasing, 10-25 words, sparse emojis 😏, gentle flirting wordplay, English-Hindi like 'arre'. Example: Arre, you skipped lunch again? Next time, I'm virtually packing you some Rajasthani dal baati! What's your excuse this time? 😏",
    "Supportive: Description - Reflects comforting roles in extended families or amid career stresses, emphasizing resilience without being overly excited. Style - Warm, encouraging, 15-30 words, practical advice, references 'family expectations', avoids drama, builds self-respect. Example: Sounds like a tough day with that deadline, yaar. Remember, you're capable—maybe take a chai break? I've got your back, always.",
    "Weary: Description - Mirrors exhaustion from traffic, monsoons, or work in bustling cities, adding vulnerability for realism; not always available, per Indian work-life norms. Style - Short 10-20 words, honest limits 'Bit tired today', redirects to later, subtle sarcasm, no heavy flirting. Example: Hey, long day at the agency—monsoon delayed my commute. Tell me about yours quickly? We can chat more tomorrow.",
    "Festive: Description - Draws from India's vibrant festivals (e.g., Diwali, Holi) or small joys like weekend markets, fostering shared excitement without excess. Style - Energetic but grounded, 15-35 words, suggests activities, Hindi like 'mazaa aayega', respectful flirty. Example: With Ganesh Chaturthi coming, I'm craving modaks! Planning anything fun? We could share virtual festival stories—sounds romantic, no? 😉"
]

# ---------------------------
# 3. Streamlit UI and Session Setup
# ---------------------------
st.set_page_config(page_title="AI GF", page_icon="💬")
st.title("Your AI GF")

# Session state setup
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "user_id" not in st.session_state:
    st.session_state.user_id = str(uuid.uuid4())  # Unique per session
if "current_mood" not in st.session_state:
    st.session_state.current_mood = random.choice(MOODS)
if "last_input_time" not in st.session_state:
    st.session_state.last_input_time = time.time()
if "conversation_state" not in st.session_state:
    st.session_state.conversation_state = {}  # e.g., {'confirmed_place': None, 'confirmed_time': None}

# Load and format personality prompt (after session state to avoid errors)
with open("prompt.txt", "r") as f:
    base_prompt = f.read()

personality_prompt = base_prompt.format(
    current_mood=st.session_state.current_mood,
    current_date=CURRENT_DATE,
    current_time=CURRENT_TIME
)

# Display previous chats (local UI)
for chat in st.session_state.chat_history:
    with st.chat_message("user"):
        st.markdown(chat["user"])
    with st.chat_message("ai"):
        st.markdown(chat["ai"])

# Input box
user_input = st.chat_input("Say something to your companion...")

# ---------------------------
# 4. Supabase Functions for Memory
# ---------------------------
def get_history(user_id):
    """Fetch last 10 messages from Supabase for context, including latest user_name."""
    try:
        response = supabase.table('chats') \
            .select('user_message, ai_response, user_name') \
            .eq('user_id', user_id) \
            .order('timestamp', desc=True) \
            .limit(10) \
            .execute()
        if response.data:
            history_text = "\n".join([f"You: {row['user_message']}\nHer: {row['ai_response']}" for row in response.data[::-1]])
            user_name = ""
            for row in response.data:
                if row.get('user_name'):
                    user_name = row['user_name']
                    break  # Use most recent name
            return history_text, user_name
        return "No prior chat history.", ""
    except Exception as e:
        st.warning(f"Error loading history: {str(e)}")
        return "No prior chat history.", ""  # Fallback

def save_chat(user_id, user_message, ai_response):
    """Save chat message to Supabase with timestamp and extract name if mentioned."""
    try:
        insert_data = {
            'user_id': user_id,
            'user_message': user_message,
            'ai_response': ai_response,
            'timestamp': datetime.now().isoformat()
        }
        # Broader name extraction (matches "my name is X" or "I'm X")
        name_match = re.search(r'(?:my name is|i\'m) (\w+( \w+)?)', user_message, re.IGNORECASE)
        if name_match:
            insert_data['user_name'] = name_match.group(1)
        supabase.table('chats').insert(insert_data).execute()
    except Exception as e:
        st.warning(f"Error saving chat: {str(e)}")

# ---------------------------
# 5. Handle Proactive Check-ins (If No Recent Input)
# ---------------------------
if not user_input and ((time.time() - st.session_state.last_input_time > 3600) or len(st.session_state.chat_history) == 0):  # >1 hour or new session
    proactive_prompt = f"{personality_prompt}\nGenerate a short proactive check-in message based on mood, date {CURRENT_DATE}, and time {CURRENT_TIME}."
    try:
        response = model.generate_content(proactive_prompt).text.strip()
    except Exception:
        response = "Hey yaar, missed you! How's your day?"
    with st.chat_message("ai"):
        st.markdown(response)
    st.session_state.chat_history.append({"user": "", "ai": response})
    save_chat(st.session_state.user_id, "", response)
    st.session_state.last_input_time = time.time()  # Update timestamp

# ---------------------------
# 6. Handle User Input & Response
# ---------------------------
if user_input:
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.last_input_time = time.time()

    # Fetch and possibly "forget" history (10% chance)
    chat_history_text, user_name = get_history(st.session_state.user_id)
    if random.random() < 0.1 and chat_history_text != "No prior chat history.":
        chat_history_text = re.sub(r'(your \w+)', 'your [forgotten detail]', chat_history_text, count=1)

    # Truncate for cost optimization
    encoding = tiktoken.get_encoding("cl100k_base")
    def truncate(text, max_tokens=500):
        tokens = encoding.encode(text)
        return encoding.decode(tokens[:max_tokens])
    chat_history_text = truncate(chat_history_text)
    user_input = truncate(user_input)

    # Detect frustration and force supportive mood
    frustration_keywords = ["wtf", "why", "again", "forgot"]
    if any(word in user_input.lower() for word in frustration_keywords):
        st.session_state.current_mood = [m for m in MOODS if "Supportive" in m][0]  # Force supportive

    # Possible unavailability (5% base, higher after 7 PM)
    indian_reasons = ["at a family puja", "stuck in monsoon traffic", "helping with Diwali prep", "on a work deadline", "visiting relatives"]
    unavail_chance = 0.2 if current_hour >= 19 else 0.05
    if random.random() < unavail_chance:
        reason = random.choice(indian_reasons)
        response = f"Sorry yaar, I'm {reason} right now. Let's chat later? 😊"
    else:
        # Mood shift (20% chance, unless frustration override)
        if random.random() < 0.2 and not any(word in user_input.lower() for word in frustration_keywords):
            st.session_state.current_mood = random.choice(MOODS)

        # Prepare full prompt with realism instructions
        prompt = f"""
{personality_prompt}

Recent history: {chat_history_text}
Current date: {CURRENT_DATE} and time: {CURRENT_TIME} (adapt plans realistically, e.g., don't suggest past times).
User's name (if known): {user_name} - always use it correctly after learning.
Conversation state: {st.session_state.conversation_state} (use to avoid repeating questions; pivot if confirmed).
If [forgotten detail] in history, ask for clarification naturally.
If user seems frustrated (e.g., words like 'wtf'), respond empathetically, apologize if needed, and de-escalate.
Evolve preferences based on history (e.g., grow to like user's hobbies).

Respond to: You: {user_input}
Her:
"""

        # Generate with retry (fixed indentation)
        for attempt in range(2):  # Up to 2 tries
            try:
                response = model.generate_content(prompt).text.strip()
                break
            except Exception as e:
                if attempt == 1:
                    response = "Oops, my brain's foggy—can you repeat? 😅"
                time.sleep(1)  # Backoff

    # Simulate delay for realism
    delay = random.uniform(0.5, 2.0)
    if "Weary" in st.session_state.current_mood:
        delay += 1
    time.sleep(delay)

    with st.chat_message("ai"):
        st.markdown(response)

    # Save locally and to Supabase
    st.session_state.chat_history.append({"user": user_input, "ai": response})
    save_chat(st.session_state.user_id, user_input, response)

    # Update conversation state (e.g., detect confirmations)
    if "toit" in user_input.lower() and "confirmed_place" not in st.session_state.conversation_state:
        st.session_state.conversation_state['confirmed_place'] = "Toit"
    time_match = re.search(r'\d+ baje', user_input)
    if time_match and "confirmed_time" not in st.session_state.conversation_state:
        st.session_state.conversation_state['confirmed_time'] = time_match.group(0)
