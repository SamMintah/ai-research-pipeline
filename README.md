# AI Documentary Research Pipeline

**Professional documentary research and script generation for YouTube creators.** Input a company name → get a complete 15-17 minute documentary package with fact-checked script, professional voiceover, and copyright-safe media assets.

## ✨ What's New (2025)

- 🎯 **Enhanced Google API Integration** - Copyright-safe image search with usage rights filtering
- 🎙️ **Professional Voiceover** - High-quality TTS with ElevenLabs integration
- 📺 **YouTube Algorithm Optimization** - Gemini-optimized scripts for maximum engagement
- 🎬 **Premium Documentary Style** - Netflix-quality storytelling with varied hook patterns
- 🔍 **Advanced Media Collection** - News images, stock footage, and targeted visual content
- ⚡ **Faster Processing** - Optimized pipeline with intelligent fallbacks

## 🚀 Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set up environment variables
cp .env.example .env
# Add your API keys (OpenAI, Google Custom Search, ElevenLabs, etc.)

# 3. Initialize database
python main.py --init-db

# 4. Run enhanced pipeline
python main.py --company "NVIDIA" --style documentary
```

## 🏗️ Enhanced Pipeline Architecture

**9-step professional documentary production pipeline:**

1. **🔍 Smart Discovery** - AI-powered search query generation with business intelligence
2. **🌐 Advanced Crawling** - Multi-source content extraction with rate limiting
3. **📊 Intelligent Extraction** - Fact and claim extraction with confidence scoring
4. **💾 Structured Storage** - PostgreSQL database with relationship mapping
5. **✅ Comprehensive Fact-Checking** - Multi-source verification with confidence metrics
6. **📝 Premium Script Generation** - YouTube-optimized documentary scripts with varied hooks
7. **🎤 Professional Voiceover** - High-quality TTS with timeline synchronization
8. **🎬 Enhanced Media Collection** - Copyright-safe images, news footage, and B-roll
9. **📦 Complete Production Package** - DaVinci Resolve timeline with all assets

## 📦 Professional Production Package

### 🎬 **Video Production Files**
- **`timeline.csv`** - DaVinci Resolve timeline with precise timing
- **`script.md`** - Professional documentary script (2400-2600 words)
- **`voiceover/`** - High-quality audio files for each section
- **`shot_list.csv`** - B-roll suggestions with timing

### 📊 **Research & Verification**
- **`fact_check_report.md`** - Comprehensive claim verification
- **`research_report.md`** - Source analysis and findings
- **`youtube_optimization.json`** - SEO titles, thumbnails, keywords

### 🎨 **Media Assets**
- **`media/`** - Copyright-safe images and footage
- **`media_index.json`** - Asset mapping with attribution
- **News coverage images** - Recent company coverage
- **Stock B-roll footage** - Professional background content
- **Targeted visuals** - CEO photos, headquarters, products

## 🎬 Documentary Styles

**Premium documentary styles optimized for YouTube:**

- **`documentary`** - Netflix-quality authoritative storytelling with emotional beats
- **`investigative`** - Mystery-driven narrative with shocking revelations  
- **`biographical`** - Character-focused human interest stories
- **`business_analysis`** - Wall Street-style strategic analysis

## 🔧 API Configuration

### **Required APIs**
- **OpenAI API** - GPT-4 for research and script generation
- **Google Custom Search API** - Copyright-safe image search
- **Serper API** - Web search and news discovery

### **Enhanced Features (Optional)**
- **ElevenLabs API** - Professional voiceover generation
- **Unsplash API** - High-quality stock photography
- **Pexels API** - Stock videos and additional imagery

### **Google Setup Guide**
1. Enable Custom Search API in Google Cloud Console
2. Create a Custom Search Engine at [cse.google.com](https://cse.google.com)
3. Configure usage rights filtering for copyright compliance
4. Add API key and Search Engine ID to `.env`

## 🤖 AI Models & Performance

### **Hybrid Architecture**
- **Cloud Models** - OpenAI GPT-4 for complex reasoning and script generation
- **Local Fallbacks** - Ollama models for offline processing and cost optimization
- **Specialized APIs** - ElevenLabs for professional voiceover quality

### **Performance Optimizations**
- **Intelligent Caching** - Reduces API calls and processing time
- **Batch Processing** - Efficient handling of multiple research tasks
- **Graceful Fallbacks** - Continues processing even if APIs are unavailable
- **Rate Limiting** - Respects API limits and prevents throttling

### **Quality Assurance**
- **Multi-source Verification** - Cross-references claims across sources
- **Confidence Scoring** - Rates reliability of extracted information
- **Copyright Compliance** - Ensures all media has proper usage rights

## 📊 Usage Examples

### **Full Production Pipeline**
```bash
# Complete documentary package
python main.py --company "NVIDIA" --style documentary

# Investigative style with enhanced media
python main.py --company "Meta" --style investigative --max-sources 100

# Business analysis focus
python main.py --company "Tesla" --style business_analysis
```

### **Development & Testing**
```bash
# Test Google API configuration
python verify_google_config.py

# Test individual components
python test_components.py test-script --company-slug nvidia
python test_components.py test-media --keywords "AI,graphics,gaming"

# Skip media for faster testing
python main.py --company "Apple" --skip-media
```

### **Production Optimization**
```bash
# High-quality production run
python main.py --company "OpenAI" --style documentary --target-words 2500

# Fast processing for drafts
python main.py --company "Spotify" --style documentary --max-sources 25
```

## 🎯 Output Quality

**Professional documentary standards:**
- **15-17 minute runtime** (2400-2600 words)
- **Netflix-quality storytelling** with emotional beats
- **Copyright-compliant media** with proper attribution
- **Professional voiceover** ready for immediate use
- **DaVinci Resolve integration** for seamless editing

## 🚀 Recent Enhancements

- ✅ **Fixed repetitive hook patterns** - No more "What if I told you..." 
- ✅ **Google Images integration** - Copyright-safe visual content
- ✅ **Enhanced media collection** - News coverage and targeted imagery
- ✅ **Professional voiceover** - High-quality TTS with timing
- ✅ **YouTube optimization** - Algorithm-friendly scripts and metadata