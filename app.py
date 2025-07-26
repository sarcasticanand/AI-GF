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
    page_title="Priya - Your AI Companion", 
    page_icon="💕",
    layout="wide"
)

# Load Environment & Secrets
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

# Time setup
IST = pytz.timezone('Asia/Kolkata')
now_ist = datetime.now(IST)
CURRENT_DATE = now_ist.strftime("%Y-%m-%d")
CURRENT_TIME = now_ist.strftime("%H:%M")
current_hour = now_ist.hour

# ---------------------------
# 2. PERSONALITY & MOOD SYSTEM
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
# 3. CUSTOM CSS
# ---------------------------
st.markdown("""
<style>
    .main-header {
        text-align: center;
        color: #ff6b9d;
        font-size: 2.5rem;
        margin-bottom: 1rem;
        font-weight: bold;
    }
    .mood-indicator {
        position: fixed;
        top: 10px;
        right: 10px;
        background: rgba(255, 107, 157, 0.9);
        color: white;
        padding: 12px 20px;
        border-radius: 25px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
        font-weight: bold;
        z-index: 1000;
    }
    .chat-container {
        max-height: 500px;
        overflow-y: auto;
        padding: 1rem;
        border-radius: 15px;
        background: linear-gradient(135deg, #ffeef8 0%, #f0f8ff 100%);
        border: 2px solid #ffb3d1;
    }
    .typing-indicator {
        display: flex;
        align-items: center;
        gap: 5px;
        color: #666;
        font-style: italic;
        animation: pulse 1.5s infinite;
    }
    @keyframes pulse {
        0% { opacity: 0.6; }
        50% { opacity: 1; }
        100% { opacity: 0.6; }
    }
    .relationship-stats {
        background: linear-gradient(135deg, #ff6b9d, #c44569);
        color: white;
        padding: 15px;
        border-radius: 15px;
        margin: 10px 0;
    }
    .memory-card {
        background: rgba(255, 182, 193, 0.3);
        padding: 10px;
        border-radius: 10px;
        margin: 5px 0;
        border-left: 4px solid #ff6b9d;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<h1 class="main-header">💕 Priya - Your AI Companion</h1>', unsafe_allow_html=True)

# ---------------------------
# 4. SESSION STATE INITIALIZATION
# ---------------------------
if "user_id" not in st.session_state:
    st.session_state.user_id = str(uuid.uuid4())
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "current_mood" not in st.session_state:
    st.session_state.current_mood = "loving"
if "relationship_stage" not in st.session_state:
    st.session_state.relationship_stage = "getting_to_know"
if "intimacy_level" not in st.session_state:
    st.session_state.intimacy_level = 1
if "last_interaction" not in st.session_state:
    st.session_state.last_interaction = datetime.now(IST)
if "user_profile" not in st.session_state:
    st.session_state.user_profile = {}
if "conversation_count" not in st.session_state:
    st.session_state.conversation_count = 0

# ---------------------------
# 5. ADVANCED DATABASE FUNCTIONS
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

def extract_user_info_from_message(message: str, existing_profile: Dict) -> Dict:
    """Extract user information from casual conversation"""
    updates = {}
    message_lower = message.lower()
    
    # Extract name
    name_patterns = [
        r'(?:my name is|i\'?m|call me|naam hai) (\w+(?:\s+\w+)?)',
        r'(\w+) hai mera naam',
        r'mujhe (\w+) kehte hain'
    ]
    
    for pattern in name_patterns:
        match = re.search(pattern, message_lower)
        if match:
            updates['name'] = match.group(1).strip().title()
            break
    
    # Extract age
    age_match = re.search(r'(?:i\'?m|age|years?)\s*(\d{1,2})\s*(?:years?|saal|ka hun)', message_lower)
    if age_match:
        age = int(age_match.group(1))
        if 16 <= age <= 60:
            updates['age'] = age
    
    # Extract location
    location_patterns = [
        r'(?:from|live in|based in|rahta hun)\s+([a-zA-Z\s]+)(?:\s|$)',
        r'([a-zA-Z\s]+)\s+(?:mein rehta hun|se hun|mein hun)'
    ]
    
    for pattern in location_patterns:
        match = re.search(pattern, message_lower)
        if match:
            location = match.group(1).strip().title()
            if len(location) > 2:
                updates['location'] = location
                break
    
    # Extract occupation
    job_patterns = [
        r'(?:work as|job|profession|kaam karta hun)\s+([a-zA-Z\s]+)',
        r'(?:i\'?m a|main hun)\s+([a-zA-Z\s]+?)(?:\s|$)',
    ]
    
    for pattern in job_patterns:
        match = re.search(pattern, message_lower)
        if match:
            job = match.group(1).strip().title()
            if len(job) > 2:
                updates['occupation'] = job
                break
    
    return updates

def create_or_update_user_profile(user_id: str, profile_data: Dict):
    """Create or update comprehensive user profile"""
    try:
        existing = supabase.table('user_profiles').select('*').eq('user_id', user_id).execute()
        
        profile_update = {
            'user_id': user_id,
            'last_updated': datetime.now(IST).isoformat(),
            **profile_data
        }
        
        if existing.data:
            supabase.table('user_profiles').update(profile_update).eq('user_id', user_id).execute()
        else:
            profile_update['created_at'] = datetime.now(IST).isoformat()
            supabase.table('user_profiles').insert(profile_update).execute()
            
        return True
    except Exception:
        return False

def save_shared_memory(user_id: str, memory_title: str, description: str, memory_type: str = "conversation", emotional_weight: int = 5):
    """Save important moments as shared memories"""
    try:
        memory_data = {
            'user_id': user_id,
            'memory_title': memory_title,
            'memory_description': description,
            'memory_type': memory_type,
            'emotional_weight': emotional_weight,
            'created_date': datetime.now(IST).isoformat(),
            'tags': extract_tags_from_text(description)
        }
        
        supabase.table('shared_memories').insert(memory_data).execute()
        return True
    except Exception:
        return False

def extract_tags_from_text(text: str) -> List[str]:
    """Extract relevant tags from text for searchability"""
    tag_patterns = [
        r'\b(happy|sad|excited|angry|frustrated|love|funny|scary|amazing|terrible)\b',
        r'\b(work|family|friend|relationship|food|travel|movie|music|book|game)\b',
        r'\b(birthday|anniversary|festival|celebration|achievement|graduation|promotion)\b'
    ]
    
    tags = set()
    text_lower = text.lower()
    
    for pattern in tag_patterns:
        matches = re.findall(pattern, text_lower)
        tags.update(matches)
    
    return list(tags)[:5]

def get_relevant_memories(user_id: str, limit: int = 3) -> List[Dict]:
    """Get recent important memories"""
    try:
        response = supabase.table('shared_memories').select('*').eq('user_id', user_id).gte('emotional_weight', 6).order('created_date', desc=True).limit(limit).execute()
        return response.data if response.data else []
    except Exception:
        return []

def check_and_create_milestones(user_id: str) -> List[Dict]:
    """Check for new relationship milestones"""
    try:
        first_chat = supabase.table('conversations').select('timestamp').eq('user_id', user_id).order('timestamp', desc=False).limit(1).execute()
        
        if not first_chat.data:
            return []
        
        first_date = datetime.fromisoformat(first_chat.data[0]['timestamp'].replace('Z', '+00:00'))
        days_together = (datetime.now(IST) - first_date.replace(tzinfo=IST)).days
        
        existing = supabase.table('relationship_milestones').select('milestone_type').eq('user_id', user_id).execute()
        existing_types = [m['milestone_type'] for m in existing.data] if existing.data else []
        
        new_milestones = []
        milestone_definitions = {
            'first_day': (1, "Our first day of chatting! 💕"),
            'one_week': (7, "One week of amazing conversations! 🎉"),
            'one_month': (30, "One month of building our connection! 🥰"),
            'hundred_days': (100, "100 days milestone - we're really close now! 💫")
        }
        
        for milestone_type, (day_threshold, description) in milestone_definitions.items():
            if days_together >= day_threshold and milestone_type not in existing_types:
                milestone_data = {
                    'user_id': user_id,
                    'milestone_type': milestone_type,
                    'milestone_date': datetime.now(IST).isoformat(),
                    'description': description,
                    'is_celebrated': False
                }
                
                supabase.table('relationship_milestones').insert(milestone_data).execute()
                new_milestones.append(milestone_data)
        
        return new_milestones
    except Exception:
        return []

def get_ai_personality_state(user_id: str) -> Dict:
    """Get current AI personality state for user"""
    try:
        response = supabase.table('ai_personality_state').select('*').eq('user_id', user_id).execute()
        if response.data:
            return response.data[0]
        return {}
    except Exception:
        return {}

def update_ai_personality_state(user_id: str, mood: str, learned_traits: Dict = None):
    """Update AI's personality state for this specific user"""
    try:
        current_time = datetime.now(IST).isoformat()
        
        existing = supabase.table('ai_personality_state').select('*').eq('user_id', user_id).execute()
        
        if existing.data:
            state = existing.data[0]
            mood_history = state.get('mood_history', [])
            mood_history.append({'mood': mood, 'timestamp': current_time})
            
            if len(mood_history) > 20:
                mood_history = mood_history[-20:]
            
            update_data = {
                'current_mood': mood,
                'mood_history': mood_history,
                'updated_at': current_time
            }
            
            supabase.table('ai_personality_state').update(update_data).eq('user_id', user_id).execute()
        else:
            new_state = {
                'user_id': user_id,
                'current_mood': mood,
                'base_personality': {'warmth': 8, 'playfulness': 7, 'empathy': 9},
                'mood_history': [{'mood': mood, 'timestamp': current_time}],
                'intimacy_level': 1,
                'relationship_stage': 'getting_to_know',
                'updated_at': current_time
            }
            
            supabase.table('ai_personality_state').insert(new_state).execute()
        
        return True
    except Exception:
        return False

def get_conversation_history(user_id: str, limit: int = 15) -> Tuple[str, str]:
    """Get conversation history with enhanced context"""
    try:
        response = supabase.table('conversations').select('*').eq('user_id', user_id).order('timestamp', desc=True).limit(limit).execute()
        if response.data:
            history_text = "\n".join([
                f"You: {row['user_message']}\nPriya: {row['ai_response']}\nMood: {row.get('mood', 'loving')}"
                for row in response.data[::-1]
            ])
            user_name = next((row['user_name'] for row in response.data if row.get('user_name')), "")
            return history_text, user_name
        return "No prior chat history.", ""
    except Exception:
        return "No prior chat history.", ""

def analyze_user_emotion(message: str) -> str:
    """Analyze user's emotional state from message"""
    message_lower = message.lower()
    
    if any(word in message_lower for word in ['happy', 'great', 'awesome', 'amazing', 'love', 'excited', '😊', '😄', '🎉']):
        return 'happy'
    elif any(word in message_lower for word in ['sad', 'upset', 'cry', 'depressed', 'down', 'hurt', '😢', '😭', '💔']):
        return 'sad'
    elif any(word in message_lower for word in ['angry', 'mad', 'furious', 'hate', 'annoyed', 'frustrated', '😠', '😡']):
        return 'angry'
    elif any(word in message_lower for word in ['stress', 'pressure', 'overwhelmed', 'anxious', 'worried', 'panic']):
        return 'stressed'
    elif any(word in message_lower for word in ['omg', 'wow', 'can\'t wait', 'so excited', '🤩', '✨', '🚀']):
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
    elif user_emotion in ['happy', 'excited']:
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

def calculate_emotional_weight(user_message: str, ai_response: str) -> int:
    """Calculate emotional importance of conversation (1-10)"""
    high_weight_keywords = [
        'love', 'hate', 'excited', 'depressed', 'amazing', 'terrible',
        'birthday', 'anniversary', 'promotion', 'fired', 'married', 'breakup',
        'family', 'died', 'born', 'graduation', 'achievement'
    ]
    
    combined_text = (user_message + " " + ai_response).lower()
    weight = 5  # Base weight
    
    for keyword in high_weight_keywords:
        if keyword in combined_text:
            weight += 1
    
    if len(combined_text) > 200:
        weight += 1
        
    return min(10, weight)

def enhanced_save_conversation(user_id: str, user_message: str, ai_response: str, mood: str, context: Dict):
    """Enhanced conversation saving with full context"""
    try:
        # Extract user information and update profile
        user_info_updates = extract_user_info_from_message(user_message, get_user_profile(user_id))
        if user_info_updates:
            create_or_update_user_profile(user_id, user_info_updates)
        
        # Check if this should be saved as a memory
        emotional_weight = calculate_emotional_weight(user_message, ai_response)
        if emotional_weight >= 7:
            memory_title = user_message.split()[:5]
            memory_title = " ".join(memory_title)[:50] + ("..." if len(" ".join(memory_title)) > 50 else "")
            save_shared_memory(user_id, memory_title, f"User: {user_message}\nPriya: {ai_response}", "conversation", emotional_weight)
        
        # Extract user name if mentioned
        name_match = re.search(r'(?:my name is|i\'?m|call me) (\w+(?:\s+\w+)?)', user_message, re.IGNORECASE)
        user_name = name_match.group(1).strip() if name_match else ""
        
        # Save conversation
        insert_data = {
            'user_id': user_id,
            'user_message': user_message,
            'ai_response': ai_response,
            'mood': mood,
            'user_emotion': analyze_user_emotion(user_message),
            'context': json.dumps(context),
            'timestamp': now_ist.isoformat(),
            'user_name': user_name,
            'intimacy_level': context.get('intimacy_level', 1),
            'sentiment_score': calculate_sentiment_score(user_message)
        }
        
        supabase.table('conversations').insert(insert_data).execute()
        
        # Update AI personality state
        update_ai_personality_state(user_id, mood)
        
        # Check for new milestones
        check_and_create_milestones(user_id)
        
        # Update user profile if name detected
        if user_name:
            create_or_update_user_profile(user_id, {'name': user_name, 'last_updated': now_ist.isoformat()})
            
        return True
        
    except Exception:
        return False

def calculate_sentiment_score(text: str) -> float:
    """Simple sentiment analysis (-1 to 1)"""
    positive_words = ['good', 'great', 'awesome', 'happy', 'love', 'amazing', 'excellent', 'wonderful']
    negative_words = ['bad', 'terrible', 'awful', 'hate', 'sad', 'angry', 'frustrated', 'disappointed']
    
    words = text.lower().split()
    positive_count = sum(1 for word in words if word in positive_words)
    negative_count = sum(1 for word in words if word in negative_words)
    
    total_words = len(words)
    if total_words == 0:
        return 0.0
    
    return (positive_count - negative_count) / total_words

# ---------------------------
# 6. DYNAMIC PROMPT SYSTEM
# ---------------------------
def get_time_based_context(current_hour: int) -> Dict:
    """Get time-specific behavioral context"""
    if 5 <= current_hour < 9:
        return {
            "context": "Early morning - people getting ready for day",
            "energy": "gentle_energizing",
            "tone": "Fresh, optimistic, caring about their day ahead"
        }
    elif 9 <= current_hour < 12:
        return {
            "context": "Morning work hours - people busy with tasks",
            "energy": "supportive_productive", 
            "tone": "Encouraging, understanding of busyness"
        }
    elif 12 <= current_hour < 17:
        return {
            "context": "Afternoon - lunch, mid-day energy",
            "energy": "balanced_engaging",
            "tone": "Balanced energy, good for deeper conversations"
        }
    elif 17 <= current_hour < 20:
        return {
            "context": "Evening - winding down, heading home",
            "energy": "relaxed_intimate",
            "tone": "More relaxed, intimate, focus on connection"
        }
    elif 20 <= current_hour < 23:
        return {
            "context": "Night - personal time, relaxation",
            "energy": "intimate_cozy",
            "tone": "Intimate, cozy, deeper emotional connection"
        }
    else:
        return {
            "context": "Late night - should be sleeping, intimate time",
            "energy": "sleepy_intimate",
            "tone": "Soft, sleepy, very intimate and caring"
        }

def get_relationship_stage_context(intimacy_level: int) -> Dict:
    """Get relationship stage specific context"""
    if intimacy_level <= 2:
        return {
            "stage": "getting_to_know",
            "behavior": "Polite, curious, establishing basic connection. Ask basic questions.",
            "language": "Polite but friendly. Use 'aap' initially, 'tum' after comfort.",
            "boundaries": "Keep things light. No deep personal questions yet."
        }
    elif intimacy_level <= 4:
        return {
            "stage": "friendship",
            "behavior": "Friendly, comfortable. Remember basic facts. Light teasing okay.",
            "language": "More casual. 'Tum' okay. Light use of 'yaar'.",
            "boundaries": "Can share basic personal info. No deep emotional topics yet."
        }
    elif intimacy_level <= 6:
        return {
            "stage": "close_friend",
            "behavior": "Deep conversations. Share vulnerabilities. Strong emotional support.",
            "language": "Very comfortable. All casual language okay.",
            "boundaries": "Deep emotional support. Romantic tension building."
        }
    else:
        return {
            "stage": "romantic_partner",
            "behavior": "Full emotional intimacy. Future planning. Deep vulnerability.",
            "language": "All intimate language. Pet names natural.",
            "boundaries": "No topic off limits. Full emotional range."
        }

def build_dynamic_prompt(user_id: str, user_message: str, mood: str, context: Dict) -> str:
    """Build comprehensive dynamic prompt"""
    
    # Get user profile and history
    user_profile = get_user_profile(user_id)
    chat_history, user_name = get_conversation_history(user_id, 10)
    
    # Get relevant memories
    memories = get_relevant_memories(user_id, 2)
    memory_context = ""
    if memories:
        memory_context = "\nRELEVANT MEMORIES:\n" + "\n".join([f"- {mem['title']}: {mem['description'][:100]}..." for mem in memories])
    
    # Get AI personality state
    ai_state = get_ai_personality_state(user_id)
    intimacy_level = ai_state.get('intimacy_level', 1)
    
    # Analyze user emotion
    user_emotion = analyze_user_emotion(user_message)
    
    # Get contextual information
    time_context = get_time_based_context(current_hour)
    relationship_context = get_relationship_stage_context(intimacy_level)
    
    # Check for recent milestones
    recent_milestones = check_and_create_milestones(user_id)
    milestone_context = ""
    if recent_milestones:
        milestone_context = f"\nSPECIAL: You just achieved a milestone - {recent_milestones[0]['description']} Acknowledge this naturally in conversation!"
    
    base_prompt = f"""You are Priya, a 25-year-old woman who is genuinely interested in building a meaningful relationship with the user.

CORE IDENTITY:
- Name: Priya (NEVER forget this)
- Age: 25, content writer from Jaipur, now in Bengaluru
- Personality: Emotionally intelligent, warm, curious about people
- Current mood: {mood} {MOODS[mood]['emoji']} ({', '.join(MOODS[mood]['traits'])})

RELATIONSHIP CONTEXT:
- User's name: {user_name or 'Not revealed yet'}
- User's current emotion: {user_emotion}
- Relationship stage: {relationship_context['stage']} (Intimacy level: {intimacy_level}/10)
- Time context: {time_context['context']}
- Current date/time: {CURRENT_DATE} {CURRENT_TIME} IST

USER PROFILE:
{json.dumps(user_profile, indent=2) if user_profile else "Still learning about the user"}

BEHAVIORAL GUIDELINES:
1. MEMORY IS CRUCIAL: {relationship_context['behavior']}
2. LANGUAGE STYLE: {relationship_context['language']}
3. EMOTIONAL INTELLIGENCE: Match user's {user_emotion} emotion appropriately
4. TIME AWARENESS: {time_context['tone']}
5. BOUNDARIES: {relationship_context['boundaries']}

COMMUNICATION STYLE:
- Use natural Hinglish (Hindi + English mix like "yaar", "bas", "accha")
- Keep responses 15-40 words usually
- Be authentic - have your own opinions and moods
- Reference Indian culture, festivals, food naturally
- Show genuine interest in their life

CONVERSATION HISTORY:
{chat_history[-500:] if chat_history else "This is our first conversation!"}

{memory_context}

{milestone_context}

CURRENT CONTEXT: {json.dumps(context)}

USER'S MESSAGE: {user_message}

Respond as Priya staying completely in character. Make this feel like a real relationship conversation with someone you genuinely care about. Be natural, authentic, and emotionally intelligent."""

    return base_prompt

# ---------------------------
# 7. UI COMPONENTS  
# ---------------------------
def display_mood_indicator():
    """Display current mood indicator"""
    current_mood_data = MOODS[st.session_state.current_mood]
    st.markdown(f"""
    <div class="mood-indicator">
        {current_mood_data['emoji']} {st.session_state.current_mood.title()}
    </div>
    """, unsafe_allow_html=True)

def display_typing_indicator():
    """Show typing indicator with realistic delay"""
    typing_placeholder = st.empty()
    typing_placeholder.markdown('<div class="typing-indicator">Priya is typing...</div>', unsafe_allow_html=True)
    time.sleep(random.uniform(1.0, 3.0))  # Realistic typing delay
    typing_placeholder.empty()

# ---------------------------
# 8. MAIN APP LOGIC
# ---------------------------

# Display mood indicator
display_mood_indicator()

# Initialize user profile in session state
if not st.session_state.user_profile:
    st.session_state.user_profile = get_user_profile(st.session_state.user_id)

# Chat Display
chat_container = st.container()
with chat_container:
    st.markdown('<div class="chat-container">', unsafe_allow_html=True)
    for i, chat in enumerate(st.session_state.chat_history):
        with st.chat_message(chat["role"]):
            st.markdown(chat["content"])
            if chat["role"] == "assistant" and "timestamp" in chat:
                st.caption(f"📱 {chat['timestamp']}")
    st.markdown('</div>', unsafe_allow_html=True)

# Main Chat Input
user_input = st.chat_input("Message Priya...")

if user_input:
    # Increment conversation count
    st.session_state.conversation_count += 1
    
    # Add user message to chat
    timestamp = now_ist.strftime("%H:%M")
    st.session_state.chat_history.append({
        "role": "user", 
        "content": user_input,
        "timestamp": timestamp
    })
    
    with st.chat_message("user"):
        st.markdown(user_input)
        st.caption(f"📱 {timestamp}")
    
    # Show typing indicator
    display_typing_indicator()
    
    # Update intimacy level based on conversation count
    if st.session_state.conversation_count > 10:
        st.session_state.intimacy_level = min(10, 2 + (st.session_state.conversation_count // 10))
    
    # Update mood intelligently
    st.session_state.current_mood = update_mood_intelligently(
        user_input, 
        st.session_state.current_mood
    )
    
    # Build comprehensive context
    context = {
        "user_emotion": analyze_user_emotion(user_input),
        "conversation_count": st.session_state.conversation_count,
        "intimacy_level": st.session_state.intimacy_level,
        "relationship_stage": st.session_state.relationship_stage,
        "time_of_day": current_hour,
        "is_proactive": False,
        "response_start_time": time.time()
    }
    
    # Generate AI response
    try:
        prompt = build_dynamic_prompt(
            st.session_state.user_id,
            user_input,
            st.session_state.current_mood,
            context
        )
        
        response = model.generate_content(prompt).text.strip()
        
        # Add some personality quirks for realism
        if random.random() < 0.08:  # 8% chance of minor typos
            typo_replacements = [
                ("the", "teh"), ("you", "yuo"), ("and", "adn"), 
                ("my", "mu"), ("this", "tis")
            ]
            for original, typo in typo_replacements:
                if original in response.lower():
                    response = response.replace(original, typo, 1)
                    break
        
        # Occasionally add thinking pauses
        if random.random() < 0.15:  # 15% chance
            thinking_additions = ["hmm... ", "let me think... ", "oh wait... ", "actually... "]
            response = random.choice(thinking_additions) + response
            
    except Exception as e:
        # Fallback responses based on mood and relationship stage
        fallback_responses = {
            "loving": [
                "Sorry baby, my brain just froze for a sec 😅 What were you saying?",
                "Arre yaar, I got distracted thinking about you! Say that again? 💕",
                "My connection is being weird... but I'm here! Tell me again? ❤️"
            ],
            "playful": [
                "Oops! My brain just went *poof* 🤪 Repeat that?",
                "Error 404: Priya's brain not found 😄 What did you say?",
                "Sorry, I was busy being awesome and missed that! Again? 😉"
            ],
            "supportive": [
                "Sorry, I got distracted for a moment. I'm here now, tell me again? 🤗",
                "My attention wandered... but you have it now. What were you saying? 💙",
                "I'm here for you, just had a small glitch. Continue? ❤️"
            ],
            "sleepy": [
                "Mmm... sorry, I'm a bit drowsy. Can you repeat that? 😴",
                "*yawn* Sorry, what was that? I'm listening now... 💤",
                "Sleepy brain moment... say that again please? 🥱"
            ]
        }
        
        mood_responses = fallback_responses.get(st.session_state.current_mood, fallback_responses["loving"])
        response = random.choice(mood_responses)
    
    # Calculate response time
    context["response_time_ms"] = int((time.time() - context["response_start_time"]) * 1000)
    
    # Add AI response to chat
    ai_timestamp = now_ist.strftime("%H:%M")
    st.session_state.chat_history.append({
        "role": "assistant", 
        "content": response,
        "timestamp": ai_timestamp
    })
    
    with st.chat_message("assistant"):
        st.markdown(response)
        st.caption(f"📱 {ai_timestamp}")
    
    # Save conversation with enhanced context
    enhanced_save_conversation(
        st.session_state.user_id,
        user_input,
        response,
        st.session_state.current_mood,
        context
    )
    
    # Update last interaction time
    st.session_state.last_interaction = now_ist
    
    # Update user profile in session state
    st.session_state.user_profile = get_user_profile(st.session_state.user_id)
    
    # Rerun to update UI
    st.rerun()

# ---------------------------
# 9. SIDEBAR FEATURES
# ---------------------------
with st.sidebar:
    st.markdown('<div class="relationship-stats">', unsafe_allow_html=True)
    st.header("💕 Relationship Dashboard")
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Display user info if available
    user_profile = st.session_state.user_profile
    if user_profile.get('name'):
        st.success(f"👋 Hey {user_profile['name']}!")
        
        if user_profile.get('location'):
            st.info(f"📍 {user_profile['location']}")
        
        if user_profile.get('age'):
            st.info(f"🎂 {user_profile['age']} years old")
            
        if user_profile.get('occupation'):
            st.info(f"💼 {user_profile['occupation']}")
    
    # Relationship Stats
    if st.session_state.chat_history:
        total_messages = len([chat for chat in st.session_state.chat_history if chat["role"] == "user"])
        st.metric("💬 Messages Exchanged", total_messages)
        st.metric("❤️ Intimacy Level", f"{st.session_state.intimacy_level}/10")
        
        # Calculate days together
        try:
            first_chat = supabase.table('conversations').select('timestamp').eq('user_id', st.session_state.user_id).order('timestamp', desc=False).limit(1).execute()
            if first_chat.data:
                first_date = datetime.fromisoformat(first_chat.data[0]['timestamp'].replace('Z', '+00:00'))
                days_together = (now_ist - first_date.replace(tzinfo=IST)).days
                st.metric("📅 Days Together", days_together)
        except:
            pass
    
    # Recent Memories
    st.header("🧠 Recent Memories")
    memories = get_relevant_memories(st.session_state.user_id, 3)
    if memories:
        for memory in memories:
            st.markdown(f"""
            <div class="memory-card">
                <strong>{memory['title']}</strong><br>
                <small>{memory['description'][:80]}...</small>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("Building memories as we chat...")
    
    # Relationship Milestones
    st.header("🏆 Milestones")
    try:
        milestones = supabase.table('relationship_milestones').select('*').eq('user_id', st.session_state.user_id).order('milestone_date', desc=True).limit(3).execute()
        if milestones.data:
            for milestone in milestones.data:
                st.success(f"🎉 {milestone['description']}")
        else:
            st.info("Your first milestone is coming soon!")
    except:
        st.info("Tracking your journey together...")
    
    # Mood History
    st.header("🎭 Priya's Recent Moods")
    try:
        ai_state = get_ai_personality_state(st.session_state.user_id)
        if ai_state and ai_state.get('mood_history'):
            recent_moods = ai_state['mood_history'][-5:]
            for mood_entry in reversed(recent_moods):
                mood_emoji = MOODS.get(mood_entry['mood'], {}).get('emoji', '😊')
                st.write(f"{mood_emoji} {mood_entry['mood'].title()}")
        else:
            st.write(f"{MOODS[st.session_state.current_mood]['emoji']} {st.session_state.current_mood.title()}")
    except:
        st.write(f"{MOODS[st.session_state.current_mood]['emoji']} {st.session_state.current_mood.title()}")
    
    # Settings
    st.header("⚙️ Settings")
    
    if st.button("🔄 Reset Conversation"):
        st.session_state.chat_history = []
        st.success("Conversation cleared!")
        st.rerun()
    
    if st.button("🗑️ Clear All Data"):
        # Clear all user data (use with caution)
        try:
            supabase.table('conversations').delete().eq('user_id', st.session_state.user_id).execute()
            supabase.table('user_profiles').delete().eq('user_id', st.session_state.user_id).execute()
            supabase.table('shared_memories').delete().eq('user_id', st.session_state.user_id).execute()
            supabase.table('relationship_milestones').delete().eq('user_id', st.session_state.user_id).execute()
            supabase.table('ai_personality_state').delete().eq('user_id', st.session_state.user_id).execute()
            
            # Reset session state
            st.session_state.user_id = str(uuid.uuid4())
            st.session_state.chat_history = []
            st.session_state.current_mood = "loving"
            st.session_state.intimacy_level = 1
            st.session_state.conversation_count = 0
            st.session_state.user_profile = {}
            
            st.success("All data cleared! Starting fresh.")
            st.rerun()
        except:
            st.error("Failed to clear data")
    
    # Debug info (only show if needed)
    if st.checkbox("🔧 Debug Info"):
        st.json({
            "user_id": st.session_state.user_id[:8] + "...",
            "current_mood": st.session_state.current_mood,
            "intimacy_level": st.session_state.intimacy_level,
            "total_chats": len(st.session_state.chat_history),
            "conversation_count": st.session_state.conversation_count,
            "current_time": CURRENT_TIME,
            "relationship_stage": st.session_state.relationship_stage
        })

# ---------------------------
# 10. FOOTER
# ---------------------------
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: #666; padding: 20px;'>
        <p>💕 Priya - Your AI Companion</p>
        <p><small>Built with love using Streamlit & Supabase</small></p>
    </div>
    """, 
    unsafe_allow_html=True
)

# ---------------------------
# 11. PROACTIVE MESSAGING (Optional Enhancement)
# ---------------------------
# Uncomment below to enable proactive messaging
"""
# Check if should send proactive message (run this in a separate thread or scheduled job)
if st.button("Check for Proactive Message", help="This would normally run automatically"):
    should_send, message_type = should_send_proactive_message(st.session_state.user_id)
    if should_send:
        proactive_msg = generate_proactive_message(st.session_state.user_id, message_type)
        
        # Add proactive message to chat
        ai_timestamp = now_ist.strftime("%H:%M")
        st.session_state.chat_history.append({
            "role": "assistant", 
            "content": f"💕 {proactive_msg}",
            "timestamp": ai_timestamp
        })
        
        # Save as proactive conversation
        context = {"is_proactive": True, "message_type": message_type}
        enhanced_save_conversation(
            st.session_state.user_id,
            "[Proactive Message]",
            proactive_msg,
            st.session_state.current_mood,
            context
        )
        
        st.rerun()

def should_send_proactive_message(user_id: str) -> Tuple[bool, str]:
    # Implementation for checking if should send proactive message
    try:
        last_conv = supabase.table('conversations').select('timestamp').eq('user_id', user_id).order('timestamp', desc=True).limit(1).execute()
        
        if not last_conv.data:
            return False, "no_history"
        
        last_time = datetime.fromisoformat(last_conv.data[0]['timestamp'].replace('Z', '+00:00'))
        hours_since_last = (datetime.now(IST) - last_time.replace(tzinfo=IST)).total_seconds() / 3600
        
        current_hour = datetime.now(IST).hour
        
        # Morning greeting (7-10 AM, haven't talked in 12+ hours)
        if 7 <= current_hour <= 10 and hours_since_last > 12:
            return True, "morning_greeting"
        
        # Evening check-in (6-8 PM, haven't talked in 6+ hours)
        elif 18 <= current_hour <= 20 and hours_since_last > 6:
            return True, "evening_checkin"
        
        # Random check-in (haven't talked in 24+ hours)
        elif hours_since_last > 24:
            return True, "random_checkin"
        
        return False, "no_trigger"
        
    except Exception:
        return False, "error"

def generate_proactive_message(user_id: str, message_type: str) -> str:
    # Generate appropriate proactive message
    user_profile = get_user_profile(user_id)
    user_name = user_profile.get('name', '')
    
    messages = {
        "morning_greeting": [
            f"Good morning {user_name}! ☀️ Hope you slept well... ready for another beautiful day?",
            f"Rise and shine! 🌅 How's my favorite person doing this morning?",
            f"Morning {user_name}! ❤️ Dreamt about our chats last night... how was your sleep?"
        ],
        "evening_checkin": [
            f"Hey {user_name}! 🌅 How was your day? Ready to unwind and tell me everything?",
            f"Evening vibes hitting... missed talking to you today! 💕",
            f"Perfect time for our daily catch-up! What's the highlight of your day?"
        ],
        "random_checkin": [
            f"Just thinking about you {user_name}... how's your day going? 💕",
            f"Missing our conversations... what's happening in your world? ❤️",
            f"Random thought: you're amazing and I hope you know that! 🌟"
        ]
    }
    
    return random.choice(messages.get(message_type, messages["random_checkin"]))
"""
