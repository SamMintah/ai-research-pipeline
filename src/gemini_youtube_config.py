# Gemini YouTube Algorithm Optimization Configuration
# Based on insights about YouTube's Large Recommender Model (LRM) integration

GEMINI_OPTIMIZATION_CONFIG = {
    # Core algorithm insights
    "algorithm_focus": {
        "personalization": "Smarter, more personal recommendations",
        "content_understanding": "Deep understanding of visuals, audio, and context",
        "viewer_experience": "Meaningful viewer experience over pure entertainment",
        "adaptation": "Recognition of evolving viewer interests and habits"
    },
    
    # Content creation guidelines for Gemini algorithm
    "content_guidelines": {
        "engagement_priority": [
            "Clear value proposition from the start",
            "Strong narrative arcs and compelling storytelling", 
            "Content that maintains interest throughout",
            "Natural interaction encouragement (comments, likes, shares)"
        ],
        "quality_factors": [
            "Relevance to specific niches or viewer interests",
            "Clarity and conciseness in presentation",
            "Well-structured and easy-to-understand content",
            "Natural integration of keywords and thematic focus"
        ],
        "ai_optimization": [
            "Content designed for AI analysis of visuals and audio",
            "Clear thematic focus throughout the video",
            "Natural keyword integration for AI understanding",
            "Structured content that AI can easily parse"
        ]
    },
    
    # High-CPM audience targeting (US/Canadian focus)
    "audience_targeting": {
        "geographic_focus": ["United States", "Canada", "United Kingdom", "Australia"],
        "demographic_preferences": {
            "age_groups": ["25-34", "35-44", "45-54"],  # Higher purchasing power
            "interests": ["business", "technology", "entrepreneurship", "finance", "innovation"],
            "education": ["college_educated", "professionals", "decision_makers"]
        },
        "cultural_elements": {
            "business_culture": ["Silicon Valley", "Wall Street", "startup ecosystem"],
            "values": ["American Dream", "entrepreneurship", "innovation", "success"],
            "terminology": ["IPO", "venture capital", "Fortune 500", "market cap", "disruption"]
        }
    },
    
    # Script optimization techniques
    "script_optimization": {
        "opening_hooks": [
            "What if I told you...",
            "Here's what most people don't know...",
            "The untold story behind...",
            "This changed everything...",
            "Before we dive in, let me ask you this..."
        ],
        "retention_techniques": [
            "But here's where it gets interesting...",
            "Wait until you hear this...",
            "This next part will blow your mind...",
            "But that's not the whole story...",
            "Here's the plot twist..."
        ],
        "engagement_patterns": [
            "Question-based transitions",
            "Cliffhanger moments",
            "Callback references",
            "Viewer-directed questions",
            "Anticipation building"
        ]
    },
    
    # SEO and discoverability optimization
    "seo_optimization": {
        "high_value_keywords": [
            "business documentary", "success story", "entrepreneurship",
            "startup journey", "billion dollar company", "corporate history",
            "innovation story", "tech industry", "business strategy"
        ],
        "trending_topics": [
            "AI and technology", "sustainable business", "remote work culture",
            "digital transformation", "cryptocurrency and fintech", "social media impact"
        ],
        "title_formulas": [
            "How [Company] Built a $X Billion Empire",
            "The Untold Story of [Person]'s Rise to Power", 
            "[Number] Secrets Behind [Company]'s Success",
            "Why [Company] Nearly Failed (And How They Survived)",
            "The Real Story Behind [Famous Event/Decision]"
        ]
    },
    
    # Thumbnail and visual optimization
    "visual_optimization": {
        "thumbnail_elements": [
            "High contrast colors (red, blue, yellow)",
            "Clear facial expressions (surprise, determination)",
            "Before/after comparisons",
            "Money/success symbols ($, graphs, charts)",
            "Bold, readable text overlays (2-4 words max)"
        ],
        "b_roll_priorities": [
            "Office/workspace footage",
            "Product demonstrations", 
            "Historical archival footage",
            "Charts and data visualizations",
            "Interview clips and testimonials"
        ]
    }
}

# Helper functions for accessing configuration
def get_engagement_hooks():
    """Get list of proven engagement hooks"""
    return GEMINI_OPTIMIZATION_CONFIG["script_optimization"]["opening_hooks"]

def get_retention_techniques():
    """Get list of retention techniques"""
    return GEMINI_OPTIMIZATION_CONFIG["script_optimization"]["retention_techniques"]

def get_cultural_keywords():
    """Get US/Canadian cultural keywords"""
    return GEMINI_OPTIMIZATION_CONFIG["audience_targeting"]["cultural_elements"]["terminology"]

def get_seo_keywords():
    """Get high-value SEO keywords"""
    return GEMINI_OPTIMIZATION_CONFIG["seo_optimization"]["high_value_keywords"]

def get_title_formulas():
    """Get proven title formulas"""
    return GEMINI_OPTIMIZATION_CONFIG["seo_optimization"]["title_formulas"]