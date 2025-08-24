"""
Documentary-style video configuration for enhanced storytelling
"""

# Video length and pacing configuration
DOCUMENTARY_CONFIG = {
    "target_duration_minutes": 15,  # Target 15-minute videos
    "target_word_count": 2500,      # Approximately 2500 words for 15 minutes
    "words_per_minute": 140,        # Slower pace for documentary style
    
    # Section structure for documentary pacing
    "section_structure": {
        "hook_teaser": {
            "word_count": 250,
            "duration_minutes": 1.8,
            "purpose": "Grab attention with shocking revelation or central mystery"
        },
        "origins_setup": {
            "word_count": 350,
            "duration_minutes": 2.5,
            "purpose": "Establish characters, background, and initial situation"
        },
        "inciting_incident": {
            "word_count": 300,
            "duration_minutes": 2.1,
            "purpose": "The moment that started everything - the founding story"
        },
        "rising_action": {
            "word_count": 400,
            "duration_minutes": 2.9,
            "purpose": "Early struggles, first successes, building momentum"
        },
        "first_climax": {
            "word_count": 350,
            "duration_minutes": 2.5,
            "purpose": "Major breakthrough or first big success"
        },
        "complications": {
            "word_count": 400,
            "duration_minutes": 2.9,
            "purpose": "New challenges, conflicts, and obstacles"
        },
        "crisis_point": {
            "word_count": 300,
            "duration_minutes": 2.1,
            "purpose": "Major crisis, failure, or turning point"
        },
        "resolution": {
            "word_count": 250,
            "duration_minutes": 1.8,
            "purpose": "How they overcame or adapted, current state"
        },
        "conclusion": {
            "word_count": 200,
            "duration_minutes": 1.4,
            "purpose": "Lessons learned, impact, and call to action"
        }
    },
    
    # Engagement techniques for retention
    "engagement_patterns": {
        "hook_frequency": 90,  # New hook every 90 seconds
        "question_frequency": 120,  # Rhetorical question every 2 minutes
        "cliffhanger_frequency": 180,  # Mini-cliffhanger every 3 minutes
        "callback_frequency": 240,  # Reference back to opening every 4 minutes
    },
    
    # Documentary storytelling elements
    "storytelling_elements": {
        "character_development": True,
        "timeline_structure": True,
        "conflict_resolution": True,
        "emotional_arcs": True,
        "investigative_reveals": True,
        "expert_perspectives": True,
        "visual_storytelling": True,
        "dramatic_pacing": True
    },
    
    # B-roll and visual cues
    "visual_elements": {
        "broll_frequency": 30,  # B-roll suggestion every 30 seconds
        "music_cue_frequency": 60,  # Music change every minute
        "pause_frequency": 45,  # Dramatic pause every 45 seconds
        "emphasis_frequency": 20,  # Emphasis marker every 20 seconds
    },
    
    # Audience targeting (US/Canadian focus)
    "audience_optimization": {
        "cultural_references_per_section": 2,
        "business_terminology": True,
        "american_english_spelling": True,
        "usd_currency_references": True,
        "north_american_context": True,
        "high_cpm_demographics": True
    }
}

# Documentary narrative structures
NARRATIVE_STRUCTURES = {
    "rise_and_fall": [
        "humble_beginnings", "early_success", "rapid_growth", 
        "peak_success", "major_crisis", "downfall", "lessons_learned"
    ],
    "hero_journey": [
        "ordinary_world", "call_to_adventure", "refusal_of_call",
        "meeting_mentor", "crossing_threshold", "tests_and_trials",
        "ordeal", "reward", "road_back", "resurrection", "return_with_elixir"
    ],
    "investigative": [
        "mystery_setup", "initial_investigation", "first_clues",
        "deeper_investigation", "obstacles_and_resistance", "breakthrough_evidence",
        "shocking_revelations", "final_truth", "implications_and_impact"
    ],
    "business_case_study": [
        "market_context", "founding_vision", "initial_strategy",
        "early_execution", "market_response", "scaling_challenges",
        "strategic_pivots", "competitive_battles", "current_state", "future_outlook"
    ]
}

# Emotional beat patterns for engagement
EMOTIONAL_BEATS = {
    "documentary_standard": [
        "curiosity", "intrigue", "sympathy", "admiration", "concern",
        "tension", "shock", "relief", "inspiration", "reflection"
    ],
    "business_focused": [
        "ambition", "determination", "excitement", "anxiety", "triumph",
        "betrayal", "resilience", "innovation", "success", "wisdom"
    ],
    "investigative_style": [
        "mystery", "suspicion", "discovery", "disbelief", "anger",
        "revelation", "vindication", "justice", "closure", "awareness"
    ]
}