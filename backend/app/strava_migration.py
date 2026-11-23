from .database import Base
from .models import strava


def migrate_strava(engine):
    """Create only the new tables; never alter or delete existing data."""
    Base.metadata.create_all(bind=engine, tables=[
        strava.StravaConnection.__table__, strava.StravaOAuthState.__table__,
        strava.StravaActivity.__table__, strava.StravaTask.__table__,
    ], checkfirst=True)