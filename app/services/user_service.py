from app.models import User
from app.repositories import UserRepository


class UserService:
    def __init__(self, user_repo: UserRepository):
        self._repo = user_repo

    def register_user(self, name: str, phone: str) -> User:
        user = User(name=name, phone=phone)
        return self._repo.add(user)
