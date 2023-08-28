from django.db.models import Manager

from .exceptions import SNOMEDCTModelOperationNotPermitted


class SNOMEDCTModelManager(Manager):
    def create(self, *args, **kwargs):
        raise SNOMEDCTModelOperationNotPermitted

    # def bulk_create(self, *args, **kwargs):
    #     raise SNOMEDCTModelOperationNotPermitted

    def get_or_create(self, *args, **kwargs):
        raise SNOMEDCTModelOperationNotPermitted

    def update_or_create(self, *args, **kwargs):
        raise SNOMEDCTModelOperationNotPermitted

    def delete(self, *args, **kwargs):
        raise SNOMEDCTModelOperationNotPermitted

    def update(self, *args, **kwargs):
        raise SNOMEDCTModelOperationNotPermitted
