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
import pytz

# ---------------------------
# 1. Load Environment / Secrets
# ---------------------------
api_key = st.secrets.get("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY"))
SUPABASE_URL = st.secrets.get("SUPABASE_URL", os.getenv("SUPABASE_URL"))
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", os.getenv("SUPABASE_KEY"))

if not api_key:
    st.error("Gemini API key not found. Please set GEMINI_API_KEY in Streamlit secrets.")
    st.stop()
if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("Supabase credentials not found. Please set them.")
    st.stop()

# Configure services
genai.configure(api_key=api_key)
model = genai.GenerativeModel("models/gemini-1.5-pro-latest")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Use IST for time-sensitive prompts
IST = pytz.timezone('Asia/Kolkata')
now_ist = datetime.now(IST)
CURRENT_DATE = now_ist.strftime("%Y-%m-%d")
CURRENT_TIME = now_ist.strftime("%H:%M")
current_hour = now_ist.hour

# ---------------------------
# 2. Mood & Prompt Setup
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
    st.session_state.user_id = str(uuid.uuid4())
if "current_mood" not in st.session_state:
    st.session_state.current_mood = random.choice(MOODS)
if "last_input_time" not in st.session_state:
    st.session_state.last_input_time = time.time()
if "conversation_state" not in st.session_state:
    st.session_state.conversation_state = {}
if "unavailability_reason" not in st.session_state:
    st.session_state.unavailability_reason = None


# Load and format personality prompt
with open("prompt.txt", "r") as f:
    base_prompt = f.read()

# This is the corrected block
personality_prompt = base_prompt.format(
    current_mood=st.session_state.current_mood,
    current_date=CURRENT_DATE,
    current_time=CURRENT_TIME
)

# Display previous chats
for chat in st.session_state.chat_history:
    with st.chat_message(chat["role"]):
        st.markdown(chat["content"])

user_input = st.chat_input("Say something to your companion...")

# ---------------------------
# 4. Supabase Functions for Memory
# ---------------------------
def get_history(user_id):
    try:
        response = supabase.table('chats').select('user_message, ai_response, user_name').eq('user_id', user_id).order('timestamp', desc=True).limit(10).execute()
        if response.data:
            history_text = "\n".join([f"You: {row['user_message']}\nHer: {row['ai_response']}" for row in response.data[::-1]])
            user_name = next((row['user_name'] for row in response.data if row.get('user_name')), "")
            return history_text, user_name
        return "No prior chat history.", ""
    except Exception as e:
        st.warning(f"Error loading history: {str(e)}")
        return "No prior chat history.", ""

def save_chat(user_id, user_message, ai_response):
    try:
        insert_data = {'user_id': user_id, 'user_message': user_message, 'ai_response': ai_response, 'timestamp': now_ist.isoformat()}
        name_match = re.search(r'(?:my name is|i\'m) (\w+( \w+)?)', user_message, re.IGNORECASE)
        if name_match:
            insert_data['user_name'] = name_match.group(1).strip()
        supabase.table('chats').insert(insert_data).execute()
    except Exception as e:
        st.warning(f"Error saving chat: {str(e)}")

# ---------------------------
# 5. Handle Chat Logic
# ---------------------------
if user_input:
    st.session_state.chat_history.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.last_input_time = time.time()

    # Check for unavailability first
    if st.session_state.unavailability_reason:
        response = f"Sorry yaar, I'm still busy with that {st.session_state.unavailability_reason}. Let's catch up in a bit, okay?"
    else:
        # Determine unavailability
        unavail_chance = 0.2 if current_hour >= 19 else 0.05
        if random.random() < unavail_chance:
            indian_reasons = ["family puja", "call with parents", "friend emergency", "work deadline"]
            st.session_state.unavailability_reason = random.choice(indian_reasons)
            response = f"Sorry yaar, I'm caught up with a {st.session_state.unavailability_reason}. Can we chat later? 😊"
        else:
            chat_history_text, user_name = get_history(st.session_state.user_id)
            if random.random() < 0.05 and chat_history_text != "No prior chat history.":
                chat_history_text = re.sub(r'(your \w+)', 'your [forgotten detail]', chat_history_text, count=1)

            encoding = tiktoken.get_encoding("cl100k_base")
            chat_history_text = encoding.decode(encoding.encode(chat_history_text)[:500])
            user_input_truncated = encoding.decode(encoding.encode(user_input)[:100])

            frustration_keywords = ["wtf", "why", "again", "forgot", "cring", "robot"]
            if any(word in user_input_truncated.lower() for word in frustration_keywords):
                st.session_state.current_mood = [m for m in MOODS if "Supportive" in m][0]
            elif random.random() < 0.2:
                st.session_state.current_mood = random.choice(MOODS)

            prompt = f"""
{personality_prompt}

### Conversation Context
- **Recent History:** {chat_history_text}
- **User's Name (if known):** {user_name}
- **Conversation State:** {st.session_state.conversation_state}

### Your Task
Respond to the user's latest message: "{user_input_truncated}"
"""
            
            for attempt in range(2):
                try:
                    response = model.generate_content(prompt).text.strip()
                    break
                except Exception as e:
                    if attempt == 1: response = "Oops, my brain's foggy—can you repeat? 😅"
                    time.sleep(1)

    delay = random.uniform(0.5, 2.0)
    if "Weary" in st.session_state.current_mood: delay += 1
    time.sleep(delay)

    st.session_state.chat_history.append({"role": "ai", "content": response})
    with st.chat_message("ai"):
        st.markdown(response)

    save_chat(st.session_state.user_id, user_input, response)

    if "toit" in user_input.lower(): st.session_state.conversation_state['confirmed_place'] = "Toit"
    time_match = re.search(r'\d+ baje', user_input)
    if time_match: st.session_state.conversation_state['confirmed_time'] = time_match.group(0)
