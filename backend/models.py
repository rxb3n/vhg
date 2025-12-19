from sqlalchemy import Column, String, Integer, Float, DateTime, Text, JSON
from sqlalchemy.sql import func
from database import Base
import json


class AdGeneration(Base):
    __tablename__ = "ad_generations"

    id = Column(String, primary_key=True, index=True)
    product_image_url = Column(String)
    script_data = Column(JSON)
    status = Column(String, default="pending")  # pending, generating, completed, failed
    final_video_url = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class Clip(Base):
    __tablename__ = "clips"

    id = Column(String, primary_key=True, index=True)
    ad_id = Column(String, index=True)
    sequence_index = Column(Integer)
    role = Column(String, nullable=True)
    prompt = Column(Text)
    wan_job_id = Column(String, nullable=True)
    s3_url = Column(String, nullable=True)
    local_path = Column(String, nullable=True)
    duration = Column(Float, default=5.0)
    status = Column(String, default="pending")  # pending, generating, completed, failed
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "ad_id": self.ad_id,
            "sequence_index": self.sequence_index,
            "role": self.role,
            "prompt": self.prompt,
            "wan_job_id": self.wan_job_id,
            "s3_url": self.s3_url,
            "local_path": self.local_path,
            "duration": self.duration,
            "status": self.status
        }

