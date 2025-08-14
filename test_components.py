#!/usr/bin/env python3
"""
Test individual components of the AI Research Pipeline
"""

import asyncio
import click
from src.agents.scriptwriter import ScriptwriterAgent
from src.agents.fact_checker import FactCheckerAgent
from src.media.pipeline import MediaPipeline
from pathlib import Path

@click.group()
def cli():
    """Test individual pipeline components"""
    pass

@cli.command()
@click.option('--company-slug', required=True, help='Company slug to generate script for')
@click.option('--style', default='storytelling', help='Script style')
async def test_script(company_slug: str, style: str):
    """Test script generation for a company"""
    print(f"Testing script generation for {company_slug}...")
    
    scriptwriter = ScriptwriterAgent()
    result = await scriptwriter.process({
        "company_slug": company_slug,
        "style": style,
        "target_words": 1600
    })
    
    if result.get("error"):
        print(f"❌ Error: {result['error']}")
        return
    
    print(f"✅ Script generated!")
    print(f"📝 Word count: {result.get('word_count', 0)}")
    print(f"⏱️  Estimated duration: {result.get('estimated_duration', 0)} minutes")
    print(f"🎬 B-roll suggestions: {len(result.get('broll_suggestions', []))}")
    
    # Save to file
    output_file = f"{company_slug}_script.md"
    with open(output_file, 'w') as f:
        f.write(result.get('script', ''))
    print(f"💾 Script saved to: {output_file}")

@cli.command()
@click.option('--company-slug', required=True, help='Company slug to fact-check')
async def test_factcheck(company_slug: str):
    """Test fact-checking for a company"""
    print(f"Testing fact-checking for {company_slug}...")
    
    fact_checker = FactCheckerAgent()
    result = await fact_checker.process({"company_slug": company_slug})
    
    if result.get("error"):
        print(f"❌ Error: {result['error']}")
        return
    
    print(f"✅ Fact-checking completed!")
    print(f"📊 Total claims: {result.get('total_claims', 0)}")
    print(f"✅ Verified claims: {result.get('verified_claims', 0)}")
    print(f"⚠️  Flagged claims: {result.get('flagged_claims', 0)}")
    
    # Save report
    report_file = f"{company_slug}_factcheck.md"
    with open(report_file, 'w') as f:
        f.write(result.get('report', ''))
    print(f"💾 Report saved to: {report_file}")

@cli.command()
@click.option('--keywords', required=True, help='Comma-separated keywords for media search')
@click.option('--output-dir', default='./test_media', help='Output directory for media')
async def test_media(keywords: str, output_dir: str):
    """Test media collection"""
    keyword_list = [k.strip() for k in keywords.split(',')]
    print(f"Testing media collection for keywords: {keyword_list}")
    
    media_pipeline = MediaPipeline()
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    result = await media_pipeline.collect_media_for_script({
        "company_name": "Test Company",
        "broll_suggestions": [
            {
                "keywords": keyword_list,
                "description": "Test media collection",
                "timestamp": "00:30",
                "duration": 10
            }
        ]
    }, output_path)
    
    print(f"✅ Media collection completed!")
    print(f"📊 Total collected: {result.get('total_collected', 0)}")
    print(f"💾 Successfully downloaded: {result.get('successfully_downloaded', 0)}")
    print(f"📁 Assets directory: {result.get('assets_directory', '')}")

def run_async_command(coro):
    """Helper to run async commands"""
    asyncio.run(coro)

# Make commands async-compatible
test_script.callback = lambda *args, **kwargs: run_async_command(test_script.callback(*args, **kwargs))
test_factcheck.callback = lambda *args, **kwargs: run_async_command(test_factcheck.callback(*args, **kwargs))
test_media.callback = lambda *args, **kwargs: run_async_command(test_media.callback(*args, **kwargs))

if __name__ == "__main__":
    cli()