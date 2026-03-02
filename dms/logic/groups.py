from django.contrib.auth.models import Group
from .roles import Role

class RoleGroupManager:
    """
    Manages the translation of DMS Roles into Django Auth Groups.
    Class-based structure defines clear boundaries and makes it easier to test or inherit.
    """

    # Maps the `Staff.Role` choices to explicit Django Group names
    MAPPING = {
        Role.PRESIDENT.value: "President",
        Role.VICE_PRESIDENT.value: "Vice President",
        Role.GENERAL_SECRETARY.value: "General Secretary",
        Role.JOINT_SECRETARY.value: "Joint Secretary",
        Role.COMMITTEE_MEMBER.value: "Committee Member",
        Role.ADMIN.value: "Administrator",
        Role.ACCOUNTANT.value: "Accountant",
        Role.ACADEMIC_HEAD.value: "Education Head",
        Role.IMAM.value: "Imam",
        Role.MUEZZIN.value: "Muezzin",
        Role.TEACHER.value: "Teacher",
        Role.SUPPORT.value: "Support Staff",
        Role.VOLUNTEER.value: "Volunteer",
    }

    @classmethod
    def setup_groups(cls):
        """
        Creates Django Groups based on the Role definitions if they don't exist.
        This can be called during post_migrate signal to ensure groups always exist.
        """
        for _, group_name in cls.MAPPING.items():
            Group.objects.get_or_create(name=group_name)

    @classmethod
    def assign_user(cls, user, role_value):
        """
        Assigns a user to the correct Django Group based on their staff role.
        Removes them from other role-based groups to prevent overlapping basic roles.
        """
        if not user:
            return
            
        target_group_name = cls.MAPPING.get(role_value)
        if not target_group_name:
            return
            
        # Ensure group exists before assigning
        target_group, _ = Group.objects.get_or_create(name=target_group_name)
        
        # Remove from other managed role groups so they only have one primary role group
        managed_group_names = cls.MAPPING.values()
        groups_to_remove = user.groups.filter(name__in=managed_group_names).exclude(name=target_group_name)
        if groups_to_remove.exists():
            user.groups.remove(*groups_to_remove)
            
        # Add to the new target group if not already a member
        if not user.groups.filter(name=target_group_name).exists():
            user.groups.add(target_group)

    @classmethod
    def remove_user(cls, user):
        """
        Removes a user from all role-based groups (e.g., when their Staff profile is deleted).
        """
        if not user:
            return
            
        managed_group_names = cls.MAPPING.values()
        groups_to_remove = user.groups.filter(name__in=managed_group_names)
        if groups_to_remove.exists():
            user.groups.remove(*groups_to_remove)
