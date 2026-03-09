from peewee import Model

from services.database import db_proxy


class ModelBase(Model):
    class Meta:
        database = db_proxy
