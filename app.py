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
# 3. DATABASE HELPER FUNCTIONS
# ---------------------------
def get_persistent_user_id():
    """Create a persistent user ID based on browser session"""
    if "persistent_user_id" not in st.session_state:
        browser_id = str(uuid.uuid4())
        st.session_state.persistent_user_id = browser_id
    return st.session_state.persistent_user_id

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
        st.error(f"Error initializing user: {e}")
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
            initialize_user_profile(user_id)
            return get_user_profile(user_id)
    except Exception as e:
        st.error(f"Error getting profile: {e}")
        return None

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
        st.error(f"Error updating profile: {e}")
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

        # Update daily interactions
        update_daily_interactions(user_id)
        
        return True
    except Exception as e:
        st.error(f"Error saving conversation: {e}")
        return False

def update_daily_interactions(user_id):
    """Update daily interaction statistics"""
    try:
        today = date.today().isoformat()
        
        # Check if record exists for today
        daily_check = supabase.table('daily_interactions').select('*').eq('user_id', user_id).eq('interaction_date', today).execute()
        
        if daily_check.data:
            # Update existing record
            current_total = daily_check.data[0]['total_messages']
            supabase.table('daily_interactions').update({
                'total_messages': current_total + 1,
                'interaction_quality_score': min(10.0, daily_check.data[0]['interaction_quality_score'] + 0.1)
            }).eq('user_id', user_id).eq('interaction_date', today).execute()
        else:
            # Create new daily record
            daily_data = {
                'user_id': user_id,
                'interaction_date': today,
                'total_messages': 1,
                'interaction_quality_score': 5.0
            }
            supabase.table('daily_interactions').insert(daily_data).execute()
    except Exception as e:
        st.error(f"Error updating daily interactions: {e}")

def detect_user_emotion(message):
    """Enhanced emotion detection"""
    message_lower = message.lower()
    
    emotion_keywords = {
        'happy': ['happy', 'great', 'awesome', 'excited', 'amazing', 'wonderful', 'fantastic'],
        'sad': ['sad', 'down', 'depressed', 'upset', 'hurt', 'crying', 'terrible'],
        'excited': ['excited', 'thrilled', 'pumped', 'can\'t wait', 'amazing'],
        'worried': ['worried', 'anxious', 'stressed', 'concerned', 'nervous'],
        'loving': ['love', 'adore', 'care', 'miss you', 'romantic'],
        'frustrated': ['angry', 'mad', 'frustrated', 'annoyed', 'pissed']
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

def create_shared_memory(user_id, title, description, memory_type='conversation', emotional_weight=5):
    """Create a shared memory"""
    try:
        memory_data = {
            'user_id': user_id,
            'memory_title': title,
            'memory_description': description,
            'memory_type': memory_type,
            'emotional_weight': emotional_weight,
            'tags': [],
            'created_date': now_ist.isoformat(),
            'last_referenced': now_ist.isoformat(),
            'reference_count': 1,
            'is_inside_joke': False
        }
        supabase.table('shared_memories').insert(memory_data).execute()
        return True
    except Exception as e:
        st.error(f"Error creating memory: {e}")
        return False

def simulate_typing_with_thinking():
    """Simulate realistic typing with thinking pauses"""
    typing_placeholder = st.empty()
    thinking_placeholder = st.empty()
    
    typing_placeholder.markdown("💭 *typing...*")
    time.sleep(random.uniform(1.0, 2.0))
    
    typing_placeholder.empty()
    thinking_placeholder.markdown("🤔 *thinking...*")
    time.sleep(random.uniform(1.5, 2.5))
    
    thinking_placeholder.empty()
    typing_placeholder.markdown("💭 *typing...*")
    time.sleep(random.uniform(0.8, 1.5))
    
    typing_placeholder.empty()
    thinking_placeholder.empty()

# ---------------------------
# 4. STREAMLIT UI
# ---------------------------
st.markdown("""
<div style='text-align: center; padding: 20px;'>
    <h1 style='color: #FF69B4; font-family: Georgia;'>💕 Malavika - Your AI Companion</h1>
    <p style='color: #666; font-style: italic;'>Advanced AI with Complete Memory System</p>
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

# Sidebar for user info and debugging
with st.sidebar:
    st.markdown("### Your Profile")
    
    if user_data:
        profile = user_data['profile']
        personality = user_data['personality']
        
        # Display current status
        st.write(f"**Name:** {profile.get('name', 'Not set')}")
        st.write(f"**Relationship:** {personality.get('relationship_stage', 'getting_to_know')}")
        st.write(f"**Intimacy Level:** {personality.get('intimacy_level', 1)}/10")
        st.write(f"**Current Mood:** {personality.get('current_mood', 'neutral')}")
        
        # Quick stats
        st.markdown("### Today's Stats")
        try:
            today_stats = supabase.table('daily_interactions').select('*').eq('user_id', user_id).eq('interaction_date', date.today().isoformat()).execute()
            if today_stats.data:
                stats = today_stats.data[0]
                st.write(f"**Messages:** {stats.get('total_messages', 0)}")
                st.write(f"**Quality Score:** {stats.get('interaction_quality_score', 5.0):.1f}/10")
        except:
            st.write("**Messages:** 0")
    
    # Quick emoji selector
    st.markdown("### Quick Emojis")
    emoji_cols = st.columns(5)
    for i, emoji in enumerate(EMOJI_OPTIONS):
        if emoji_cols[i % 5].button(emoji):
            st.session_state.quick_emoji = emoji
    
    # Debug info
    st.markdown("### Debug Info")
    st.write(f"**User ID:** {user_id[:8]}...")
    st.write(f"**Session:** {st.session_state.session_id[:8]}...")

# Display chat history
for chat in st.session_state.chat_history:
    with st.chat_message(chat["role"]):
        st.markdown(chat["content"])

# Chat input
user_input = st.chat_input("Talk to Malavika...")

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
    
    # Create dynamic prompt
    profile = user_data['profile']
    personality = user_data['personality']
    
    # Get recent conversation history
    try:
        recent_convos = supabase.table('conversations').select('user_message, ai_response').eq('user_id', user_id).order('timestamp', desc=True).limit(5).execute()
        history = "\n".join([f"You: {row['user_message']}\nMalavika: {row['ai_response']}" for row in recent_convos.data[::-1]]) if recent_convos.data else "No prior history."
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
    
    # Create shared memory for meaningful interactions
    if context['user_emotion'] in ['loving', 'excited'] or len(user_input) > 100:
        create_shared_memory(
            user_id, 
            f"Conversation on {CURRENT_DATE}", 
            f"User said: {user_input[:100]}... AI responded with care and understanding.",
            'conversation',
            7 if context['user_emotion'] == 'loving' else 5
        )
    
    # Clear quick emoji
    if hasattr(st.session_state, 'quick_emoji'):
        del st.session_state.quick_emoji

# Display current database status
if st.sidebar.button("Show Database Status"):
    st.sidebar.markdown("### Database Status")
    tables_to_check = ['user_profiles', 'ai_personality_state', 'conversations', 'daily_interactions', 'shared_memories']
    for table in tables_to_check:
        try:
            count = supabase.table(table).select('id', count='exact').execute()
            st.sidebar.write(f"**{table}:** {count.count} records")
        except:
            st.sidebar.write(f"**{table}:** Error")
