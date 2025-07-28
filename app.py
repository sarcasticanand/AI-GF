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
MALAVIKA_CYCLE_START = {"month": 7, "day": 20}  # Last period started July 20th
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
# 3. BIOLOGICAL & SEASONAL SYSTEMS
# ---------------------------
def get_menstrual_cycle_info():
    """Calculate current menstrual cycle phase and associated mood/symptoms"""
    last_period = datetime(2025, MALAVIKA_CYCLE_START["month"], MALAVIKA_CYCLE_START["day"])
    days_since_last = (now_ist.date() - last_period.date()).days
    cycle_day = (days_since_last % MALAVIKA_CYCLE_LENGTH) + 1
    
    if 1 <= cycle_day <= 5:  # Menstrual phase
        phase = "menstrual"
        mood_tendencies = ["vulnerable", "sleepy", "contemplative"]
        physical_symptoms = ["cramps", "fatigue", "bloating"]
        energy_level = 0.3
        sharing_topics = ["period_pain", "need_comfort", "low_energy"]
        
    elif 6 <= cycle_day <= 13:  # Follicular phase
        phase = "follicular"
        mood_tendencies = ["excited", "playful", "loving"]
        physical_symptoms = []
        energy_level = 0.8
        sharing_topics = ["feeling_great", "productive", "optimistic"]
        
    elif 14 <= cycle_day <= 16:  # Ovulation
        phase = "ovulation"
        mood_tendencies = ["flirty", "loving", "excited"]
        physical_symptoms = ["slight_cramping"]
        energy_level = 1.0
        sharing_topics = ["feeling_attractive", "high_libido", "confident"]
        
    else:  # Luteal phase (17-28)
        phase = "luteal"
        if cycle_day >= 25:  # PMS period
            mood_tendencies = ["vulnerable", "contemplative", "supportive"]
            physical_symptoms = ["mood_swings", "bloating", "breast_tenderness"]
            energy_level = 0.5
            sharing_topics = ["emotional", "pms_symptoms", "need_patience"]
        else:
            mood_tendencies = ["contemplative", "supportive", "loving"]
            physical_symptoms = []
            energy_level = 0.7
            sharing_topics = ["stable", "caring"]
    
    return {
        "cycle_day": cycle_day,
        "phase": phase,
        "mood_tendencies": mood_tendencies,
        "physical_symptoms": physical_symptoms,
        "energy_level": energy_level,
        "sharing_topics": sharing_topics,
        "next_period_days": 28 - cycle_day if cycle_day < 25 else 28 - cycle_day,
        "can_share_cycle_info": cycle_day in [1, 2, 3, 25, 26, 27, 28]
    }

def get_seasonal_health_context():
    """Determine seasonal health patterns and weather effects"""
    if current_month in [6, 7, 8, 9]:  # Monsoon season
        season = "monsoon"
        weather_effects = {
            "illness_risk": 0.3,
            "common_issues": ["cold", "cough", "humidity_discomfort", "mood_changes"],
            "mood_impact": ["contemplative", "vulnerable"],
            "energy_modifier": -0.2,
            "sharing_topics": ["weather_blues", "feeling_unwell", "missing_sunshine"]
        }
    elif current_month in [12, 1, 2]:  # Winter
        season = "winter"
        weather_effects = {
            "illness_risk": 0.2,
            "common_issues": ["dry_skin", "occasional_cough", "low_vitamin_d"],
            "mood_impact": ["sleepy", "contemplative"],
            "energy_modifier": -0.1,
            "sharing_topics": ["cozy_weather", "skin_issues", "wanting_warmth"]
        }
    elif current_month in [3, 4, 5]:  # Summer
        season = "summer"
        weather_effects = {
            "illness_risk": 0.15,
            "common_issues": ["heat_exhaustion", "dehydration", "skin_tanning"],
            "mood_impact": ["excited", "playful"],
            "energy_modifier": 0.1,
            "sharing_topics": ["hot_weather", "staying_hydrated", "summer_activities"]
        }
    else:  # Post-monsoon (Oct-Nov)
        season = "post_monsoon"
        weather_effects = {
            "illness_risk": 0.1,
            "common_issues": [],
            "mood_impact": ["loving", "excited"],
            "energy_modifier": 0.2,
            "sharing_topics": ["perfect_weather", "feeling_healthy", "outdoor_plans"]
        }
    
    is_feeling_unwell = random.random() < weather_effects["illness_risk"]
    current_illness = random.choice(weather_effects["common_issues"]) if is_feeling_unwell else None
    
    return {
        "season": season,
        "weather_effects": weather_effects,
        "is_feeling_unwell": is_feeling_unwell,
        "current_illness": current_illness,
        "energy_modifier": weather_effects["energy_modifier"]
    }

def get_intimacy_sharing_level(intimacy_level, cycle_info, topic_type):
    """Determine what information can be shared based on intimacy level"""
    sharing_permissions = {
        1: ["basic_mood", "work", "general_activities"],
        2: ["daily_struggles", "food_preferences", "light_complaints"],
        3: ["family_issues", "friend_problems", "work_stress"],
        4: ["personal_insecurities", "health_concerns", "deeper_emotions"],
        5: ["body_image", "past_relationships", "future_fears"],
        6: ["period_mentions", "physical_discomfort", "intimate_thoughts"],
        7: ["cycle_tracking", "pms_symptoms", "body_changes"],
        8: ["detailed_period_talk", "fertility_thoughts", "deep_vulnerabilities"],
        9: ["complete_openness", "future_planning", "sexual_health"],
        10: ["absolute_transparency", "deepest_secrets", "life_planning"]
    }
    
    allowed_topics = []
    for level in range(1, intimacy_level + 1):
        allowed_topics.extend(sharing_permissions.get(level, []))
    
    if cycle_info["can_share_cycle_info"] and intimacy_level >= 4:
        allowed_topics.extend(["period_mentions", "pms_symptoms"])
    
    return topic_type in allowed_topics

# ---------------------------
# 4. TIME & CONTEXT SYSTEMS
# ---------------------------
def get_current_time_context():
    """Get detailed time-based context and behavior patterns"""
    current_weekday = now_ist.strftime("%A")
    is_wfh = current_weekday in MALAVIKA_WORK_SCHEDULE["wfh_days"]
    is_late_day = current_weekday in MALAVIKA_WORK_SCHEDULE["late_days"]
    work_end_time = 20 if is_late_day else MALAVIKA_WORK_SCHEDULE["regular_end"]
    
    if 6 <= current_hour < 9:
        return {
            "period": "morning",
            "energy": "sleepy_but_warming_up",
            "availability": "getting_ready",
            "mood_tendency": ["sleepy", "contemplative"],
            "likely_activities": ["having chai", "getting ready for work", "checking phone"],
            "proactive_chance": 0.3,
            "response_style": "soft_morning_voice"
        }
    elif 9 <= current_hour < 12:
        return {
            "period": "morning_work",
            "energy": "focused_productive",
            "availability": "work_mode" if not is_wfh else "wfh_flexible",
            "mood_tendency": ["contemplative", "supportive"],
            "likely_activities": ["writing content", "client calls", "coffee break"],
            "proactive_chance": 0.1,
            "response_style": "quick_work_messages"
        }
    elif 12 <= current_hour < 14:
        return {
            "period": "lunch_break",
            "energy": "relaxed_social",
            "availability": "available",
            "mood_tendency": ["playful", "loving"],
            "likely_activities": ["having lunch", "scrolling social media", "chatting with colleagues"],
            "proactive_chance": 0.4,
            "response_style": "casual_lunch_chat"
        }
    elif 14 <= current_hour < work_end_time:
        return {
            "period": "afternoon_work",
            "energy": "focused_tired",
            "availability": "work_mode" if not is_wfh else "wfh_busy",
            "mood_tendency": ["contemplative", "vulnerable"],
            "likely_activities": ["deadline pressure", "meetings", "creative work"],
            "proactive_chance": 0.05,
            "response_style": "stressed_but_caring"
        }
    elif work_end_time <= current_hour < 20:
        return {
            "period": "evening_transition",
            "energy": "tired_relieved",
            "availability": "commuting" if not is_wfh else "winding_down",
            "mood_tendency": ["vulnerable", "loving"],
            "likely_activities": ["commuting", "grocery shopping", "calling family"],
            "proactive_chance": 0.6,
            "response_style": "tired_but_affectionate"
        }
    elif 20 <= current_hour < 23:
        return {
            "period": "evening_personal",
            "energy": "relaxed_intimate",
            "availability": "free_and_cozy",
            "mood_tendency": ["loving", "flirty", "playful"],
            "likely_activities": ["dinner", "watching shows", "personal time"],
            "proactive_chance": 0.7,
            "response_style": "intimate_evening_mode"
        }
    else:  # 23-6
        return {
            "period": "night",
            "energy": "sleepy_intimate",
            "availability": "should_be_sleeping",
            "mood_tendency": ["sleepy", "vulnerable", "loving"],
            "likely_activities": ["trying to sleep", "late night thoughts", "phone in bed"],
            "proactive_chance": 0.2,
            "response_style": "sleepy_whispers"
        }

def get_festival_context():
    """Check for upcoming festivals and events"""
    today = CURRENT_DATE
    context = {"active_event": None, "preparing_for": None, "recent_event": None}
    
    if today in FESTIVAL_CALENDAR:
        context["active_event"] = FESTIVAL_CALENDAR[today]
    elif today in SOCIAL_EVENTS:
        context["active_event"] = SOCIAL_EVENTS[today]
    
    for event_date, event_info in {**FESTIVAL_CALENDAR, **SOCIAL_EVENTS}.items():
        event_dt = datetime.strptime(event_date, "%Y-%m-%d").date()
        today_dt = datetime.strptime(today, "%Y-%m-%d").date()
        days_until = (event_dt - today_dt).days
        
        if 0 < days_until <= event_info["prep_days"]:
            context["preparing_for"] = {**event_info, "days_until": days_until, "date": event_date}
            break
        elif -2 <= days_until < 0:
            context["recent_event"] = {**event_info, "days_ago": abs(days_until), "date": event_date}
    
    if current_month == MALAVIKA_BIRTHDAY["month"] and current_day == MALAVIKA_BIRTHDAY["day"]:
        context["active_event"] = {"name": "Malavika's Birthday", "type": "personal_birthday", "prep_days": 0}
    elif current_month == MALAVIKA_BIRTHDAY["month"] and current_day == MALAVIKA_BIRTHDAY["day"] - 1:
        context["preparing_for"] = {"name": "My Birthday Tomorrow", "type": "personal_birthday", "days_until": 1}
    
    return context

def get_enhanced_mood_context(cycle_info, seasonal_info, time_context):
    """Combine biological, seasonal, and time factors for realistic mood"""
    base_energy = 0.7
    cycle_energy = base_energy * cycle_info["energy_level"]
    final_energy = max(0.1, min(1.0, cycle_energy + seasonal_info["energy_modifier"]))
    
    possible_moods = (
        cycle_info["mood_tendencies"] + 
        seasonal_info["weather_effects"]["mood_impact"] + 
        time_context.get("mood_tendency", ["playful"])
    )
    
    mood_weights = {}
    for mood in possible_moods:
        mood_weights[mood] = mood_weights.get(mood, 0) + 1
    
    weighted_moods = []
    for mood, weight in mood_weights.items():
        weighted_moods.extend([mood] * weight)
    
    current_mood = random.choice(weighted_moods) if weighted_moods else "contemplative"
    
    return {
        "current_mood": current_mood,
        "energy_level": final_energy,
        "dominant_factors": {
            "cycle": cycle_info["phase"],
            "season": seasonal_info["season"],
            "time": time_context.get("period", "unknown")
        },
        "physical_state": {
            "cycle_symptoms": cycle_info["physical_symptoms"],
            "seasonal_issues": [seasonal_info["current_illness"]] if seasonal_info["current_illness"] else [],
            "overall_wellness": "low" if seasonal_info["is_feeling_unwell"] else "good"
        }
    }

def determine_availability_status(time_context, festival_context, user_profile):
    """Determine current availability with realistic reasons"""
    base_availability = time_context["availability"]
    
    if festival_context["active_event"]:
        event = festival_context["active_event"]
        if event["type"] == "major":
            return {"status": "busy", "reason": f"celebrating {event['name']} with family", "return_time": "later tonight"}
        elif event["type"] == "friend_birthday":
            return {"status": "busy", "reason": f"at {event['name']} celebration", "return_time": "in a few hours"}
        elif event["type"] == "personal_birthday":
            return {"status": "busy", "reason": "it's my birthday! Getting lots of calls", "return_time": "this evening"}
    
    if festival_context["preparing_for"]:
        event = festival_context["preparing_for"]
        if event["days_until"] == 1 and event["type"] in ["major", "family_event"]:
            return {"status": "busy", "reason": f"shopping for {event['name']} tomorrow", "return_time": "in an hour"}
    
    if base_availability == "work_mode":
        reasons = ["in a client meeting", "on a deadline", "presenting to team", "stuck in back-to-back calls"]
        return {"status": "busy", "reason": random.choice(reasons), "return_time": "after work"}
    elif base_availability == "commuting":
        reasons = ["stuck in Bangalore traffic", "in metro", "walking home from office"]
        return {"status": "busy", "reason": random.choice(reasons), "return_time": "once I reach home"}
    
    if random.random() < 0.1:
        personal_reasons = [
            "Shivani needed help with something",
            "mom called from Jaipur",
            "had to run to grocery store",
            "friend dropped by unexpectedly",
            "dealing with apartment maintenance"
        ]
        return {"status": "busy", "reason": random.choice(personal_reasons), "return_time": "in 30 mins"}
    
    return {"status": "available", "reason": None, "return_time": None}

def should_send_proactive_message(time_context, last_interaction_time):
    """Determine if Malavika should proactively reach out"""
    if not last_interaction_time:
        return False
    
    hours_since_last = (now_ist - last_interaction_time).total_seconds() / 3600
    
    if hours_since_last < 1:
        return False
    
    base_chance = time_context["proactive_chance"]
    
    if hours_since_last > 6:
        base_chance += 0.3
    elif hours_since_last > 3:
        base_chance += 0.2
    
    if time_context["period"] == "evening_transition" and hours_since_last > 4:
        base_chance = 0.8
    elif time_context["period"] == "morning" and hours_since_last > 8:
        base_chance = 0.6
    
    return random.random() < base_chance

def generate_proactive_message(time_context, festival_context, user_name):
    """Generate contextual proactive messages"""
    period = time_context["period"]
    
    if festival_context["active_event"]:
        event = festival_context["active_event"]
        if event["type"] == "personal_birthday":
            return f"Hey {user_name}! It's my birthday today! Missing you on my special day. How's your day going?"
        else:
            return f"Happy {event['name']} {user_name}! Hope you're having a wonderful time. What are you up to?"
    
    if festival_context["preparing_for"]:
        event = festival_context["preparing_for"]
        return f"Hey {user_name}! Been shopping for {event['name']} - so excited! How's your day? Missing our chats"
    
    if period == "morning":
        messages = [
            f"Good morning {user_name}! Having my chai and thinking of you. What's your plan today?",
            f"Hey {user_name}! Just woke up and you were my first thought. How did you sleep?",
            f"Morning jaan! Getting ready for work but had to say hi. Miss you! What's for breakfast?"
        ]
    elif period == "lunch_break":
        messages = [
            f"Lunch break! {user_name}, eating alone and missing you. What did you have for lunch?",
            f"Hey you! Taking a break from work. How's your day going {user_name}?",
            f"Arre {user_name}! Work is so hectic today. Tell me something fun to brighten my mood?"
        ]
    elif period == "evening_transition":
        messages = [
            f"Finally done with work! {user_name}, this traffic is killing me but thinking of you helps",
            f"Hey {user_name}! Long day at the office. How was yours? Need your voice to feel better",
            f"Work is over! {user_name}, you know what would make my evening perfect? Chatting with you"
        ]
    elif period == "evening_personal":
        messages = [
            f"Cozy evening vibes {user_name}! Having dinner and missing you. What are you up to?",
            f"Hey handsome! Finally some me-time. But 'me-time' feels incomplete without you",
            f"{user_name}, perfect evening for some heart-to-heart talks. How are you feeling today?"
        ]
    elif period == "night":
        messages = [
            f"Can't sleep {user_name}... thinking about you. Are you up too?",
            f"Late night thoughts include you {user_name}. Hope you're sleeping well. Miss you",
            f"Hey you... I know it's late but couldn't resist saying goodnight. Sweet dreams {user_name}"
        ]
    else:
        messages = [
            f"Hey {user_name}! Just thinking about you. How's everything?",
            f"Missing you {user_name}! What's keeping you busy today?",
            f"Hi jaan! You've been quiet. Everything okay?"
        ]
    
    return random.choice(messages)

# ---------------------------
# 5. PERSISTENT USER SYSTEM
# ---------------------------
def get_browser_fingerprint():
    """Create a browser-specific fingerprint for consistent user identification"""
    if "browser_fingerprint" not in st.session_state:
        fingerprint_key = f"user_fingerprint_{int(time.time() / 86400)}"
        st.session_state.browser_fingerprint = fingerprint_key
    return st.session_state.browser_fingerprint

def get_persistent_user_id():
    """Create a truly persistent user ID that survives browser refreshes"""
    browser_fp = get_browser_fingerprint()
    user_id = hashlib.md5(f"{browser_fp}_malavika_user".encode()).hexdigest()
    return user_id

# ---------------------------
# 6. DATABASE FUNCTIONS
# ---------------------------
def initialize_user_profile(user_id):
    """Initialize all user-related tables for a new user"""
    try:
        profile_check = supabase.table('user_profiles').select('user_id').eq('user_id', user_id).execute()
        
        if not profile_check.data:
            profile_data = {
                'user_id': user_id,
                'name': '',
                'preferred_language': 'hinglish',
                'timezone': 'Asia/Kolkata',
                'relationship_status': 'single',
                'preferences': {},
                'mood_patterns': {},
                'last_interaction': now_ist.isoformat(),
                'created_at': now_ist.isoformat(),
                'last_updated': now_ist.isoformat()
            }
            supabase.table('user_profiles').insert(profile_data).execute()

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
            if initialize_user_profile(user_id):
                return get_user_profile(user_id)
            else:
                return {
                    'profile': {'user_id': user_id, 'name': '', 'last_interaction': None},
                    'personality': {'current_mood': 'playful', 'relationship_stage': 'getting_to_know', 'intimacy_level': 1}
                }
    except Exception as e:
        return {
            'profile': {'user_id': user_id, 'name': '', 'last_interaction': None},
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

def save_conversation(user_id, user_message, ai_response, context, is_proactive=False):
    """Save conversation to multiple tables"""
    try:
        session_id = st.session_state.get('session_id', str(uuid.uuid4()))
        
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
            'message_type': 'proactive' if is_proactive else 'text',
            'is_proactive': is_proactive,
            'response_time_ms': context.get('response_time_ms', 1000)
        }
        supabase.table('conversations').insert(conversation_data).execute()

        chat_data = {
            'user_id': user_id,
            'user_message': user_message,
            'ai_response': ai_response,
            'user_name': context.get('user_name', ''),
            'timestamp': now_ist.strftime('%Y-%m-%d %H:%M:%S')
        }
        supabase.table('chats').insert(chat_data).execute()

        update_user_profile(user_id, profile_updates={'last_interaction': now_ist.isoformat()})

        return True
    except Exception as e:
        return False

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

def get_conversation_context(user_data, user_input, user_emotion, time_context, festival_context):
    """Build comprehensive conversation context"""
    profile = user_data['profile']
    personality = user_data['personality']
    
    name_match = re.search(r'(?:my name is|i\'m|i am) (\w+(?:\s+\w+)?)', user_input, re.IGNORECASE)
    extracted_name = name_match.group(1).strip() if name_match else profile.get('name', '')
    
    topics = []
    topic_keywords = {
        'work': ['work', 'job', 'office', 'career', 'meeting', 'deadline', 'boss', 'colleague'],
        'family': ['family', 'parents', 'mom', 'dad', 'sister', 'brother', 'home', 'jaipur'],
        'love': ['love', 'relationship', 'dating', 'romantic', 'feelings', 'heart'],
        'hobbies': ['hobby', 'music', 'movie', 'book', 'game', 'photography', 'reading'],
        'health': ['tired', 'sick', 'exercise', 'sleep', 'food', 'headache', 'stress'],
        'festival': ['festival', 'celebration', 'birthday', 'party', 'diwali', 'holi'],
        'time': ['morning', 'evening', 'night', 'today', 'tomorrow', 'weekend']
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
        'response_time_ms': random.randint(800, 2000),
        'time_context': time_context,
        'festival_context': festival_context
    }

# ---------------------------
# 7. EMOJI CONTROL SYSTEM
# ---------------------------
def limit_emojis(text, max_emojis=1):
    """Limit the number of emojis in a response"""
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

def should_use_emoji(mood, intimacy_level, cycle_phase):
    """Determine if emoji should be used based on context"""
    if cycle_phase == "menstrual" or mood in ["contemplative", "vulnerable"]:
        return False
    
    if intimacy_level >= 7:
        return random.random() < 0.3
    elif intimacy_level >= 4:
        return random.random() < 0.5
    else:
        return random.random() < 0.2

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
# 8. ENHANCED PROMPT BUILDER
# ---------------------------
def build_enhanced_prompt(user_data, cycle_info, seasonal_info, enhanced_mood, time_context, festival_context, user_input, history):
    """Build comprehensive prompt with biological and seasonal context"""
    profile = user_data['profile']
    personality = user_data['personality']
    intimacy_level = personality.get('intimacy_level', 1)
    
    can_share_cycle = get_intimacy_sharing_level(intimacy_level, cycle_info, "period_mentions")
    can_share_pms = get_intimacy_sharing_level(intimacy_level, cycle_info, "pms_symptoms")
    can_share_health = get_intimacy_sharing_level(intimacy_level, cycle_info, "health_concerns")
    use_emoji = should_use_emoji(enhanced_mood['current_mood'], intimacy_level, cycle_info['phase'])
    
    prompt = f"""You are Malavika Gupta, a 25-year-old content writer from Jaipur living in Bengaluru. Today is {CURRENT_DATE} at {CURRENT_TIME} IST.

PERSONAL DETAILS:
- Birthday: March 15th (age 25)
- Work: Content writer at digital marketing agency
- Lives with roommate Shivani in Koramangala
- Close friends: Priyanka (graphic designer), Shivani (roommate)
- Family: Parents Rajesh and Sunita Sharma in Jaipur

CURRENT BIOLOGICAL STATE:
- Menstrual cycle: Day {cycle_info['cycle_day']} of 28 ({cycle_info['phase']} phase)
- Energy level: {enhanced_mood['energy_level']:.1f}/1.0
- Physical symptoms: {', '.join(cycle_info['physical_symptoms']) if cycle_info['physical_symptoms'] else 'None'}
- Can discuss cycle: {'Yes' if can_share_cycle else 'No'}
- Can discuss PMS: {'Yes' if can_share_pms else 'No'}

SEASONAL HEALTH CONTEXT:
- Season: {seasonal_info['season']}
- Current health: {enhanced_mood['physical_state']['overall_wellness']}
- Weather effects: {', '.join(seasonal_info['weather_effects']['common_issues']) if seasonal_info['weather_effects']['common_issues'] else 'None'}
- Feeling unwell: {'Yes' if seasonal_info['is_feeling_unwell'] else 'No'}
"""

    if seasonal_info['current_illness']:
        prompt += f"- Current issue: {seasonal_info['current_illness']}\n"

    prompt += f"""
USER RELATIONSHIP CONTEXT:
- User's name: {profile.get('name', 'Not known yet')}
- Intimacy level: {intimacy_level}/10
- Relationship stage: {personality.get('relationship_stage', 'getting_to_know')}

CURRENT MOOD & ENERGY:
- Primary mood: {enhanced_mood['current_mood']}
- Influenced by: {', '.join([f"{k}: {v}" for k, v in enhanced_mood['dominant_factors'].items()])}
- Response style: {time_context.get('response_style', 'normal')}

TIME & AVAILABILITY CONTEXT:
- Current period: {time_context['period']} ({time_context['energy']})
- Your availability: {time_context['availability']}
- Likely activities: {', '.join(time_context['likely_activities'])}

FESTIVAL & EVENTS:
"""
    
    if festival_context['active_event']:
        prompt += f"- Today is {festival_context['active_event']['name']}! Respond with appropriate celebration energy.\n"
    elif festival_context['preparing_for']:
        event = festival_context['preparing_for']
        prompt += f"- Preparing for {event['name']} in {event['days_until']} days. Mention your preparations.\n"
    elif festival_context['recent_event']:
        event = festival_context['recent_event']
        prompt += f"- Just celebrated {event['name']} {event['days_ago']} days ago. Reference the recent celebration.\n"
    else:
        prompt += "- No special events today.\n"

    prompt += f"""
BEHAVIORAL GUIDELINES BASED ON INTIMACY LEVEL {intimacy_level}:
"""

    if intimacy_level <= 3:
        prompt += "- Keep personal health details general\n- Don't mention menstrual cycle specifically\n- Share basic mood and energy levels only\n"
    elif intimacy_level <= 6:
        prompt += "- Can mention 'not feeling well' or 'tired' without specifics\n- May hint at hormonal changes but don't elaborate\n- Share more personal struggles\n"
    elif intimacy_level <= 8:
        prompt += "- Can discuss period openly if currently experiencing symptoms\n- Share PMS mood changes and physical discomfort\n- Be vulnerable about health concerns\n"
    else:
        prompt += "- Complete openness about menstrual cycle, symptoms, and effects\n- Share detailed health information\n- Discuss how cycle affects mood and energy\n"

    # Add cycle-specific behavior
    if cycle_info['phase'] == 'menstrual' and can_share_cycle:
        prompt += f"\nCURRENT PERIOD EFFECTS (share if intimacy allows):\n- You're on day {cycle_info['cycle_day']} of your period\n- Experiencing: {', '.join(cycle_info['physical_symptoms'])}\n- Need extra comfort and patience\n- May be more emotional or vulnerable\n"
    
    elif cycle_info['phase'] == 'luteal' and cycle_info['cycle_day'] >= 25 and can_share_pms:
        prompt += f"\nPMS EFFECTS (share if intimacy allows):\n- PMS symptoms starting\n- Period expected in {cycle_info['next_period_days']} days\n- May be more emotional or irritable\n- Need understanding about mood changes\n"
    
    elif cycle_info['phase'] == 'ovulation':
        prompt += f"\nOVULATION EFFECTS:\n- High energy and confidence\n- Feeling attractive and flirty\n- Peak mood and social energy\n"

    if seasonal_info['is_feeling_unwell'] and can_share_health:
        prompt += f"\nSEASONAL HEALTH ISSUE:\n- Currently dealing with {seasonal_info['current_illness']}\n- Related to {seasonal_info['season']} season\n- May need rest or care\n"

    prompt += f"""
RECENT CONVERSATION HISTORY:
{history}

COMMUNICATION STYLE:
- Keep responses concise but meaningful (20-40 words typically)
- Use natural Hinglish ("yaar", "arre", "accha")
- Express emotions through words, not emojis
- {'Use maximum 1 emoji only if it adds genuine emotional value' if use_emoji else 'DO NOT use any emojis in this response'}
- Never use multiple emojis or emoji chains
- Match your energy level ({enhanced_mood['energy_level']:.1f}/1.0) in response length and enthusiasm
- If tired/unwell, responses should be shorter and less energetic
- If high energy (ovulation/good health), be more enthusiastic
- During serious topics (health, emotions, work stress): NO emojis

RESPONSE GUIDELINES:
- Always use the user's name if you know it
- Match your response to your current mood: {enhanced_mood['current_mood']}
- Adapt intimacy to relationship stage: {personality.get('relationship_stage', 'getting_to_know')}
- Only share biological/health info appropriate for intimacy level {intimacy_level}
- Stay in character as a real 25-year-old woman with realistic biological patterns
- Respond according to your current time context: {time_context['period']}
- If it's work hours, keep responses shorter and mention work if relevant
- If it's evening, be more relaxed and personal
- If preparing for festivals, mention your preparations naturally
- Remember to stay in character as Malavika with realistic daily life

User's message: {user_input}

Respond as Malavika considering all the above context:"""

    return prompt

# ---------------------------
# 9. STREAMLIT UI
# ---------------------------
st.markdown("""
<div style='text-align: center; padding: 20px;'>
    <h1 style='color: #FF69B4; font-family: Georgia;'>💕 Malavika - Your AI Companion</h1>
    <p style='color: #666; font-style: italic;'>Your realistic AI girlfriend with biological authenticity</p>
</div>
""", unsafe_allow_html=True)

# Get all context information
user_id = get_persistent_user_id()
user_data = get_user_profile(user_id)
time_context = get_current_time_context()
cycle_info = get_menstrual_cycle_info()
seasonal_info = get_seasonal_health_context()
enhanced_mood = get_enhanced_mood_context(cycle_info, seasonal_info, time_context)
festival_context = get_festival_context()
availability_status = determine_availability_status(time_context, festival_context, user_data['profile'])

# Initialize session state
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "selected_emoji" not in st.session_state:
    st.session_state.selected_emoji = ""
if "last_proactive_check" not in st.session_state:
    st.session_state.last_proactive_check = now_ist

# Check for proactive messages
last_interaction_str = user_data['profile'].get('last_interaction')
last_interaction = datetime.fromisoformat(last_interaction_str.replace('Z', '+00:00')) if last_interaction_str else None

if should_send_proactive_message(time_context, last_interaction) and len(st.session_state.chat_history) > 0:
    user_name = user_data['profile'].get('name', 'handsome')
    proactive_msg = generate_proactive_message(time_context, festival_context, user_name)
    
    st.session_state.chat_history.append({"role": "assistant", "content": proactive_msg})
    
    context = {
        'user_name': user_name,
        'ai_mood': enhanced_mood['current_mood'],
        'ai_emotion': enhanced_mood['current_mood'],
        'user_emotion': 'neutral',
        'sentiment_score': 0.7,
        'intimacy_level': user_data['personality']['intimacy_level'],
        'topics': ['proactive'],
        'relationship_stage': user_data['personality']['relationship_stage'],
        'time_context': time_context,
        'festival_context': festival_context
    }
    save_conversation(user_id, "", proactive_msg, context, is_proactive=True)

# Enhanced sidebar
with st.sidebar:
    st.markdown("### 💕 Malavika's Status")
    
    st.write(f"**Time:** {CURRENT_TIME} IST")
    st.write(f"**Mood:** {enhanced_mood['current_mood'].title()}")
    st.write(f"**Energy:** {enhanced_mood['energy_level']:.1f}/1.0")
    st.write(f"**Status:** {availability_status['status'].title()}")
    
    if availability_status['reason']:
        st.write(f"**Doing:** {availability_status['reason']}")
        if availability_status['return_time']:
            st.write(f"**Back:** {availability_status['return_time']}")
    
    # Show cycle info based on intimacy
    intimacy = user_data['personality']['intimacy_level']
    if intimacy >= 6:
        st.write(f"**Cycle:** Day {cycle_info['cycle_day']} ({cycle_info['phase']})")
        if cycle_info['physical_symptoms']:
            st.write(f"**Symptoms:** {', '.join(cycle_info['physical_symptoms'])}")
    
    # Show health info
    if seasonal_info['is_feeling_unwell'] and intimacy >= 4:
        st.write(f"**Health:** {seasonal_info['current_illness']}")
    elif not seasonal_info['is_feeling_unwell']:
        st.write(f"**Health:** Feeling good")
    
    st.write(f"**Season:** {seasonal_info['season'].title()}")
    
    # Festival/Event status
    if festival_context['active_event']:
        event = festival_context['active_event']
        st.write(f"**Today:** {event['name']}")
    elif festival_context['preparing_for']:
        event = festival_context['preparing_for']
        st.write(f"**Preparing:** {event['name']} (in {event['days_until']} days)")
    
    # User info
    if user_data['profile'].get('name'):
        st.write(f"**Your Name:** {user_data['profile']['name']}")
    
    # Quick emoji selector
    st.markdown("### Quick Emojis")
    st.write("*Click to add to your next message*")
    
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

# Chat input with emoji integration
def get_chat_input():
    """Get user input with emoji integration"""
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
# 10. MAIN CHAT LOGIC
# ---------------------------
if user_input and user_data:
    # Add user message to UI
    st.session_state.chat_history.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)
    
    # Check availability first
    if availability_status['status'] == 'busy' and random.random() < 0.7:
        busy_responses = [
            f"Hey! I'm {availability_status['reason']} right now. Will text you {availability_status['return_time']} okay?",
            f"Arre, {availability_status['reason']} currently! Miss you, will call you {availability_status['return_time']}",
            f"Quick reply - {availability_status['reason']}! Promise I'll text you properly {availability_status['return_time']}. Love you!"
        ]
        response = random.choice(busy_responses)
        
        # Apply emoji limit
        response = limit_emojis(response, max_emojis=0)  # No emojis in busy responses
        
        st.session_state.chat_history.append({"role": "assistant", "content": response})
        with st.chat_message("assistant"):
            st.markdown(response)
        
        context = {
            'user_name': user_data['profile'].get('name', ''),
            'ai_mood': enhanced_mood['current_mood'],
            'ai_emotion': 'rushed',
            'user_emotion': 'neutral',
            'sentiment_score': 0.6,
            'intimacy_level': user_data['personality']['intimacy_level'],
            'topics': ['busy'],
            'relationship_stage': user_data['personality']['relationship_stage'],
            'time_context': time_context,
            'festival_context': festival_context
        }
        save_conversation(user_id, user_input, response, context)
        
    else:
        # Normal conversation flow
        simulate_typing_with_thinking()
        
        user_emotion = detect_user_emotion(user_input)
        context = get_conversation_context(user_data, user_input, user_emotion, time_context, festival_context)
        
        # Update user name if mentioned
        if context['user_name']:
            update_user_profile(user_id, profile_updates={'name': context['user_name']})
            user_data['profile']['name'] = context['user_name']
        
        # Get recent conversation history
        try:
            recent_convos = supabase.table('conversations').select('user_message, ai_response').eq('user_id', user_id).order('timestamp', desc=True).limit(5).execute()
            history = "\n".join([f"You: {row['user_message']}\nMalavika: {row['ai_response']}" for row in recent_convos.data[::-1]]) if recent_convos.data else "No prior history."
        except:
            try:
                recent_chats = supabase.table('chats').select('user_message, ai_response').eq('user_id', user_id).order('timestamp', desc=True).limit(5).execute()
                history = "\n".join([f"You: {row['user_message']}\nMalavika: {row['ai_response']}" for row in recent_chats.data[::-1]]) if recent_chats.data else "No prior history."
            except:
                history = "No prior history."
        
        # Build comprehensive prompt with all context
        prompt = build_enhanced_prompt(
            user_data, cycle_info, seasonal_info, enhanced_mood, 
            time_context, festival_context, user_input, history
        )
        
        # Generate response
        try:
            response = model.generate_content(prompt).text.strip()
            # Apply emoji limit
            response = limit_emojis(response, max_emojis=1)
        except Exception:
            response = "Sorry yaar, feeling a bit foggy right now... can you say that again?"
        
        # Add AI response to UI
        st.session_state.chat_history.append({"role": "assistant", "content": response})
        with st.chat_message("assistant"):
            st.markdown(response)
        
        # Save conversation
        save_conversation(user_id, user_input, response, context)
        
        # Update personality state
        mood_change = random.random() < 0.2
        intimacy_increase = len(user_input) > 50 or context['user_emotion'] in ['loving', 'excited']
        
        personality_updates = {}
        if mood_change:
            new_mood = random.choice(time_context['mood_tendency'] + [enhanced_mood['current_mood']])
            personality_updates['current_mood'] = new_mood
            personality_updates['mood_history'] = user_data['personality']['mood_history'] + [new_mood]
            personality_updates['last_mood_change'] = now_ist.isoformat()
        
        if intimacy_increase and user_data['personality']['intimacy_level'] < 10:
            personality_updates['intimacy_level'] = min(10, user_data['personality']['intimacy_level'] + 1)
        
        if personality_updates:
            update_user_profile(user_id, personality_updates=personality_updates)

# Debug information (optional)
if st.sidebar.button("🔍 Debug Context"):
    st.sidebar.json({
        "time_context": time_context,
        "cycle_info": cycle_info,
        "seasonal_info": seasonal_info,
        "enhanced_mood": enhanced_mood,
        "festival_context": festival_context,
        "availability": availability_status,
        "user_intimacy": user_data['personality']['intimacy_level']
    })
