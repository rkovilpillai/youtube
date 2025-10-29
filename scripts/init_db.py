"""
Database Initialization Script
Creates all database tables and optionally seeds with sample data.
"""
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from api.database import init_db, SessionLocal
from api.models import Campaign, Keyword, CampaignStatus, KeywordType, KeywordSource, KeywordStatus


def create_sample_data():
    """Create sample campaign and keywords for testing."""
    db = SessionLocal()
    
    try:
        # Check if sample data already exists
        existing = db.query(Campaign).filter(Campaign.name == "Sample Tech Campaign").first()
        if existing:
            print("âœ… Sample data already exists")
            return
        
        print("📝 Creating sample data...")
        
        # Create sample campaign
        sample_campaign = Campaign(
            name="Sample Tech Campaign",
            brand_name="TechCo",
            brand_url="https://www.techco.com",
            product_category="Consumer Electronics",
            campaign_goal="Product Awareness",
            campaign_definition="Launch campaign for new smartphone targeting tech enthusiasts aged 25-40. Focus on innovation, performance, and camera quality.",
            brand_context_text="Brand values: Innovation, Quality, User Experience. Tone: Professional yet approachable.",
            status=CampaignStatus.DRAFT
        )
        
        db.add(sample_campaign)
        db.commit()
        db.refresh(sample_campaign)
        
        # Create sample keywords
        sample_keywords = [
            # Core keywords
            {"keyword": "smartphone review", "type": KeywordType.CORE, "score": 0.95},
            {"keyword": "tech unboxing", "type": KeywordType.CORE, "score": 0.90},
            {"keyword": "mobile phone", "type": KeywordType.CORE, "score": 0.88},
            
            # Long-tail keywords
            {"keyword": "best budget smartphone 2024", "type": KeywordType.LONG_TAIL, "score": 0.85},
            {"keyword": "flagship phone camera test", "type": KeywordType.LONG_TAIL, "score": 0.82},
            
            # Related topics
            {"keyword": "mobile accessories", "type": KeywordType.RELATED, "score": 0.75},
            {"keyword": "phone cases", "type": KeywordType.RELATED, "score": 0.70},
            
            # Intent-based
            {"keyword": "how to choose a smartphone", "type": KeywordType.INTENT_BASED, "score": 0.80},
            {"keyword": "smartphone buying guide", "type": KeywordType.INTENT_BASED, "score": 0.78},
        ]
        
        for kw_data in sample_keywords:
            keyword = Keyword(
                campaign_id=sample_campaign.id,
                keyword=kw_data["keyword"],
                keyword_type=kw_data["type"],
                relevance_score=kw_data["score"],
                source=KeywordSource.AI_GENERATED,
                status=KeywordStatus.ACTIVE
            )
            db.add(keyword)
        
        db.commit()
        
        print(f"✅ Created sample campaign: {sample_campaign.name}")
        print(f"✅ Created {len(sample_keywords)} sample keywords")
        print(f"📝 Campaign ID: {sample_campaign.id}")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error creating sample data: {e}")
    finally:
        db.close()


def main():
    """Main initialization function."""
    print("🚀 Initializing YouTube Contextual Product Pipeline Database...")
    print()
    
    # Initialize database (create tables)
    init_db()
    
    # Ask if user wants sample data
    print()
    response = input("Would you like to create sample data for testing? (y/n): ").lower()
    
    if response == 'y':
        create_sample_data()
    
    print()
    print("✅ Database initialization complete!")
    print()
    print("Next steps:")
    print("1. Start the backend API: python -m uvicorn api.main:app --reload --port 8000")
    print("2. Start the frontend: streamlit run frontend/app.py")


if __name__ == "__main__":
    main()
