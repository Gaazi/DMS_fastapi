from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from datetime import date
import traceback

# Internal Imports
from app.core.database import get_session
from app.models import Institution, Student, Admission, Course

from app.utils.context import TemplateResponse
from datetime import date as dt_date

router = APIRouter()

@router.api_route("/{institution_slug}/join/", methods=["GET", "POST"], response_class=HTMLResponse, name="public_admission")
async def public_admission(request: Request, institution_slug: str, session: Session = Depends(get_session)):
    """
    عوام کے لیے اوپن داخلہ فارم (بغیر لاگ ان) - 1:1 جینگو ریفیکٹر
    """
    institution = session.exec(select(Institution).where(Institution.slug == institution_slug)).first()
    if not institution:
        return HTMLResponse(content="ادارہ نہیں ملا۔", status_code=404)
    
    from app.schemas.forms import PublicAdmissionSchema
    from pydantic import ValidationError

    if request.method == "POST":
        form_data = await request.form()
        data = dict(form_data)
        
        try:
            # Validate input data
            validated_data = PublicAdmissionSchema(**data)
            
            # 1. Start Transaction
            with session.begin_nested() as nested:
                # 2. Create Student
                student = Student(
                    name=validated_data.name,
                    father_name=validated_data.father_name,
                    mobile=validated_data.mobile,
                    address=validated_data.address,
                    inst_id=institution.id,
                    is_active=False,
                    admission_date=dt_date.today()
                )
                session.add(student)
                session.flush()
                
                # 3. Create Enrollment (if course selected)
                if validated_data.course_id:
                    new_admission = Admission(
                        student_id=student.id,
                        course_id=validated_data.course_id,
                        status='pending',
                        admission_date=dt_date.today(),
                        inst_id=institution.id
                    )
                    session.add(new_admission)
                
            session.commit()
            return await TemplateResponse.render("dms/public_admission_success.html", request, session, {"institution": institution})
            
        except ValidationError as e:
            errors = {err['loc'][0]: err['msg'] for err in e.errors()}
            courses = session.exec(select(Course).where(Course.inst_id == institution.id, Course.is_active == True)).all()
            return await TemplateResponse.render("dms/public_admission.html", request, session, {
                "institution": institution,
                "courses": courses,
                "errors": errors,
                "form_data": data
            })
            
        except Exception as e:
            session.rollback()
            return await TemplateResponse.render("dms/public_admission.html", request, session, {
                "institution": institution,
                "courses": session.exec(select(Course).where(Course.inst_id == institution.id)).all(),
                "error_msg": str(e)
            })
            
    courses = session.exec(select(Course).where(Course.inst_id == institution.id, Course.is_active == True)).all()
    return await TemplateResponse.render("dms/public_admission.html", request, session, {
        "institution": institution,
        "courses": courses,
        "form": None
    })

