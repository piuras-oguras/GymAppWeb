from sqlalchemy import Column, Integer, String, DateTime
from database import Base
from datetime import datetime

class Pass(Base):
    __tablename__ = "passes"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    email = Column(String, index=True, nullable=False)
    pass_type = Column(String, nullable=False)
    purchase_date = Column(DateTime, default=datetime.utcnow)
