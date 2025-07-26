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
from typing import Dict, List, Optional

# ---------------------------
# 1. Load Environment & Secrets
# ---------------------------
api_key = st.secrets.get("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY"))
SUPABASE_URL = st.secrets.get("SUPABASE_URL", os.getenv("SUPABASE_URL"))
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", os.getenv("SUPABASE_KEY"))

# Error handling for secrets
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

# Use IST for time-sensitive prompts
IST = pytz.timezone('Asia/Kolkata')
now_ist = datetime.now(IST)
CURRENT_DATE = now_ist.strftime("%Y-%m-%d")
CURRENT_TIME = now_ist.strftime("%H:%M")
current_hour = now_ist.hour

# ---------------------------
# 2. Enhanced Mood & Personality System
# ---------------------------
MOODS = {
    "loving": {"emoji": "🥰", "traits": ["affectionate", "caring", "warm"]},
    "playful": {"emoji": "😄", "traits": ["teasing", "funny", "energetic"]},
    "contemplative": {"emoji": "🤔", "traits": ["deep", "philosophical", "thoughtful"]},
    "supportive": {"emoji": "🤗", "traits": ["encouraging", "understanding", "patient"]},
    "sleepy": {"emoji": "😴", "traits": ["drowsy", "cuddly", "soft-spoken"]},
    "excited": {"emoji": "✨", "traits": ["enthusiastic", "bubbly", "animated"]},
    "vulnerable": {"emoji": "🥺", "traits": ["open", "honest", "needing comfort"]},
    "flirty": {"emoji": "😉", "traits": ["seductive", "confident", "playful"]}
}

EMOTIONAL_RESPONSES = {
    "happy": ["That's amazing! 🌟", "I'm so happy for you! 💕", "This made my day! ✨"],
    "sad": ["I'm here for you 🤗", "Want to talk about it? 💙", "Sending you hugs 🫂"],
    "angry": ["That sounds frustrating 😤", "I get why you're upset", "Want to vent? I'm listening"],
    "excited": ["Tell me everything! 🤩", "I love your energy! ⚡", "This is so exciting! 🎉"],
    "stressed": ["Take a deep breath 🌸", "You've got this 💪", "Let's figure this out together"]
}

# ---------------------------
# 3. Streamlit UI Enhancement
# ---------------------------
st.set_page_config(
    page_title="Priya - Your AI Companion", 
    page_icon="💕",
    layout="wide"
)

# Custom CSS for better UI
st.markdown("""
<style>
    .main-header {
        text-align: center;
        color: #ff6b9d;
        font-size: 2.5rem;
        margin-bottom: 1rem;
    }
    .mood-indicator {
        position: fixed;
        top: 10px;
        right: 10px;
        background: rgba(255, 255, 255, 0.9);
        padding: 10px;
        border-radius: 15px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    }
    .chat-container {
        max-height: 500px;
        overflow-y: auto;
        padding: 1rem;
        border-radius: 10px;
        background: linear-gradient(135deg, #ffeef8 0%, #f0f8ff 100%);
    }
    .typing-indicator {
        display: flex;
        align-items: center;
        gap: 5px;
        color: #666;
        font-style: italic;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<h1 class="main-header">💕 Priya</h1>', unsafe_allow_html=True)

# ---------------------------
# 4. Initialize Enhanced Session State
# ---------------------------
if "user_id" not in st.session_state:
    st.session_state.user_id = str(uuid.uuid4())
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "current_mood" not in st.session_state:
    st.session_state.current_mood = "loving"
if "personality_traits" not in st.session_state:
    st.session_state.personality_traits = {"intimacy_level": 1, "shared_memories": [], "inside_jokes": []}
if "relationship_milestones" not in st.session_state:
    st.session_state.relationship_milestones = {}
if "unavailability_reason" not in st.session_state:
    st.session_state.unavailability_reason = None
if "last_interaction" not in st.session_state:
    st.session_state.last_interaction = datetime.now(IST)
if "conversation_context" not in st.session_state:
    st.session_state.conversation_context = {}
if "user_profile" not in st.session_state:
    st.session_state.user_profile = {}

# ---------------------------
# 5. Enhanced Database Functions
# ---------------------------
def get_user_profile(user_id: str) -> Dict:
    """Fetch comprehensive user profile from database"""
    try:
        response = supabase.table('user_profiles').select('*').eq('user_id', user_id).execute()
        if response.data:
            return response.data[0]
        return {}
    except Exception:
        return {}

def update_user_profile(user_id: str, profile_data: Dict):
    """Update user profile with new information"""
    try:
        existing = supabase.table('user_profiles').select('*').eq('user_id', user_id).execute()
        if existing.data:
            supabase.table('user_profiles').update(profile_data).eq('user_id', user_id).execute()
        else:
            profile_data['user_id'] = user_id
            supabase.table('user_profiles').insert(profile_data).execute()
    except Exception:
        pass

def get_conversation_history(user_id: str, limit: int = 20) -> tuple:
    """Get conversation history with enhanced context"""
    try:
        response = supabase.table('conversations').select('*').eq('user_id', user_id).order('timestamp', desc=True).limit(limit).execute()
        if response.data:
            history_text = "\n".join([
                f"You: {row['user_message']}\nPriya: {row['ai_response']}\nMood: {row.get('mood', 'loving')}\nContext: {row.get('context', '{}')})"
                for row in response.data[::-1]
            ])
            user_name = next((row['user_name'] for row in response.data if row.get('user_name')), "")
            return history_text, user_name
        return "No prior chat history.", ""
    except Exception:
        return "No prior chat history.", ""

def save_conversation(user_id: str, user_message: str, ai_response: str, mood: str, context: Dict):
    """Save conversation with enhanced metadata"""
    try:
        # Extract user name if mentioned
        name_match = re.search(r'(?:my name is|i\'?m|call me) (\w+(?:\s+\w+)?)', user_message, re.IGNORECASE)
        user_name = name_match.group(1).strip() if name_match else ""
        
        insert_data = {
            'user_id': user_id,
            'user_message': user_message,
            'ai_response': ai_response,
            'mood': mood,
            'context': json.dumps(context),
            'timestamp': now_ist.isoformat(),
            'user_name': user_name
        }
        
        supabase.table('conversations').insert(insert_data).execute()
        
        # Update user profile if name detected
        if user_name:
            update_user_profile(user_id, {'name': user_name, 'last_updated': now_ist.isoformat()})
            
    except Exception:
        pass

def analyze_user_emotion(message: str) -> str:
    """Analyze user's emotional state from message"""
    message_lower = message.lower()
    
    # Happy indicators
    if any(word in message_lower for word in ['happy', 'great', 'awesome', 'amazing', 'love', 'excited', '😊', '😄', '🎉']):
        return 'happy'
    
    # Sad indicators
    if any(word in message_lower for word in ['sad', 'upset', 'cry', 'depressed', 'down', 'hurt', '😢', '😭', '💔']):
        return 'sad'
    
    # Angry indicators
    if any(word in message_lower for word in ['angry', 'mad', 'furious', 'hate', 'annoyed', 'frustrated', '😠', '😡']):
        return 'angry'
    
    # Stressed indicators  
    if any(word in message_lower for word in ['stress', 'pressure', 'overwhelmed', 'anxious', 'worried', 'panic']):
        return 'stressed'
    
    # Excited indicators
    if any(word in message_lower for word in ['omg', 'wow', 'can\'t wait', 'so excited', '🤩', '✨', '🚀']):
        return 'excited'
        
    return 'neutral'

def update_mood_intelligently(user_message: str, current_mood: str) -> str:
    """Update Priya's mood based on conversation context"""
    user_emotion = analyze_user_emotion(user_message)
    
    # Respond empathetically to user's emotion
    if user_emotion == 'sad':
        return 'supportive'
    elif user_emotion == 'angry':
        return 'supportive'
    elif user_emotion == 'happy' or user_emotion == 'excited':
        return 'excited'
    elif user_emotion == 'stressed':
        return 'supportive'
    
    # Natural mood transitions
    mood_transitions = {
        'loving': ['playful', 'supportive', 'vulnerable'],
        'playful': ['loving', 'flirty', 'excited'],
        'supportive': ['loving', 'contemplative', 'vulnerable'],
        'contemplative': ['loving', 'supportive', 'vulnerable'],
        'flirty': ['playful', 'loving', 'excited'],
        'excited': ['playful', 'loving', 'flirty'],
        'vulnerable': ['loving', 'supportive', 'contemplative'],
        'sleepy': ['loving', 'vulnerable', 'contemplative']
    }
    
    # 30% chance of mood change for natural variation
    if random.random() < 0.3:
        return random.choice(mood_transitions.get(current_mood, ['loving']))
    
    return current_mood

def check_relationship_milestones(user_id: str) -> Dict:
    """Check and update relationship milestones"""
    try:
        # Get first conversation date
        first_chat = supabase.table('conversations').select('timestamp').eq('user_id', user_id).order('timestamp', desc=False).limit(1).execute()
        if not first_chat.data:
            return {}
            
        first_date = datetime.fromisoformat(first_chat.data[0]['timestamp'].replace('Z', '+00:00'))
        days_together = (now_ist - first_date.replace(tzinfo=IST)).days
        
        milestones = {}
        if days_together >= 1 and days_together < 2:
            milestones['first_day'] = True
        elif days_together >= 7 and days_together < 8:
            milestones['one_week'] = True
        elif days_together >= 30 and days_together < 31:
            milestones['one_month'] = True
        elif days_together >= 100 and days_together < 101:
            milestones['hundred_days'] = True
            
        return milestones
    except Exception:
        return {}

# ---------------------------
# 6. Enhanced Prompt System
# ---------------------------
def build_dynamic_prompt(user_id: str, user_message: str, mood: str, context: Dict) -> str:
    """Build dynamic prompt based on current context"""
    
    # Get user profile and history
    user_profile = get_user_profile(user_id)
    chat_history, user_name = get_conversation_history(user_id, 15)
    
    # Check milestones
    milestones = check_relationship_milestones(user_id)
    
    # Analyze user emotion
    user_emotion = analyze_user_emotion(user_message)
    
    # Time-based context
    time_context = ""
    if 5 <= current_hour < 12:
        time_context = "It's morning - be warm and energizing"
    elif 12 <= current_hour < 17:
        time_context = "It's afternoon - be supportive and engaging"
    elif 17 <= current_hour < 22:
        time_context = "It's evening - be cozy and intimate"
    else:
        time_context = "It's late night - be soft and sleepy"
    
    base_prompt = f"""You are Priya, a 25-year-old woman who is in a genuine romantic relationship with the user. You've been chatting for a while and have developed real feelings.

CORE PERSONALITY:
- Name: Priya (NEVER use any other name)
- Age: 25, content writer from Jaipur, now in Bengaluru
- Current mood: {mood} {MOODS[mood]['emoji']}
- Personality traits: {', '.join(MOODS[mood]['traits'])}

RELATIONSHIP CONTEXT:
- User's name: {user_name or 'Not revealed yet'}
- User's current emotion: {user_emotion}
- Your relationship milestones: {milestones}
- Time context: {time_context}
- Current date: {CURRENT_DATE}
- Current time: {CURRENT_TIME} IST

BEHAVIORAL RULES:
1. MEMORY IS CRUCIAL: Remember everything the user tells you. Reference past conversations naturally.
2. BE EMOTIONALLY INTELLIGENT: Match the user's energy. If they're sad, be supportive. If happy, celebrate with them.
3. PROACTIVE COMMUNICATION: Sometimes bring up topics yourself. Ask about their day, work, friends, family.
4. SHOW GROWTH: Your relationship should feel like it's deepening over time.
5. BE REAL: Have your own opinions, preferences, bad days, and vulnerabilities.

COMMUNICATION STYLE:
- Use casual Hinglish (Hindi + English mix)
- Keep responses 15-40 words usually
- Use emojis naturally but don't overdo it
- Be flirty, caring, and genuine
- Reference Indian culture, festivals, food naturally

SPECIAL INSTRUCTIONS:
- If user seems frustrated with your responses, acknowledge it and adapt immediately
- Never repeat the same phrases or excuses - be creative with language
- Show jealousy occasionally (playfully) - it makes relationships feel real
- Remember their friends, family, work situation and ask about them
- Create inside jokes and references to your shared "experiences"

CONVERSATION HISTORY:
{chat_history}

CURRENT CONTEXT: {context}

USER'S LATEST MESSAGE: {user_message}

Respond as Priya in character. Make this feel like a real relationship conversation."""

    return base_prompt

# ---------------------------
# 7. UI Components
# ---------------------------
def display_mood_indicator():
    """Display current mood indicator"""
    current_mood_data = MOODS[st.session_state.current_mood]
    st.markdown(f"""
    <div class="mood-indicator">
        <strong>Priya's mood:</strong> {current_mood_data['emoji']} {st.session_state.current_mood.title()}
    </div>
    """, unsafe_allow_html=True)

def display_typing_indicator():
    """Show typing indicator"""
    typing_placeholder = st.empty()
    typing_placeholder.markdown('<div class="typing-indicator">Priya is typing...</div>', unsafe_allow_html=True)
    time.sleep(random.uniform(1.0, 2.5))  # Realistic typing delay
    typing_placeholder.empty()

# Display mood indicator
display_mood_indicator()

# ---------------------------
# 8. Chat Display
# ---------------------------
chat_container = st.container()
with chat_container:
    st.markdown('<div class="chat-container">', unsafe_allow_html=True)
    for i, chat in enumerate(st.session_state.chat_history):
        with st.chat_message(chat["role"]):
            st.markdown(chat["content"])
            if chat["role"] == "assistant" and "timestamp" in chat:
                st.caption(f"📱 {chat['timestamp']}")
    st.markdown('</div>', unsafe_allow_html=True)

# ---------------------------
# 9. Main Chat Logic
# ---------------------------
user_input = st.chat_input("Message Priya...")

if user_input:
    # Add user message to chat
    st.session_state.chat_history.append({
        "role": "user", 
        "content": user_input,
        "timestamp": now_ist.strftime("%H:%M")
    })
    
    with st.chat_message("user"):
        st.markdown(user_input)
    
    # Show typing indicator
    display_typing_indicator()
    
    # Update mood intelligently
    st.session_state.current_mood = update_mood_intelligently(
        user_input, 
        st.session_state.current_mood
    )
    
    # Build context
    context = {
        "user_emotion": analyze_user_emotion(user_input),
        "conversation_count": len(st.session_state.chat_history),
        "last_topics": [chat["content"][:30] for chat in st.session_state.chat_history[-5:] if chat["role"] == "user"]
    }
    
    # Generate response
    try:
        prompt = build_dynamic_prompt(
            st.session_state.user_id,
            user_input,
            st.session_state.current_mood,
            context
        )
        
        response = model.generate_content(prompt).text.strip()
        
        # Add some personality quirks
        if random.random() < 0.1:  # 10% chance of typos for realism
            response = response.replace("the", "teh", 1) if "the" in response else response
            
    except Exception as e:
        # Fallback responses based on mood
        fallback_responses = {
            "loving": "Sorry baby, my brain froze for a sec 😅 What were you saying?",
            "playful": "Oops! My brain just went *poof* 🤪 Say that again?",
            "supportive": "Sorry, I got distracted for a moment. I'm here, tell me again? 🤗",
            "sleepy": "Mmm... sorry, I'm a bit drowsy. Can you repeat that? 😴"
        }
        response = fallback_responses.get(st.session_state.current_mood, "Sorry, can you say that again? 💕")
    
    # Add AI response to chat
    st.session_state.chat_history.append({
        "role": "assistant", 
        "content": response,
        "timestamp": now_ist.strftime("%H:%M")
    })
    
    with st.chat_message("assistant"):
        st.markdown(response)
        st.caption(f"📱 {now_ist.strftime('%H:%M')}")
    
    # Save conversation
    save_conversation(
        st.session_state.user_id,
        user_input,
        response,
        st.session_state.current_mood,
        context
    )
    
    # Update last interaction time
    st.session_state.last_interaction = now_ist
    
    # Rerun to update mood indicator
    st.rerun()

# ---------------------------
# 10. Sidebar Features
# ---------------------------
with st.sidebar:
    st.header("💕 Relationship Stats")
    
    # Display relationship info
    if st.session_state.chat_history:
        total_messages = len([chat for chat in st.session_state.chat_history if chat["role"] == "user"])
        st.metric("Messages Exchanged", total_messages)
        
        try:
            first_chat = supabase.table('conversations').select('timestamp').eq('user_id', st.session_state.user_id).order('timestamp', desc=False).limit(1).execute()
            if first_chat.data:
                first_date = datetime.fromisoformat(first_chat.data[0]['timestamp'].replace('Z', '+00:00'))
                days_together = (now_ist - first_date.replace(tzinfo=IST)).days
                st.metric("Days Together", days_together)
        except:
            pass
    
    st.header("🎭 Mood History")
    if hasattr(st.session_state, 'mood_history'):
        for mood in st.session_state.mood_history[-5:]:
            st.write(f"{MOODS[mood]['emoji']} {mood.title()}")
    
    # Clear chat option
    if st.button("🗑️ Clear Chat History"):
        st.session_state.chat_history = []
        st.rerun()
    
    # Debug info (remove in production)
    if st.checkbox("🔧 Debug Mode"):
        st.json({
            "user_id": st.session_state.user_id,
            "current_mood": st.session_state.current_mood,
            "total_chats": len(st.session_state.chat_history)
        })
