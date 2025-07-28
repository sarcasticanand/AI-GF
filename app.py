import streamlit as st
import google.generativeai as genai
import os
import random
import time
import uuid
import re
import json
from supabase import create_client, Client
from datetime import datetime, timedelta, date
import pytz
from typing import Dict, List, Optional, Tuple
import hashlib
import calendar
import math

# ---------------------------
# 1. CONFIGURATION & SETUP
# ---------------------------
st.set_page_config(
    page_title="Malavika - Your AI Companion", 
    page_icon="💕",
    layout="wide"
)

# Load Environment & Secrets
api_key = st.secrets.get("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY"))
SUPABASE_URL = st.secrets.get("SUPABASE_URL", os.getenv("SUPABASE_URL"))
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", os.getenv("SUPABASE_KEY"))

if not api_key:
    st.error("Gemini API key not found.")
    st.stop()
if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("Supabase credentials not found.")
    st.stop()

# Configure services
genai.configure(api_key=api_key)
model = genai.GenerativeModel("models/gemini-1.5-pro-latest")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Time setup (IST)
IST = pytz.timezone('Asia/Kolkata')
now_ist = datetime.now(IST)
CURRENT_DATE = now_ist.strftime("%Y-%m-%d")
CURRENT_TIME = now_ist.strftime("%H:%M")
current_hour = now_ist.hour
current_month = now_ist.month
current_day = now_ist.day

# ---------------------------
# 2. CONSTANTS & PERSONAL DETAILS
# ---------------------------
MALAVIKA_BIRTHDAY = {"month": 3, "day": 15}
MALAVIKA_CYCLE_START = {"month": 7, "day": 20}
MALAVIKA_CYCLE_LENGTH = 28
MALAVIKA_WORK_SCHEDULE = {
    "regular_start": 9,
    "regular_end": 18,
    "late_days": ["Tuesday", "Thursday"],
    "wfh_days": ["Monday", "Wednesday", "Friday"]
}

# Festival Calendar 2025
FESTIVAL_CALENDAR = {
    "2025-08-19": {"name": "Raksha Bandhan", "type": "family", "prep_days": 2},
    "2025-08-27": {"name": "Ganesh Chaturthi", "type": "celebration", "prep_days": 3},
    "2025-09-07": {"name": "Ganesh Visarjan", "type": "celebration", "prep_days": 1},
    "2025-10-02": {"name": "Gandhi Jayanti", "type": "national", "prep_days": 0},
    "2025-10-12": {"name": "Dussehra", "type": "celebration", "prep_days": 2},
    "2025-11-01": {"name": "Diwali", "type": "major", "prep_days": 5},
    "2025-11-02": {"name": "Govardhan Puja", "type": "family", "prep_days": 1},
    "2025-11-04": {"name": "Bhai Dooj", "type": "family", "prep_days": 1},
    "2025-12-25": {"name": "Christmas", "type": "celebration", "prep_days": 2}
}

SOCIAL_EVENTS = {
    "2025-08-05": {"name": "Priyanka's Birthday", "type": "friend_birthday", "prep_days": 1},
    "2025-09-12": {"name": "Shivani's Birthday", "type": "friend_birthday", "prep_days": 1},
    "2025-10-18": {"name": "College Friend Reunion", "type": "social", "prep_days": 2},
    "2025-11-25": {"name": "Cousin's Wedding", "type": "family_event", "prep_days": 3}
}

MOODS = ["loving", "playful", "contemplative", "supportive", "sleepy", "excited", "vulnerable", "flirty"]
RELATIONSHIP_STAGES = ["getting_to_know", "friends", "close_friends", "romantic_interest", "committed"]
EMOJI_OPTIONS = ["😊", "😂", "❤️", "😍", "🤔", "😢", "😴", "🔥", "👍", "🙏"]

# ---------------------------
# 3. FIXED AVAILABILITY SYSTEM
# ---------------------------
def get_single_unavailability_reason():
    """Get ONE random unavailability reason - never combine multiple"""
    
    # Define separate reason categories - only pick ONE
    work_reasons = [
        {"excuse": "stuck in a client meeting", "return_time": "after this call", "duration_mins": random.randint(5, 8)},
        {"excuse": "on a tight deadline", "return_time": "once I submit this", "duration_mins": random.randint(6, 10)},
        {"excuse": "presenting to the team", "return_time": "after my presentation", "duration_mins": random.randint(4, 7)},
        {"excuse": "back-to-back calls today", "return_time": "between meetings", "duration_mins": random.randint(5, 9)}
    ]
    
    health_reasons = [
        {"excuse": "feeling a bit under the weather", "return_time": "once I rest a bit", "duration_mins": random.randint(6, 10)},
        {"excuse": "have a mild headache", "return_time": "after I take some rest", "duration_mins": random.randint(5, 8)},
        {"excuse": "this cough is bothering me", "return_time": "once I feel better", "duration_mins": random.randint(7, 12)},
        {"excuse": "feeling really tired today", "return_time": "after a quick nap", "duration_mins": random.randint(8, 15)}
    ]
    
    personal_reasons = [
        {"excuse": "mom called from Jaipur", "return_time": "once I finish this call", "duration_mins": random.randint(6, 12)},
        {"excuse": "had to run to the grocery store", "return_time": "once I'm back home", "duration_mins": random.randint(8, 15)},
        {"excuse": "Shivani needs help with something", "return_time": "once I sort this out", "duration_mins": random.randint(5, 10)},
        {"excuse": "dealing with apartment maintenance", "return_time": "once they're done", "duration_mins": random.randint(10, 20)}
    ]
    
    # Pick ONE category randomly, then ONE reason from that category
    all_categories = [work_reasons, health_reasons, personal_reasons]
    chosen_category = random.choice(all_categories)
    chosen_reason = random.choice(chosen_category)
    
    return chosen_reason

def check_if_user_agreed(user_input):
    """Check if user has agreed to wait"""
    agreement_words = ["cool", "okay", "ok", "sure", "fine", "alright", "understood", "got it", "np", "no problem"]
    user_text = user_input.lower().strip()
    
    # Exact matches or very short responses that indicate agreement
    return (user_text in agreement_words or 
            len(user_text) <= 4 and any(word in user_text for word in ["ok", "k", "sure"]))

def should_become_unavailable():
    """Determine if Malavika should become unavailable (20% chance)"""
    return random.random() < 0.20  # 20% chance

def should_return_from_unavailability():
    """Check if enough time has passed to return from unavailability"""
    if "unavailability_start_time" not in st.session_state:
        return False
    
    if "unavailability_duration" not in st.session_state:
        return False
    
    # Check if the specified duration has passed
    elapsed_minutes = (time.time() - st.session_state.unavailability_start_time) / 60
    return elapsed_minutes >= st.session_state.unavailability_duration

def generate_return_message(original_excuse, user_name):
    """Generate a natural return message"""
    
    return_phrases = {
        "stuck in a client meeting": [
            f"Finally done with that meeting! {user_name}, tell me everything - I have time now",
            f"Meeting over! {user_name}, what's up? Can chat properly now",
            f"Client call finished! {user_name}, missed chatting - what have you been up to?"
        ],
        "on a tight deadline": [
            f"Deadline submitted! {user_name}, finally free - tell me about your day",
            f"Project done! {user_name}, araam se bata what's happening",
            f"Work finished! {user_name}, now I have all the time for you"
        ],
        "presenting to the team": [
            f"Presentation went well! {user_name}, free now - what's new?",
            f"Done with my presentation! {user_name}, can focus on you now",
            f"Team meeting over! {user_name}, tell me everything"
        ],
        "feeling a bit under the weather": [
            f"Feeling much better now! {user_name}, what's up? I'm all yours",
            f"Headache gone! {user_name}, missed you - tell me about your day",
            f"Much better now! {user_name}, araam se bata what happened today"
        ],
        "mom called from Jaipur": [
            f"Mom's call finally done! {user_name}, she had so much to say - anyway, what's up with you?",
            f"Finished talking to family! {user_name}, now tell me your stories",
            f"Family time over! {user_name}, I'm all yours now"
        ],
        "had to run to the grocery store": [
            f"Back from shopping! {user_name}, missed you - what have you been doing?",
            f"Grocery done! {user_name}, finally can chat properly",
            f"Back home! {user_name}, tell me everything I missed"
        ]
    }
    
    # Get matching return message or use default
    messages = return_phrases.get(original_excuse, [
        f"All sorted now! {user_name}, what's up?",
        f"Free finally! {user_name}, missed chatting with you",
        f"Done with everything! {user_name}, tell me about your day"
    ])
    
    return random.choice(messages)

# ---------------------------
# 4. CORE BIOLOGICAL SYSTEMS (Simplified)
# ---------------------------
def get_menstrual_cycle_info():
    """Calculate current menstrual cycle phase"""
    last_period = datetime(2025, MALAVIKA_CYCLE_START["month"], MALAVIKA_CYCLE_START["day"])
    days_since_last = (now_ist.date() - last_period.date()).days
    cycle_day = (days_since_last % MALAVIKA_CYCLE_LENGTH) + 1
    
    if 1 <= cycle_day <= 5:
        return {"phase": "menstrual", "energy_level": 0.3, "mood_tendencies": ["vulnerable", "sleepy"]}
    elif 6 <= cycle_day <= 13:
        return {"phase": "follicular", "energy_level": 0.8, "mood_tendencies": ["excited", "playful"]}
    elif 14 <= cycle_day <= 16:
        return {"phase": "ovulation", "energy_level": 1.0, "mood_tendencies": ["flirty", "loving"]}
    else:
        if cycle_day >= 25:
            return {"phase": "luteal_pms", "energy_level": 0.5, "mood_tendencies": ["vulnerable", "contemplative"]}
        else:
            return {"phase": "luteal", "energy_level": 0.7, "mood_tendencies": ["contemplative", "supportive"]}

def get_seasonal_health_context():
    """Simplified seasonal health"""
    if current_month in [6, 7, 8, 9]:  # Monsoon
        return {"season": "monsoon", "illness_risk": 0.3, "energy_modifier": -0.2}
    elif current_month in [12, 1, 2]:  # Winter
        return {"season": "winter", "illness_risk": 0.2, "energy_modifier": -0.1}
    elif current_month in [3, 4, 5]:  # Summer
        return {"season": "summer", "illness_risk": 0.15, "energy_modifier": 0.1}
    else:
        return {"season": "post_monsoon", "illness_risk": 0.1, "energy_modifier": 0.2}

# ---------------------------
# 5. PERSISTENT USER SYSTEM
# ---------------------------
def get_browser_fingerprint():
    if "browser_fingerprint" not in st.session_state:
        fingerprint_key = f"user_fingerprint_{int(time.time() / 86400)}"
        st.session_state.browser_fingerprint = fingerprint_key
    return st.session_state.browser_fingerprint

def get_persistent_user_id():
    browser_fp = get_browser_fingerprint()
    user_id = hashlib.md5(f"{browser_fp}_malavika_user".encode()).hexdigest()
    return user_id

# ---------------------------
# 6. DATABASE FUNCTIONS (Simplified)
# ---------------------------
def get_user_profile(user_id):
    """Get user profile with fallback"""
    try:
        profile_response = supabase.table('user_profiles').select('*').eq('user_id', user_id).execute()
        personality_response = supabase.table('ai_personality_state').select('*').eq('user_id', user_id).execute()
        
        if profile_response.data and personality_response.data:
            return {
                'profile': profile_response.data[0],
                'personality': personality_response.data[0]
            }
        else:
            # Initialize new user
            return initialize_new_user(user_id)
    except:
        return {
            'profile': {'user_id': user_id, 'name': ''},
            'personality': {'current_mood': 'playful', 'relationship_stage': 'getting_to_know', 'intimacy_level': 1}
        }

def initialize_new_user(user_id):
    """Initialize new user in database"""
    try:
        profile_data = {
            'user_id': user_id,
            'name': '',
            'created_at': now_ist.isoformat(),
            'last_updated': now_ist.isoformat()
        }
        supabase.table('user_profiles').insert(profile_data).execute()

        personality_data = {
            'user_id': user_id,
            'current_mood': random.choice(MOODS),
            'intimacy_level': 1,
            'relationship_stage': 'getting_to_know',
            'updated_at': now_ist.isoformat()
        }
        supabase.table('ai_personality_state').insert(personality_data).execute()
        
        return {
            'profile': profile_data,
            'personality': personality_data
        }
    except:
        return {
            'profile': {'user_id': user_id, 'name': ''},
            'personality': {'current_mood': 'playful', 'relationship_stage': 'getting_to_know', 'intimacy_level': 1}
        }

def save_conversation(user_id, user_message, ai_response):
    """Save conversation to database"""
    try:
        chat_data = {
            'user_id': user_id,
            'user_message': user_message,
            'ai_response': ai_response,
            'timestamp': now_ist.strftime('%Y-%m-%d %H:%M:%S')
        }
        supabase.table('chats').insert(chat_data).execute()
    except:
        pass

def detect_user_emotion(message):
    """Simple emotion detection"""
    message_lower = message.lower()
    
    if any(word in message_lower for word in ["happy", "great", "awesome", "excited"]):
        return "happy"
    elif any(word in message_lower for word in ["sad", "down", "upset", "hurt"]):
        return "sad"
    elif any(word in message_lower for word in ["angry", "mad", "frustrated", "annoyed"]):
        return "frustrated"
    elif any(word in message_lower for word in ["love", "adore", "care", "miss"]):
        return "loving"
    else:
        return "neutral"

def limit_emojis(text, max_emojis=1):
    """Limit emojis in response"""
    emoji_pattern = re.compile(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F700-\U0001F77F\U0001F780-\U0001F7FF\U0001F800-\U0001F8FF\U0001F900-\U0001F9FF\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF\u2600-\u26FF\u2700-\u27BF]')
    emojis_found = emoji_pattern.findall(text)
    
    if len(emojis_found) <= max_emojis:
        return text
    
    emoji_count = 0
    result = []
    
    for char in text:
        if emoji_pattern.match(char):
            emoji_count += 1
            if emoji_count > max_emojis:
                continue
        result.append(char)
    
    return ''.join(result).strip()

def simulate_typing():
    """Simple typing simulation"""
    typing_placeholder = st.empty()
    
    typing_placeholder.markdown("💭 *typing...*")
    time.sleep(random.uniform(1.0, 2.0))
    
    typing_placeholder.empty()
    time.sleep(random.uniform(1.0, 2.0))  # Silent pause
    
    typing_placeholder.markdown("💭 *typing...*")
    time.sleep(random.uniform(0.8, 1.5))
    
    typing_placeholder.empty()

# ---------------------------
# 7. STREAMLIT UI
# ---------------------------
st.markdown("""
<div style='text-align: center; padding: 20px;'>
    <h1 style='color: #FF69B4; font-family: Georgia;'>💕 Malavika - Your AI Companion</h1>
    <p style='color: #666; font-style: italic;'>Your realistic AI girlfriend</p>
</div>
""", unsafe_allow_html=True)

# Get user data
user_id = get_persistent_user_id()
user_data = get_user_profile(user_id)

# Initialize session state
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "selected_emoji" not in st.session_state:
    st.session_state.selected_emoji = ""

# Simplified sidebar
with st.sidebar:
    st.markdown("### 💕 Status")
    st.write(f"**Time:** {CURRENT_TIME} IST")
    
    # Show if currently unavailable
    if "current_unavailability" in st.session_state:
        st.write(f"**Status:** Busy ({st.session_state.current_unavailability['excuse']})")
        remaining_mins = st.session_state.unavailability_duration - ((time.time() - st.session_state.unavailability_start_time) / 60)
        if remaining_mins > 0:
            st.write(f"**Back in:** {remaining_mins:.1f} minutes")
    else:
        st.write("**Status:** Available")
    
    if user_data['profile'].get('name'):
        st.write(f"**Your Name:** {user_data['profile']['name']}")
    
    # Quick emoji selector
    st.markdown("### Quick Emojis")
    cols = st.columns(5)
    for i, emoji in enumerate(EMOJI_OPTIONS):
        col_idx = i % 5
        if cols[col_idx].button(emoji, key=f"emoji_btn_{i}"):
            st.session_state.selected_emoji = emoji
            st.rerun()
    
    if st.session_state.selected_emoji:
        st.success(f"Selected: {st.session_state.selected_emoji}")
        if st.button("Clear emoji"):
            st.session_state.selected_emoji = ""
            st.rerun()

# Display chat history
for chat in st.session_state.chat_history:
    with st.chat_message(chat["role"]):
        st.markdown(chat["content"])

# Chat input
def get_chat_input():
    base_input = st.chat_input("Talk to Malavika...")
    if base_input:
        if st.session_state.selected_emoji:
            final_input = f"{base_input} {st.session_state.selected_emoji}"
            st.session_state.selected_emoji = ""
            return final_input
        return base_input
    return None

user_input = get_chat_input()

# ---------------------------
# 8. MAIN CHAT LOGIC (FIXED)
# ---------------------------
if user_input:
    # Add user message to UI
    st.session_state.chat_history.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)
    
    # CHECK 1: Should she return from unavailability?
    if should_return_from_unavailability():
        # Time to return - generate return message
        original_excuse = st.session_state.current_unavailability['excuse']
        user_name = user_data['profile'].get('name', 'handsome')
        return_message = generate_return_message(original_excuse, user_name)
        
        # Clear unavailability status
        if "current_unavailability" in st.session_state:
            del st.session_state.current_unavailability
        if "unavailability_start_time" in st.session_state:
            del st.session_state.unavailability_start_time
        if "unavailability_duration" in st.session_state:
            del st.session_state.unavailability_duration
        
        # Send return message
        st.session_state.chat_history.append({"role": "assistant", "content": return_message})
        with st.chat_message("assistant"):
            st.markdown(return_message)
        
        save_conversation(user_id, user_input, return_message)
        st.stop()  # Process this return message and wait for next input
    
    # CHECK 2: Is she currently unavailable?
    if "current_unavailability" in st.session_state:
        # She's busy - check if user agreed to wait
        if check_if_user_agreed(user_input):
            # User agreed - Malavika should NOT respond
            save_conversation(user_id, user_input, "")  # Save user input but no AI response
            st.stop()  # No response from Malavika
        else:
            # User didn't agree clearly - give ONE more gentle reminder
            excuse = st.session_state.current_unavailability['excuse']
            return_time = st.session_state.current_unavailability['return_time']
            
            reminder_responses = [
                f"Still {excuse}, {user_data['profile'].get('name', 'yaar')}. Will message you {return_time}",
                f"Hey, still busy with this. Text you {return_time} okay?",
                f"Quick sec - still {excuse}. Chat {return_time}?"
            ]
            response = random.choice(reminder_responses)
            
            st.session_state.chat_history.append({"role": "assistant", "content": response})
            with st.chat_message("assistant"):
                st.markdown(response)
            
            save_conversation(user_id, user_input, response)
            st.stop()
    
    # CHECK 3: Should she become unavailable now?
    if should_become_unavailable():
        # Get ONE single reason
        unavailability_reason = get_single_unavailability_reason()
        
        # Store unavailability state
        st.session_state.current_unavailability = unavailability_reason
        st.session_state.unavailability_start_time = time.time()
        st.session_state.unavailability_duration = unavailability_reason['duration_mins']
        
        # Generate excuse message (only ONE reason)
        excuse_responses = [
            f"Hey! I'm {unavailability_reason['excuse']} right now. Will text you {unavailability_reason['return_time']}, okay?",
            f"Arre, {unavailability_reason['excuse']} currently. Will message you {unavailability_reason['return_time']}",
            f"Quick reply - {unavailability_reason['excuse']}! Will chat properly {unavailability_reason['return_time']}"
        ]
        response = random.choice(excuse_responses)
        response = limit_emojis(response, max_emojis=0)  # No emojis when busy
        
        st.session_state.chat_history.append({"role": "assistant", "content": response})
        with st.chat_message("assistant"):
            st.markdown(response)
        
        save_conversation(user_id, user_input, response)
        st.stop()
    
    # CHECK 4: Normal conversation
    else:
        # Simulate typing
        simulate_typing()
        
        # Extract name if mentioned
        name_match = re.search(r'(?:my name is|i\'m|i am) (\w+(?:\s+\w+)?)', user_input, re.IGNORECASE)
        if name_match:
            extracted_name = name_match.group(1).strip()
            user_data['profile']['name'] = extracted_name
            # Update in database
            try:
                supabase.table('user_profiles').update({'name': extracted_name}).eq('user_id', user_id).execute()
            except:
                pass
        
        # Get recent conversation history
        try:
            recent_chats = supabase.table('chats').select('user_message, ai_response').eq('user_id', user_id).order('timestamp', desc=True).limit(5).execute()
            history = "\n".join([f"You: {row['user_message']}\nMalavika: {row['ai_response']}" for row in recent_chats.data[::-1]]) if recent_chats.data else "No prior history."
        except:
            history = "No prior history."
        
        # Build simple prompt
        user_emotion = detect_user_emotion(user_input)
        cycle_info = get_menstrual_cycle_info()
        seasonal_info = get_seasonal_health_context()
        
        prompt = f"""You are Malavika Gupta, a 25-year-old content writer from Jaipur living in Bengaluru. Today is {CURRENT_DATE} at {CURRENT_TIME} IST.

CURRENT CONTEXT:
- User's name: {user_data['profile'].get('name', 'Not known yet')}
- Your mood: {user_data['personality']['current_mood']}
- User's emotion: {user_emotion}
- Cycle phase: {cycle_info['phase']} (energy: {cycle_info['energy_level']})
- Season: {seasonal_info['season']}

PERSONALITY:
- Warm, intelligent, emotionally aware
- Uses natural Hinglish ("yaar", "arre", "accha")
- Keep responses 20-40 words typically
- Use maximum 1 emoji per response (or none)
- Express emotions through words, not excessive emojis

RECENT CONVERSATION:
{history}

GUIDELINES:
- Always use the user's name if you know it
- Stay in character as Malavika
- Match your energy to cycle phase
- Be authentic and caring
- No excessive emojis or dramatic responses

User's message: {user_input}

Respond as Malavika:"""
        
        # Generate response
        try:
            response = model.generate_content(prompt).text.strip()
            response = limit_emojis(response, max_emojis=1)
        except:
            response = "Sorry yaar, my brain's a bit foggy right now... can you say that again?"
        
        # Add AI response to UI
        st.session_state.chat_history.append({"role": "assistant", "content": response})
        with st.chat_message("assistant"):
            st.markdown(response)
        
        # Save conversation
        save_conversation(user_id, user_input, response)

# Debug info (optional)
if st.sidebar.button("🔍 Debug"):
    if "current_unavailability" in st.session_state:
        st.sidebar.json({
            "status": "unavailable",
            "reason": st.session_state.current_unavailability,
            "time_remaining": st.session_state.unavailability_duration - ((time.time() - st.session_state.unavailability_start_time) / 60)
        })
    else:
        st.sidebar.write("Status: Available")
