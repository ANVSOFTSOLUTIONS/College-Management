from fastapi import APIRouter, Depends

from app.api.deps import CurrentUser, require_roles
from app.modules.lesson_plans import service
from app.modules.lesson_plans.service import AddTopicsIn, LessonPlan, Progress, TopicUpdate
from app.modules.parents import service as parents

router = APIRouter(prefix="/lesson-plans", tags=["lesson plans"])
portal_router = APIRouter(prefix="/me/parent/children", tags=["parent portal"])

_staff = require_roles("admin", "teacher")


@router.get("/progress", response_model=list[Progress])
async def progress(current_user: CurrentUser = Depends(_staff)) -> list[Progress]:
    """Syllabus covered per batch and subject: all for admins, the department for HODs, own subjects for faculty."""
    return await service.progress(current_user)


@router.get("", response_model=LessonPlan)
async def plan(class_id: str, subject_id: str, current_user: CurrentUser = Depends(_staff)) -> LessonPlan:
    return await service.plan(current_user, class_id, subject_id)


@router.post("", response_model=LessonPlan)
async def add_topics(payload: AddTopicsIn, current_user: CurrentUser = Depends(_staff)) -> LessonPlan:
    return await service.add_topics(current_user, payload)


@router.put("/topics/{topic_id}", response_model=LessonPlan)
async def update_topic(topic_id: str, payload: TopicUpdate, current_user: CurrentUser = Depends(_staff)) -> LessonPlan:
    return await service.update_topic(current_user, topic_id, payload)


@router.delete("/topics/{topic_id}", response_model=LessonPlan)
async def delete_topic(topic_id: str, current_user: CurrentUser = Depends(_staff)) -> LessonPlan:
    return await service.delete_topic(current_user, topic_id)


@portal_router.get("/{student_id}/syllabus", response_model=list[LessonPlan])
async def child_syllabus(student_id: str, current_user: CurrentUser = Depends(require_roles("parent", "student"))) -> list[LessonPlan]:
    return await service.student_syllabus(await parents.child_row(current_user, student_id))
