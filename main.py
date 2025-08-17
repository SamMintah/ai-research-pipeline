#!/usr/bin/env python3
"""
AI Research & Script Generator
Main entry point for the research pipeline
"""

import asyncio
import click
from pathlib import Path
from src.pipeline import ResearchPipeline
from src.database import create_tables

@click.command()
@click.option('--company', help='Company name to research')
@click.option('--output-dir', default='./output', help='Output directory')
@click.option('--max-sources', default=30, help='Maximum sources to crawl')
@click.option('--style', default='storytelling', type=click.Choice(['documentary', 'energetic', 'storytelling']), help='Script style')
@click.option('--skip-media', is_flag=True, help='Skip media collection')
@click.option('--init-db', is_flag=True, help='Initialize database tables')
def main(company: str, output_dir: str, max_sources: int, style: str, skip_media: bool, init_db: bool):
    """Run AI research pipeline for company story videos"""
    
    if init_db:
        print("Initializing database...")
        create_tables()
        print("Database initialized successfully!")
        return
    
    if not company:
        ctx = click.get_current_context()
        click.echo("Error: Missing option '--company' is required when not using '--init-db'.")
        click.echo(ctx.get_help())
        ctx.exit(1)

    print(f"🔍 Starting AI Research Pipeline for: {company}")
    print(f"📁 Output directory: {output_dir}")
    print(f"🌐 Max sources: {max_sources}")
    print(f"🎬 Script style: {style}")
    if skip_media:
        print("⏭️  Skipping media collection")
    print("-" * 50)
    
    # Run the pipeline
    pipeline = ResearchPipeline()
    results = asyncio.run(pipeline.run(company, output_dir))
    
    if "error" in results:
        print(f"❌ Pipeline failed: {results['error']}")
        return
    
    print("\n✅ Pipeline completed successfully!")
    print(f"📊 Results saved to: {results['output_dir']}")
    
    # Print summary
    steps = results.get("pipeline_steps", {})
    if "discovery" in steps:
        print(f"🔍 Sources discovered: {steps['discovery'].get('total_found', 0)}")
    if "crawling" in steps:
        print(f"📄 Sources crawled: {len(steps['crawling'])}")
    if "extraction" in steps:
        print(f"💡 Facts extracted: {len(steps['extraction'])}")
    if "fact_checking" in steps:
        fc = steps['fact_checking']
        print(f"✅ Claims verified: {fc.get('verified_claims', 0)}/{fc.get('total_claims', 0)}")
    if "script_generation" in steps:
        sg = steps['script_generation']
        if not sg.get('error'):
            print(f"📝 Script generated: {sg.get('word_count', 0)} words ({sg.get('estimated_duration', 0)} min)")
    if "voiceover_generation" in steps:
        vg = steps['voiceover_generation']
        if not vg.get('error'):
            print(f"🎤 Voiceover generated: {vg.get('audio_files_generated', 0)} audio files")
    if "media_collection" in steps:
        mc = steps['media_collection']
        print(f"🎬 Media assets: {mc.get('successfully_downloaded', 0)} files downloaded")

if __name__ == "__main__":
    main()
