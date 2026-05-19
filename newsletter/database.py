from datetime import date
from sqlalchemy import create_engine, Column, Integer, String, Text, Date, DateTime
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.sql import func

engine = create_engine("sqlite:///newsletter.db")
Session = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


class Article(Base):
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    edition_date = Column(Date, nullable=False, index=True)
    title = Column(String(500), nullable=False)
    source = Column(String(200))
    original_url = Column(String(1000))
    company = Column(String(300))
    summary = Column(Text)
    sales_opportunity = Column(Text)
    saas_categories = Column(Text)
    talking_points = Column(Text)
    created_at = Column(DateTime, server_default=func.now())


def init_db():
    Base.metadata.create_all(engine)


def get_articles_for_date(edition_date: date) -> list[Article]:
    with Session() as session:
        return (
            session.query(Article)
            .filter(Article.edition_date == edition_date)
            .order_by(Article.id)
            .all()
        )


def get_available_dates() -> list[date]:
    with Session() as session:
        rows = (
            session.query(Article.edition_date)
            .distinct()
            .order_by(Article.edition_date.desc())
            .all()
        )
        return [r[0] for r in rows]


def save_articles(articles: list[dict], edition_date: date):
    with Session() as session:
        # Clear existing articles for this date before saving
        session.query(Article).filter(Article.edition_date == edition_date).delete()
        for a in articles:
            session.add(Article(edition_date=edition_date, **a))
        session.commit()
