"""
Use Cases - User profile management.
"""

from typing import Dict, Any
from src.domain.user_profile import UserProfile
from src.domain.profile_repository_interface import IProfileRepository


class CreateProfileUseCase:
    def __init__(self, repository: IProfileRepository):
        self.repository = repository

    def execute(self, **kwargs) -> Dict[str, Any]:
        try:
            profile = UserProfile(**kwargs)
            saved = self.repository.save(profile)
            return {'success': True, 'data': saved.to_dict()}
        except ValueError as e:
            return {'success': False, 'error': str(e)}
        except Exception as e:
            return {'success': False, 'error': f'Unexpected error: {str(e)}'}


class GetProfilesUseCase:
    def __init__(self, repository: IProfileRepository):
        self.repository = repository

    def execute(self) -> Dict[str, Any]:
        try:
            profiles = self.repository.get_all()
            return {
                'success': True,
                'total': len(profiles),
                'data': [p.to_dict() for p in profiles],
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}


class GetProfileByIdUseCase:
    def __init__(self, repository: IProfileRepository):
        self.repository = repository

    def execute(self, profile_id: int) -> Dict[str, Any]:
        try:
            profile = self.repository.get_by_id(profile_id)
            if profile:
                return {'success': True, 'data': profile.to_dict()}
            return {'success': False, 'error': 'Profile not found'}
        except Exception as e:
            return {'success': False, 'error': str(e)}


class UpdateProfileUseCase:
    def __init__(self, repository: IProfileRepository):
        self.repository = repository

    def execute(self, profile_id: int, **kwargs) -> Dict[str, Any]:
        try:
            existing = self.repository.get_by_id(profile_id)
            if not existing:
                return {'success': False, 'error': 'Profile not found'}
            for key, value in kwargs.items():
                if hasattr(existing, key) and value is not None:
                    setattr(existing, key, value)
            updated = self.repository.update(existing)
            return {'success': True, 'data': updated.to_dict()}
        except ValueError as e:
            return {'success': False, 'error': str(e)}
        except Exception as e:
            return {'success': False, 'error': f'Unexpected error: {str(e)}'}

