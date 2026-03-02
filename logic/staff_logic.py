from sqlalchemy.orm import Session
from models import StaffAdvance, Staff
from typing import List, Optional
from datetime import date as dt_date

class StaffAdvanceService:
    @staticmethod
    def get_all_advances(session: Session, limit: int = 100) -> List[StaffAdvance]:
        """Fetch all staff advances records."""
        return session.query(StaffAdvance).order_by(StaffAdvance.date.desc()).limit(limit).all()

    @staticmethod
    def create_advance(session: Session, staff_id: int, amount: float, date: Optional[dt_date] = None) -> StaffAdvance:
        """Create a new staff advance record."""
        new_advance = StaffAdvance(
            staff_id=staff_id,
            amount=amount,
            date=date or dt_date.today(),
            is_adjusted=False
        )
        session.add(new_advance)
        session.commit()
        session.refresh(new_advance)
        return new_advance

    @staticmethod
    def adjust_advance(session: Session, advance_id: int) -> bool:
        """Mark a specific advance as adjusted."""
        advance = session.get(StaffAdvance, advance_id)
        if advance:
            advance.is_adjusted = True
            session.commit()
            return True
        return False

    @staticmethod
    def delete_advance(session: Session, advance_id: int) -> bool:
        """Delete an advance record."""
        advance = session.get(StaffAdvance, advance_id)
        if advance:
            session.delete(advance)
            session.commit()
            return True
        return False
