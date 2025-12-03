import uuid
from django.db import models
from crum import get_current_request
from common.mixins import AuditModel


class BaseModel(AuditModel):
    id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
        primary_key=True
    )

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        request = get_current_request()

        if request and hasattr(request, 'profile') and request.profile:
            user = request.profile.user

            if self.__class__.__name__ != 'Profile':
                if self._state.adding and not self.created_by:
                    self.created_by = user
                self.updated_by = user

        super(BaseModel, self).save(*args, **kwargs)

    def __str__(self):
        return str(self.id)