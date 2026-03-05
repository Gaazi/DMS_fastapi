from app.admin.base import DMSModelView
from app.models.announcement import Announcement
from app.models.backup import SystemSnapshot

class AnnouncementAdmin(DMSModelView, model=Announcement):
    column_list = [Announcement.id, Announcement.title, Announcement.target_audience, Announcement.is_published, Announcement.created_at]
    column_searchable_list = [Announcement.title]
    category = "System"
    icon = "fa-solid fa-bullhorn"

class SystemSnapshotAdmin(DMSModelView, model=SystemSnapshot):
    column_list = [SystemSnapshot.id, SystemSnapshot.label, SystemSnapshot.backup_type, SystemSnapshot.created_at, SystemSnapshot.size]
    category = "System"
    icon = "fa-solid fa-database"
