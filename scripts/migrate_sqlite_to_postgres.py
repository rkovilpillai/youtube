import sys
import uuid
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from api.models import Campaign, Base

SQLITE_URL = "sqlite:///youtube_pipeline.db"  # adjust path if needed
POSTGRES_URL = "postgresql://youtube_db_hs49_user:aLiMh4zlh84AlQTOblMLxwIYN3ImLIXE@dpg-d418q615pdvs73c1g6vg-a.oregon-postgres.render.com/youtube_db_hs49"  # Render credentials

sqlite_engine = create_engine(SQLITE_URL)
postgres_engine = create_engine(POSTGRES_URL)

SQLiteSession = sessionmaker(bind=sqlite_engine)
PostgresSession = sessionmaker(bind=postgres_engine)

def migrate(limit=5):
    Base.metadata.create_all(bind=postgres_engine)
    with SQLiteSession() as s_src, PostgresSession() as s_dst:
        campaigns = s_src.query(Campaign).limit(limit).all()
        for c in campaigns:
            # refresh IDs if you don’t want collisions
            new_id = str(uuid.uuid4())
            clone = Campaign(
                id=new_id,
                name=c.name,
                brand_name=c.brand_name,
                brand_url=c.brand_url,
                product_category=c.product_category,
                campaign_goal=c.campaign_goal,
                campaign_definition=c.campaign_definition,
                brand_context_text=c.brand_context_text,
                status=c.status,
                created_at=c.created_at,
                updated_at=c.updated_at,
                audience_intent=c.audience_intent,
                audience_persona=c.audience_persona,
                tone_profile=c.tone_profile,
                emotion_guidance=c.emotion_guidance,
                interest_guidance=c.interest_guidance,
                guardrail_terms=c.guardrail_terms,
                inspiration_links=c.inspiration_links,
                primary_language=c.primary_language,
                primary_market=c.primary_market,
                avg_view_count=c.avg_view_count,
                avg_like_count=c.avg_like_count,
                avg_comment_count=c.avg_comment_count,
            )
            s_dst.add(clone)
        s_dst.commit()

if __name__ == "__main__":
    migrate(limit=2)  # adjust how many to migrate
