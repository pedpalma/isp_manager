# Importa os três models para garantir registro no metadata do SQLAlchemy
# (necessário para resolver a ForeignKey app_user -> user_group em tempo de
# configuração dos mappers) independentemente da ordem de import dos módulos.

from app.domains.auth.models.app_user import AppUser
from app.domains.auth.models.app_user_session import AppUserSession
from app.domains.auth.models.user_group import UserGroup

__all__ = ["AppUser", "AppUserSession", "UserGroup"]
