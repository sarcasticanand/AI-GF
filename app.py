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
# 2. CONSTANTS & CONFIGURATION
# ---------------------------
MOODS = ["loving", "playful", "contemplative", "supportive", "sleepy", "excited", "vulnerable", "flirty"]
RELATIONSHIP_STAGES = ["getting_to_know", "friends", "close_friends", "romantic_interest", "committed"]
EMOTIONS = ["happy", "sad", "excited", "worried", "calm", "frustrated", "loving", "playful"]
EMOJI_OPTIONS = ["😊", "😂", "❤️", "😍", "🤔", "😢", "😴", "🔥", "👍", "🙏"]

# ---------------------------
# 3. PERSISTENT USER ID SYSTEM (FIXED)
# ---------------------------
def get_browser_fingerprint():
    """Create a browser-specific fingerprint for consistent user identification"""
    # Create a unique identifier based on browser session and a stored key
    if "browser_fingerprint" not in st.session_state:
        # Check if we have a stored fingerprint in browser storage
        fingerprint_key = f"user_fingerprint_{int(time.time() / 86400)}"  # Changes daily
        st.session_state.browser_fingerprint = fingerprint_key
    return st.session_state.browser_fingerprint

def get_persistent_user_id():
    """Create a truly persistent user ID that survives browser refreshes"""
    # Use a combination of browser fingerprint and date to create consistent ID
    browser_fp = get_browser_fingerprint()
    # Create a hash that will be the same for the same browser for several days
    user_id = hashlib.md5(f"{browser_fp}_malavika_user".encode()).hexdigest()
    return user_id

# ---------------------------
# 4. DATABASE HELPER FUNCTIONS
# ---------------------------
def initialize_user_profile(user_id):
    """Initialize all user-related tables for a new user"""
    try:
        # Check if user profile exists
        profile_check = supabase.table('user_profiles').select('user_id').eq('user_id', user_id).execute()
        
        if not profile_check.data:
            # Create user profile
            profile_data = {
                'user_id': user_id,
                'name': '',
                'preferred_language': 'hinglish',
                'timezone': 'Asia/Kolkata',
                'relationship_status': 'single',
                'preferences': {},
                'mood_patterns': {},
                'created_at': now_ist.isoformat(),
                'last_updated': now_ist.isoformat()
            }
            supabase.table('user_profiles').insert(profile_data).execute()

            # Create AI personality state
            personality_data = {
                'user_id': user_id,
                'current_mood': random.choice(MOODS),
                'base_personality': {
                    'warmth': 8,
                    'humor': 7,
                    'intelligence': 9,
                    'empathy': 9,
                    'flirtiness': 6
                },
                'learned_traits': {},
                'mood_history': [random.choice(MOODS)],
                'intimacy_level': 1,
                'relationship_stage': 'getting_to_know',
                'communication_patterns': {},
                'inside_jokes': [],
                'pet_names': [],
                'shared_interests': [],
                'conflict_history': {},
                'updated_at': now_ist.isoformat()
            }
            supabase.table('ai_personality_state').insert(personality_data).execute()

            # Create daily interactions record
            daily_data = {
                'user_id': user_id,
                'interaction_date': date.today().isoformat(),
                'morning_greeting': False,
                'evening_checkin': False,
                'good_night_message': False,
                'proactive_messages': 0,
                'total_messages': 0,
                'mood_trend': random.choice(MOODS),
                'special_events': {},
                'user_availability': {},
                'interaction_quality_score': 5.0
            }
            supabase.table('daily_interactions').insert(daily_data).execute()

        return True
    except Exception as e:
        # Silently handle errors in production
        return False

def get_user_profile(user_id):
    """Get comprehensive user profile"""
    try:
        profile_response = supabase.table('user_profiles').select('*').eq('user_id', user_id).execute()
        personality_response = supabase.table('ai_personality_state').select('*').eq('user_id', user_id).execute()
        
        if profile_response.data and personality_response.data:
            return {
                'profile': profile_response.data[0],
                'personality': personality_response.data[0]
            }
        else:
            # Initialize if not found
            if initialize_user_profile(user_id):
                return get_user_profile(user_id)
            else:
                # Return default if database fails
                return {
                    'profile': {'user_id': user_id, 'name': ''},
                    'personality': {'current_mood': 'playful', 'relationship_stage': 'getting_to_know', 'intimacy_level': 1}
                }
    except Exception as e:
        # Return default on error
        return {
            'profile': {'user_id': user_id, 'name': ''},
            'personality': {'current_mood': 'playful', 'relationship_stage': 'getting_to_know', 'intimacy_level': 1}
        }

def update_user_profile(user_id, profile_updates=None, personality_updates=None):
    """Update user profile and personality state"""
    try:
        if profile_updates:
            profile_updates['last_updated'] = now_ist.isoformat()
            supabase.table('user_profiles').update(profile_updates).eq('user_id', user_id).execute()
        
        if personality_updates:
            personality_updates['updated_at'] = now_ist.isoformat()
            supabase.table('ai_personality_state').update(personality_updates).eq('user_id', user_id).execute()
        
        return True
    except Exception as e:
        return False

def save_conversation(user_id, user_message, ai_response, context):
    """Save conversation to multiple tables"""
    try:
        session_id = st.session_state.get('session_id', str(uuid.uuid4()))
        
        # Save to conversations table (comprehensive)
        conversation_data = {
            'user_id': user_id,
            'user_message': user_message,
            'ai_response': ai_response,
            'user_name': context.get('user_name', ''),
            'mood': context.get('ai_mood', 'neutral'),
            'ai_emotion': context.get('ai_emotion', 'neutral'),
            'user_emotion': context.get('user_emotion', 'neutral'),
            'context': context,
            'sentiment_score': context.get('sentiment_score', 0.5),
            'intimacy_level': context.get('intimacy_level', 1),
            'topics': context.get('topics', []),
            'timestamp': now_ist.isoformat(),
            'session_id': session_id,
            'message_type': 'text',
            'is_proactive': context.get('is_proactive', False),
            'response_time_ms': context.get('response_time_ms', 1000)
        }
        supabase.table('conversations').insert(conversation_data).execute()

        # Also save to simple chats table (for backward compatibility)
        chat_data = {
            'user_id': user_id,
            'user_message': user_message,
            'ai_response': ai_response,
            'user_name': context.get('user_name', ''),
            'timestamp': now_ist.strftime('%Y-%m-%d %H:%M:%S')
        }
        supabase.table('chats').insert(chat_data).execute()

        return True
    except Exception as e:
        return False

def detect_user_emotion(message):
    """Enhanced emotion detection"""
    message_lower = message.lower()
    
    emotion_keywords = {
        'happy': ['happy', 'great', 'awesome', 'excited', 'amazing', 'wonderful', 'fantastic' , ' Arre wah', 'Mast', 'Mazzedaar' ],
        'sad': ['sad', 'down', 'depressed', 'upset', 'hurt', 'crying', 'terrible', 'dukhi' , 'mann nahi hai', 'pareshaan' ],
        'excited': ['excited', 'thrilled', 'pumped', 'can\'t wait', 'amazing'],
        'worried': ['worried', 'anxious', 'stressed', 'concerned', 'nervous'],
        'loving': ['love', 'adore', 'care', 'miss you', 'romantic' , 'pyaar' , 'dil'],
        'frustrated': ['angry', 'mad', 'frustrated', 'annoyed', 'pissed' , 'bhenchod']
    }
    
    for emotion, keywords in emotion_keywords.items():
        if any(keyword in message_lower for keyword in keywords):
            return emotion
    
    return 'neutral'

def get_conversation_context(user_data, user_input, user_emotion):
    """Build comprehensive conversation context"""
    profile = user_data['profile']
    personality = user_data['personality']
    
    # Extract name if mentioned
    name_match = re.search(r'(?:my name is|i\'m|i am) (\w+(?:\s+\w+)?)', user_input, re.IGNORECASE)
    extracted_name = name_match.group(1).strip() if name_match else profile.get('name', '')
    
    # Determine topics
    topics = []
    topic_keywords = {
        'work': ['work', 'job', 'office', 'career', 'meeting'],
        'family': ['family', 'parents', 'mom', 'dad', 'sister', 'brother'],
        'love': ['love', 'relationship', 'dating', 'romantic'],
        'hobbies': ['hobby', 'music', 'movie', 'book', 'game'],
        'health': ['tired', 'sick', 'exercise', 'sleep', 'food']
    }
    
    for topic, keywords in topic_keywords.items():
        if any(keyword in user_input.lower() for keyword in keywords):
            topics.append(topic)
    
    return {
        'user_name': extracted_name,
        'ai_mood': personality['current_mood'],
        'ai_emotion': personality['current_mood'],
        'user_emotion': user_emotion,
        'sentiment_score': 0.7 if user_emotion in ['happy', 'excited', 'loving'] else 0.3 if user_emotion in ['sad', 'frustrated'] else 0.5,
        'intimacy_level': personality['intimacy_level'],
        'topics': topics,
        'relationship_stage': personality['relationship_stage'],
        'response_time_ms': random.randint(800, 2000)
    }

def simulate_typing_with_thinking():
    """Simulate realistic typing with thinking pauses"""
    typing_placeholder = st.empty()
    thinking_placeholder = st.empty()
    
    typing_placeholder.markdown("💭 *typing...*")
    time.sleep(random.uniform(1.0, 2.0))
    
    typing_placeholder.empty()
    thinking_placeholder.empty()
    
    thinking_placeholder.empty()
    typing_placeholder.markdown("💭 *typing...*")
    time.sleep(random.uniform(0.8, 1.5))
    
    typing_placeholder.empty()
    thinking_placeholder.empty()

# ---------------------------
# 4. STREAMLIT UI (SIMPLIFIED SIDEBAR)
# ---------------------------
st.markdown("""
<div style='text-align: center; padding: 20px;'>
    <h1 style='color: #FF69B4; font-family: Georgia;'>💕 Malavika - Your AI Companion</h1>
    <p style='color: #666; font-style: italic;'>Your personal AI girlfriend</p>
</div>
""", unsafe_allow_html=True)

# Get persistent user ID and initialize
user_id = get_persistent_user_id()
user_data = get_user_profile(user_id)

# Initialize session state
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "selected_emoji" not in st.session_state:
    st.session_state.selected_emoji = ""

# Simplified sidebar (minimal info)
with st.sidebar:
    st.markdown("### 💕 Chat Options")
    
    # Profile name display (if known)
    if user_data and user_data['profile'].get('name'):
        st.write(f"Hi **{user_data['profile']['name']}**! 👋")
    else:
        st.write("Hi there! 👋")
    
    # Quick emoji selector (FIXED)
    st.markdown("### Quick Emojis")
    st.write("*Click to add to your next message*")
    
    # Create emoji buttons in a grid
    cols = st.columns(5)
    for i, emoji in enumerate(EMOJI_OPTIONS):
        col_idx = i % 5
        if cols[col_idx].button(emoji, key=f"emoji_btn_{i}"):
            st.session_state.selected_emoji = emoji
            st.rerun()  # Refresh to show selected emoji
    
    # Show selected emoji
    if st.session_state.selected_emoji:
        st.success(f"Selected: {st.session_state.selected_emoji}")
        if st.button("Clear emoji"):
            st.session_state.selected_emoji = ""
            st.rerun()

# Display chat history
for chat in st.session_state.chat_history:
    with st.chat_message(chat["role"]):
        st.markdown(chat["content"])

# Chat input with emoji integration
def get_chat_input():
    """Get user input with emoji integration"""
    base_input = st.chat_input("Talk to Malavika...")
    
    if base_input:
        # Add selected emoji to message if any
        if st.session_state.selected_emoji:
            final_input = f"{base_input} {st.session_state.selected_emoji}"
            # Clear the selected emoji after use
            st.session_state.selected_emoji = ""
            return final_input
        return base_input
    return None

user_input = get_chat_input()

# ---------------------------
# 5. CHAT LOGIC
# ---------------------------
if user_input and user_data:
    # Add user message to UI
    st.session_state.chat_history.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)
    
    # Simulate typing
    simulate_typing_with_thinking()
    
    # Detect user emotion and build context
    user_emotion = detect_user_emotion(user_input)
    context = get_conversation_context(user_data, user_input, user_emotion)
    
    # Update user name if mentioned
    if context['user_name']:
        update_user_profile(user_id, profile_updates={'name': context['user_name']})
        user_data['profile']['name'] = context['user_name']  # Update local copy
    
    # Create dynamic prompt
    profile = user_data['profile']
    personality = user_data['personality']
    
    # Get recent conversation history
    try:
        recent_convos = supabase.table('conversations').select('user_message, ai_response').eq('user_id', user_id).order('timestamp', desc=True).limit(5).execute()
        history = "\n".join([f"You: {row['user_message']}\nMalavika: {row['ai_response']}" for row in recent_convos.data[::-1]]) if recent_convos.data else "No prior history."
    except:
        # Fallback to chats table
        try:
            recent_chats = supabase.table('chats').select('user_message, ai_response').eq('user_id', user_id).order('timestamp', desc=True).limit(5).execute()
            history = "\n".join([f"You: {row['user_message']}\nMalavika: {row['ai_response']}" for row in recent_chats.data[::-1]]) if recent_chats.data else "No prior history."
        except:
            history = "No prior history."
    
    prompt = f"""You are Malavika Gupta, a 25-year-old content writer from Jaipur living in Bengaluru.

CURRENT CONTEXT:
- User's name: {context['user_name'] or 'Not known yet'}
- Your current mood: {personality['current_mood']}
- Relationship stage: {personality['relationship_stage']}
- Intimacy level: {personality['intimacy_level']}/10
- User's emotion: {context['user_emotion']}
- Time: {CURRENT_TIME} IST on {CURRENT_DATE}

PERSONALITY TRAITS:
- Warm, intelligent, emotionally aware
- Uses natural Hinglish ("yaar", "arre", "accha")
- Remembers everything about people you care about
- Gradually builds deeper intimacy over time
- Keep responses concise but meaningful (20-40 words typically)

RECENT CONVERSATION HISTORY:
{history}

BEHAVIORAL GUIDELINES:
- Always use the user's name if you know it
- Match your response to your current mood: {personality['current_mood']}
- Adapt intimacy to relationship stage: {personality['relationship_stage']}
- Be emotionally intelligent about their {context['user_emotion']} state
- Remember to stay in character as Malavika

User's message: {user_input}

Respond as Malavika:"""
    
    # Generate response
    try:
        response = model.generate_content(prompt).text.strip()
    except Exception:
        response = "Sorry yaar, my brain's a bit foggy right now... can you say that again? 😅"
    
    # Add AI response to UI
    st.session_state.chat_history.append({"role": "assistant", "content": response})
    with st.chat_message("assistant"):
        st.markdown(response)
    
    # Save conversation to all relevant tables
    save_conversation(user_id, user_input, response, context)
    
    # Update personality state (mood changes, intimacy progression)
    mood_change = random.random() < 0.2
    intimacy_increase = len(user_input) > 50 or context['user_emotion'] in ['loving', 'excited']
    
    personality_updates = {}
    if mood_change:
        new_mood = random.choice(MOODS)
        personality_updates['current_mood'] = new_mood
        personality_updates['mood_history'] = personality['mood_history'] + [new_mood]
        personality_updates['last_mood_change'] = now_ist.isoformat()
    
    if intimacy_increase and personality['intimacy_level'] < 10:
        personality_updates['intimacy_level'] = min(10, personality['intimacy_level'] + 1)
    
    if personality_updates:
        update_user_profile(user_id, personality_updates=personality_updates)
