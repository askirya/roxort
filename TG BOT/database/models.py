from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, DateTime, Enum
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import enum

Base = declarative_base()

class UserRole(enum.Enum):
    USER = "user"
    ADMIN = "admin"

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True)
    username = Column(String, nullable=True)
    phone_number = Column(String, nullable=True)
    balance = Column(Float, default=0.0)
    rating = Column(Float, default=5.0)
    role = Column(Enum(UserRole), default=UserRole.USER)
    registered_at = Column(DateTime, default=datetime.utcnow)
    
class PhoneListing(Base):
    __tablename__ = 'phone_listings'
    
    id = Column(Integer, primary_key=True)
    seller_id = Column(Integer, ForeignKey('users.id'))
    service = Column(String)
    duration = Column(Integer)  # в часах
    price = Column(Float)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Transaction(Base):
    __tablename__ = 'transactions'
    
    id = Column(Integer, primary_key=True)
    buyer_id = Column(Integer, ForeignKey('users.id'))
    seller_id = Column(Integer, ForeignKey('users.id'))
    listing_id = Column(Integer, ForeignKey('phone_listings.id'))
    amount = Column(Float)
    status = Column(String)  # pending, completed, disputed, cancelled
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

class Dispute(Base):
    __tablename__ = 'disputes'
    
    id = Column(Integer, primary_key=True)
    transaction_id = Column(Integer, ForeignKey('transactions.id'))
    initiator_id = Column(Integer, ForeignKey('users.id'))
    description = Column(String)
    status = Column(String)  # open, resolved, closed
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)

class Review(Base):
    __tablename__ = 'reviews'
    
    id = Column(Integer, primary_key=True)
    transaction_id = Column(Integer, ForeignKey('transactions.id'))
    reviewer_id = Column(Integer, ForeignKey('users.id'))
    reviewed_id = Column(Integer, ForeignKey('users.id'))
    rating = Column(Integer)  # от 1 до 5
    comment = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow) 