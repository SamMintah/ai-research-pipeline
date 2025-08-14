from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Text, JSON, ForeignKey, Date
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime

Base = declarative_base()

class Company(Base):
    __tablename__ = "companies"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    sources = relationship("Source", back_populates="company")
    claims = relationship("Claim", back_populates="company")
    media_assets = relationship("MediaAsset", back_populates="company")

class Source(Base):
    __tablename__ = "sources"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"))
    url = Column(Text)
    domain = Column(String)
    title = Column(Text)
    author = Column(String)
    published_at = Column(DateTime)
    content = Column(Text)
    license = Column(JSON)
    reliability = Column(Integer)  # 1-5 scale
    created_at = Column(DateTime, default=datetime.utcnow)
    
    company = relationship("Company", back_populates="sources")
    claim_sources = relationship("ClaimSource", back_populates="source")

class Claim(Base):
    __tablename__ = "claims"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"))
    claim = Column(Text, nullable=False)
    claim_date = Column(Date)
    subject = Column(String)
    predicate = Column(String)
    object = Column(String)
    confidence = Column(Float)
    corroboration_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    company = relationship("Company", back_populates="claims")
    claim_sources = relationship("ClaimSource", back_populates="claim")

class ClaimSource(Base):
    __tablename__ = "claim_sources"
    
    claim_id = Column(UUID(as_uuid=True), ForeignKey("claims.id"), primary_key=True)
    source_id = Column(UUID(as_uuid=True), ForeignKey("sources.id"), primary_key=True)
    quote = Column(Text)
    start_char = Column(Integer)
    end_char = Column(Integer)
    
    claim = relationship("Claim", back_populates="claim_sources")
    source = relationship("Source", back_populates="claim_sources")

class MediaAsset(Base):
    __tablename__ = "media_assets"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"))
    path = Column(String)
    source_url = Column(Text)
    width = Column(Integer)
    height = Column(Integer)
    license = Column(JSON)
    safe_for_use = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    company = relationship("Company", back_populates="media_assets")