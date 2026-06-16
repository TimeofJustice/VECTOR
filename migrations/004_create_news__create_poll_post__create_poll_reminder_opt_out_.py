"""Peewee migrations -- 004_create_news__create_poll_post__create_poll_reminder_opt_out_.py.

Some examples (model - class or model name)::

    > Model = migrator.orm['table_name']            # Return model in current state by name
    > Model = migrator.ModelClass                   # Return model in current state by name

    > migrator.sql(sql)                             # Run custom SQL
    > migrator.run(func, *args, **kwargs)           # Run python function with the given args
    > migrator.create_model(Model)                  # Create a model (could be used as decorator)
    > migrator.remove_model(model, cascade=True)    # Remove a model
    > migrator.add_fields(model, **fields)          # Add fields to a model
    > migrator.change_fields(model, **fields)       # Change fields
    > migrator.remove_fields(model, *field_names, cascade=True)
    > migrator.rename_field(model, old_field_name, new_field_name)
    > migrator.rename_table(model, new_table_name)
    > migrator.add_index(model, *col_names, unique=False)
    > migrator.add_not_null(model, *field_names)
    > migrator.add_default(model, field_name, default)
    > migrator.add_constraint(model, name, sql)
    > migrator.drop_index(model, *col_names)
    > migrator.drop_not_null(model, *field_names)
    > migrator.drop_constraints(model, *constraints)

"""

from contextlib import suppress

import peewee as pw
from peewee_migrate import Migrator


with suppress(ImportError):
    import playhouse.postgres_ext as pw_pext


def migrate(migrator: Migrator, database: pw.Database, *, fake=False):
    """Write your migrations here."""
    
    migrator.add_fields(
        'guildsettings',

        news_category_id=pw.BigIntegerField(null=True),
        news_channel_id=pw.BigIntegerField(null=True))

    @migrator.create_model
    class News(pw.Model):
        channel_id = pw.BigIntegerField(primary_key=True)
        guild_id = pw.BigIntegerField(index=True)
        role_id = pw.BigIntegerField()
        name = pw.TextField()
        description = pw.TextField(null=True)
        restricted_role_id = pw.BigIntegerField(null=True)
        read_only = pw.BooleanField(default=False)
        selector_channel_id = pw.BigIntegerField(null=True)
        selector_message_id = pw.BigIntegerField(index=True, null=True)
        created_at = pw.DateTimeField()

        class Meta:
            table_name = "news"

    @migrator.create_model
    class PollPost(pw.Model):
        id = pw.AutoField()
        recurring_poll_id = pw.IntegerField(null=True)
        guild_id = pw.BigIntegerField(index=True)
        channel_id = pw.BigIntegerField()
        poll_message_id = pw.BigIntegerField(index=True)
        tracking_message_id = pw.BigIntegerField()
        question = pw.TextField()
        closes_at = pw.DateTimeField(null=True)
        reminder_sent = pw.BooleanField(default=False)
        created_at = pw.DateTimeField()

        class Meta:
            table_name = "pollpost"

    @migrator.create_model
    class PollReminderOptOut(pw.Model):
        id = pw.AutoField()
        user_id = pw.BigIntegerField(unique=True)
        created_at = pw.DateTimeField()

        class Meta:
            table_name = "pollreminderoptout"

    @migrator.create_model
    class RecurringPoll(pw.Model):
        id = pw.AutoField()
        guild_id = pw.BigIntegerField(index=True)
        channel_id = pw.BigIntegerField()
        question = pw.TextField()
        options = pw.TextField()
        interval_days = pw.IntegerField()
        duration_hours = pw.IntegerField(default=0)
        allow_multiselect = pw.BooleanField(default=False)
        remind = pw.BooleanField(default=False)
        created_by = pw.BigIntegerField()
        event_date = pw.DateField(null=True)
        next_run = pw.DateTimeField(index=True)
        created_at = pw.DateTimeField()

        class Meta:
            table_name = "recurringpoll"


def rollback(migrator: Migrator, database: pw.Database, *, fake=False):
    """Write your rollback migrations here."""
    
    migrator.remove_fields('guildsettings', 'news_category_id', 'news_channel_id')

    migrator.remove_model('recurringpoll')

    migrator.remove_model('pollreminderoptout')

    migrator.remove_model('pollpost')

    migrator.remove_model('news')
