from django.apps import AppConfig


class DmsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'dms'

    def ready(self):
        # Import inside the ready method to avoid circular imports
        from django.db.models.signals import post_migrate
        from .logic.groups import RoleGroupManager
        
        def create_default_groups(sender, **kwargs):
            RoleGroupManager.setup_groups()
            
        post_migrate.connect(create_default_groups, sender=self)
