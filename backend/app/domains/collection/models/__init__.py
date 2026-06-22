# Importa os models para que o mapper do SQLAlchemy enxergue-os.

from app.domains.collection.models.collection_job import CollectionJob
from app.domains.collection.models.collection_log import CollectionLog
from app.domains.collection.models.pending_onu import PendingOnu

__all__ = ["CollectionJob", "CollectionLog", "PendingOnu"]
