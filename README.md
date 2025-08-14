# AI Research & Script Generator

Automated research and script generation for company story videos (10-15 minutes). Input a company name → get a complete video production package with fact-checked script, B-roll suggestions, and licensed media assets.

## 🚀 Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set up environment variables
cp .env.example .env
# Edit .env with your API keys

# 3. Initialize database
python main.py --init-db

# 4. Run full pipeline
python main.py --company "Netflix" --style storytelling
```

## 🏗️ Architecture

The pipeline consists of 8 integrated steps:

1. **Discovery** - Multi-source web search (Serper, Bing)
2. **Crawling** - Rate-limited content extraction
3. **Extraction** - AI-powered fact extraction with confidence scoring
4. **Database Storage** - Structured data storage with PostgreSQL
5. **Fact-Checking** - Cross-reference verification with 2+ sources
6. **Script Generation** - YouTube-ready scripts with 3 style options
7. **Media Collection** - Licensed assets from Unsplash, Pexels, Wikimedia
8. **Output Generation** - Complete production package

## 📦 Complete Output Package

- `script.md` - Voiceover-ready script with timestamps and citations
- `shot_list.csv` - B-roll suggestions mapped to script sections
- `fact_check_report.md` - Verification status of all claims
- `research_report.md` - Raw research findings and sources
- `thumbnail_concepts.txt` - Title and thumbnail ideas
- `assets/` - Downloaded media files with license information
- `assets/media_index.json` - Media mapping to script sections

## 🎬 Script Styles

Choose from 3 optimized styles:

- `storytelling` - Narrative approach with character development
- `documentary` - Authoritative, informative tone
- `energetic` - Fast-paced YouTuber style

## 🔧 API Keys Required

- **OpenAI API** - For script generation and fact extraction
- **Serper API** - For web search (recommended)
- **Unsplash API** - For stock photos (optional)
- **Pexels API** - For photos and videos (optional)

## 📊 Example Usage

```bash
# Full pipeline with custom style
python main.py --company "Tesla" --style documentary --max-sources 50

# Skip media collection for faster processing
python main.py --company "Apple" --skip-media

# Test individual components
python test_components.py test-script --company-slug tesla
python test_components.py test-factcheck --company-slug tesla
python test_components.py test-media --keywords "electric car,tesla,elon musk"
```