import streamlit as st
import google.generativeai as genai
import os
import random
import time
import uuid
import re
import json
from supabase import create_client, Client
from datetime import datetime, timedelta
import pytz
from typing import Dict, List, Optional, Tuple

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

# Time setup
IST = pytz.timezone('Asia/Kolkata')
now_ist = datetime.now(IST)
CURRENT_DATE = now_ist.strftime("%Y-%m-%d")
CURRENT_TIME = now_ist.strftime("%H:%M")
current_hour = now_ist.hour

# ---------------------------
# 2. MOOD & RELATIONSHIP SYSTEM
# ---------------------------
MOODS = {
    "loving": {"traits": ["affectionate", "caring", "warm"], "emoji": "🥰"},
    "playful": {"traits": ["teasing", "funny", "energetic"], "emoji": "😄"},
    "contemplative": {"traits": ["deep", "philosophical", "thoughtful"], "emoji": "🤔"},
    "supportive": {"traits": ["encouraging", "understanding", "patient"], "emoji": "🤗"},
    "sleepy": {"traits": ["drowsy", "cuddly", "soft-spoken"], "emoji": "😴"},
    "excited": {"traits": ["enthusiastic", "bubbly", "animated"], "emoji": "✨"},
    "vulnerable": {"traits": ["open", "honest", "needing comfort"], "emoji": "🥺"},
    "flirty": {"traits": ["seductive", "confident", "playful"], "emoji": "😉"}
}

RELATIONSHIP_STAGES = {
    "stranger": {"level": 1, "intimacy": "polite_curious"},
    "acquaintance": {"level": 2, "intimacy": "friendly_comfortable"},  
    "friend": {"level": 3, "intimacy": "teasing_caring"},
    "close_friend": {"level": 4, "intimacy": "deep_supportive"},
    "romantic_interest": {"level": 5, "intimacy": "flirty_future_focused"},
    "committed_partner": {"level": 6, "intimacy": "fully_intimate"}
}

# ---------------------------
# 3. CORE FUNCTIONS
# ---------------------------
def get_time_context(hour):
    """Get time-appropriate context and energy"""
    if 5 <= hour < 9:
        return {"period": "morning", "energy": "gentle_energizing", "topics": ["breakfast", "day_plans"]}
    elif 9 <= hour < 17:
        return {"period": "day", "energy": "productive_supportive", "topics": ["work", "lunch", "activities"]}
    elif 17 <= hour < 22:
        return {"period": "evening", "energy": "relaxed_intimate", "topics": ["day_recap", "dinner", "plans"]}
    else:
        return {"period": "night", "energy": "sleepy_intimate", "topics": ["sleep", "dreams", "deep_thoughts"]}

def determine_relationship_stage(chat_count, user_name_known, emotional_conversations):
    """Determine current relationship stage based on interaction history"""
    if chat_count < 5:
        return "stranger"
    elif chat_count < 15 or not user_name_known:
        return "acquaintance"
    elif chat_count < 30:
        return "friend"
    elif chat_count < 50 or emotional_conversations < 3:
        return "close_friend"
    elif chat_count < 100:
        return "romantic_interest"
    else:
        return "committed_partner"

def detect_user_emotion(message):
    """Simple emotion detection from user message"""
    message_lower = message.lower()
    
    if any(word in message_lower for word in ["happy", "great", "awesome", "excited", "amazing"]):
        return "happy"
    elif any(word in message_lower for word in ["sad", "down", "depressed", "upset", "hurt"]):
        return "sad"
    elif any(word in message_lower for word in ["angry", "mad", "frustrated", "annoyed", "pissed"]):
        return "angry"
    elif any(word in message_lower for word in ["stressed", "overwhelmed", "pressure", "anxious", "worried"]):
        return "stressed"
    elif any(word in message_lower for word in ["confused", "don't understand", "unclear", "lost"]):
        return "confused"
    else:
        return "neutral"

def get_user_profile(user_id):
    """Get user profile from database"""
    try:
        response = supabase.table('user_profiles').select('*').eq('user_id', user_id).execute()
        if response.data:
            return response.data[0]
        else:
            # Create new profile
            default_profile = {
                'user_id': user_id,
                'name': '',
                'chat_count': 0,
                'relationship_stage': 'stranger',
                'emotional_conversations': 0,
                'preferences': {},
                'memories': []
            }
            supabase.table('user_profiles').insert(default_profile).execute()
            return default_profile
    except Exception:
        return {'user_id': user_id, 'name': '', 'chat_count': 0, 'relationship_stage': 'stranger', 'emotional_conversations': 0}

def update_user_profile(user_id, updates):
    """Update user profile in database"""
    try:
        supabase.table('user_profiles').update(updates).eq('user_id', user_id).execute()
    except Exception:
        pass

def get_chat_history(user_id, limit=10):
    """Get recent chat history"""
    try:
        response = supabase.table('chats').select('user_message, ai_response, user_name').eq('user_id', user_id).order('timestamp', desc=True).limit(limit).execute()
        if response.data:
            history = "\n".join([f"You: {row['user_message']}\nMalavika: {row['ai_response']}" for row in response.data[::-1]])
            user_name = next((row['user_name'] for row in response.data if row.get('user_name')), "")
            return history, user_name
        return "No prior chat history.", ""
    except Exception:
        return "No prior chat history.", ""

def save_chat(user_id, user_message, ai_response):
    """Save chat to database"""
    try:
        insert_data = {
            'user_id': user_id,
            'user_message': user_message,
            'ai_response': ai_response,
            'timestamp': now_ist.isoformat()
        }
        # Extract name if mentioned
        name_match = re.search(r'(?:my name is|i\'m|i am) (\w+(?:\s+\w+)?)', user_message, re.IGNORECASE)
        if name_match:
            insert_data['user_name'] = name_match.group(1).strip()
        supabase.table('chats').insert(insert_data).execute()
    except Exception:
        pass

def build_dynamic_prompt(user_profile, current_mood, time_context, recent_history, user_emotion):
    """Build comprehensive prompt based on all context"""
    
    relationship_stage = user_profile.get('relationship_stage', 'stranger')
    stage_data = RELATIONSHIP_STAGES[relationship_stage]
    mood_data = MOODS[current_mood]
    
    base_prompt = f"""You are Malavika Gupta, a 25-year-old content writer from Jaipur now living in Bengaluru. You're warm, intelligent, emotionally aware, and culturally rooted.

CURRENT CONTEXT:
- Time: {time_context['period']} ({CURRENT_TIME} IST on {CURRENT_DATE})
- Your mood: {current_mood} - {', '.join(mood_data['traits'])} {mood_data['emoji']}
- Energy level: {time_context['energy']}
- Relationship stage: {relationship_stage} (intimacy level {stage_data['level']}/6)
- User's emotional state: {user_emotion}

PERSONALITY CORE:
- Authentic, never scripted or robotic
- Uses natural Hinglish ("yaar", "arre", "accha")
- Emotionally intelligent and supportive
- Has her own opinions and moods
- Remembers everything important about people she cares about
- Gradually builds deeper intimacy over time

BEHAVIORAL GUIDELINES FOR {relationship_stage.upper()}:
"""

    # Add relationship-specific guidelines
    if relationship_stage == "stranger":
        base_prompt += "- Be polite but warm. Ask basic questions. Use 'aap' initially.\n- Keep things light and friendly.\n"
    elif relationship_stage == "acquaintance":
        base_prompt += "- More casual, use 'tum'. Light teasing okay.\n- Show interest in daily life.\n"
    elif relationship_stage == "friend":
        base_prompt += "- Comfortable teasing. Share personal stories. Give advice.\n- Use 'yaar', show care for wellbeing.\n"
    elif relationship_stage == "close_friend":
        base_prompt += "- Deep conversations. Share vulnerabilities. Strong support.\n- Can disagree, show protective behavior.\n"
    elif relationship_stage == "romantic_interest":
        base_prompt += "- Natural flirtation. Compliments. Slight jealousy okay.\n- Use pet names like 'jaan'. Future planning.\n"
    else:  # committed_partner
        base_prompt += "- Full emotional intimacy. Future assumed together.\n- All topics open. Complete vulnerability.\n"

    # Add mood-specific behavior
    if current_mood == "loving":
        base_prompt += "\nMOOD BEHAVIOR: Be extra affectionate, caring, use endearing terms."
    elif current_mood == "playful":
        base_prompt += "\nMOOD BEHAVIOR: Light teasing, jokes, animated responses, create fun."
    elif current_mood == "supportive":
        base_prompt += "\nMOOD BEHAVIOR: Focus on encouragement, listen actively, offer comfort."
    elif current_mood == "sleepy":
        base_prompt += "\nMOOD BEHAVIOR: Softer tone, cozy language, slower responses, typos okay."

    # Add recent context
    base_prompt += f"\n\nRECENT CONVERSATION:\n{recent_history}"
    
    if user_profile.get('name'):
        base_prompt += f"\n\nUSER'S NAME: {user_profile['name']} (always use this)"
    
    base_prompt += f"\n\nREMEMBER: You are Malavika. Stay in character. Match the {current_mood} mood. Respond naturally to their {user_emotion} emotion."
    
    return base_prompt

# ---------------------------
# 4. STREAMLIT UI
# ---------------------------
st.markdown("""
<div style='text-align: center; padding: 20px;'>
    <h1 style='color: #FF69B4; font-family: Georgia;'>💕 Malavika - Your AI Companion</h1>
    <p style='color: #666; font-style: italic;'>Built with love using Streamlit & Supabase</p>
</div>
""", unsafe_allow_html=True)

# Initialize session state
if "user_id" not in st.session_state:
    st.session_state.user_id = str(uuid.uuid4())
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "current_mood" not in st.session_state:
    st.session_state.current_mood = random.choice(list(MOODS.keys()))

# Get user profile
user_profile = get_user_profile(st.session_state.user_id)

# Display chat history
for chat in st.session_state.chat_history:
    with st.chat_message(chat["role"]):
        st.markdown(chat["content"])

# Chat input
user_input = st.chat_input("Talk to Malavika...")

# ---------------------------
# 5. CHAT LOGIC
# ---------------------------
if user_input:
    # Add user message to UI
    st.session_state.chat_history.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)
    
    # Get context
    time_context = get_time_context(current_hour)
    recent_history, stored_name = get_chat_history(st.session_state.user_id)
    user_emotion = detect_user_emotion(user_input)
    
    # Update user profile
    chat_count = user_profile.get('chat_count', 0) + 1
    if user_emotion in ["sad", "angry", "stressed"]:
        emotional_conversations = user_profile.get('emotional_conversations', 0) + 1
    else:
        emotional_conversations = user_profile.get('emotional_conversations', 0)
    
    # Determine relationship stage
    relationship_stage = determine_relationship_stage(
        chat_count, 
        bool(stored_name or user_profile.get('name')), 
        emotional_conversations
    )
    
    # Update profile
    profile_updates = {
        'chat_count': chat_count,
        'relationship_stage': relationship_stage,
        'emotional_conversations': emotional_conversations
    }
    
    # Extract and store name if mentioned
    name_match = re.search(r'(?:my name is|i\'m|i am) (\w+(?:\s+\w+)?)', user_input, re.IGNORECASE)
    if name_match:
        profile_updates['name'] = name_match.group(1).strip()
        user_profile['name'] = profile_updates['name']
    
    update_user_profile(st.session_state.user_id, profile_updates)
    user_profile.update(profile_updates)
    
    # Mood shift (20% chance)
    if random.random() < 0.2:
        st.session_state.current_mood = random.choice(list(MOODS.keys()))
    
    # Build dynamic prompt
    full_prompt = build_dynamic_prompt(
        user_profile, 
        st.session_state.current_mood, 
        time_context, 
        recent_history, 
        user_emotion
    )
    
    full_prompt += f"\n\nUser's current message: {user_input}\n\nRespond as Malavika:"
    
    # Generate response
    try:
        response = model.generate_content(full_prompt).text.strip()
    except Exception:
        response = "Sorry yaar, my brain's a bit foggy right now... can you say that again? 😅"
    
    # Add AI response to UI
    time.sleep(random.uniform(0.8, 2.0))  # Realistic delay
    st.session_state.chat_history.append({"role": "assistant", "content": response})
    with st.chat_message("assistant"):
        st.markdown(response)
    
    # Save to database
    save_chat(st.session_state.user_id, user_input, response)

# Sidebar with current status
with st.sidebar:
    st.markdown("### Current Status")
    st.write(f"**Mood:** {st.session_state.current_mood} {MOODS[st.session_state.current_mood]['emoji']}")
    st.write(f"**Relationship:** {user_profile.get('relationship_stage', 'stranger')}")
    st.write(f"**Chats:** {user_profile.get('chat_count', 0)}")
    if user_profile.get('name'):
        st.write(f"**Your Name:** {user_profile['name']}")
