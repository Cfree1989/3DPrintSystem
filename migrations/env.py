import logging
from logging.config import fileConfig

from flask import current_app

from alembic import context

# Create the app and get db from it to ensure full initialization
from app import create_app # Assuming your factory is in app/__init__.py

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
logger = logging.getLogger('alembic.env')

# Centralized target_metadata
target_metadata_obj = None

flask_app_instance = create_app()
with flask_app_instance.app_context():
    from extensions import db # Get the db instance that has been init_app'd
    # Models should be imported by create_app or by Job model using db from extensions.
    # Explicitly import models here if still facing issues ensuring they are loaded.
    # from app.models.job import Job 
    
    target_metadata_obj = db.metadata # This db is now app-aware and should have metadata
    # logger.info(f"DETECTED TABLES IN DB.METADATA: {list(target_metadata_obj.tables.keys())}") # DIAGNOSTIC PRINT REMOVED
    
    db_url = current_app.config.get('SQLALCHEMY_DATABASE_URI')
    config.set_main_option('sqlalchemy.url', db_url)


def get_engine():
    # Ensure we are using the engine from the app context if needed
    # For Flask-SQLAlchemy >= 3, db.engine is correct
    # For < 3, db.get_engine() is used.
    # The flask_migrate helper get_engine() should handle this.
    try:
        # this works with Flask-SQLAlchemy<3 and Alchemical
        return current_app.extensions['migrate'].db.get_engine()
    except (TypeError, AttributeError):
        # this works with Flask-SQLAlchemy>=3
        return current_app.extensions['migrate'].db.engine

# We won't use get_engine_url() anymore as we set sqlalchemy.url directly from app config
# def get_engine_url():
# ... (rest of get_engine_url commented out or removed)

# config.set_main_option('sqlalchemy.url', get_engine_url()) # Set above from app_context


def get_metadata():
    return target_metadata_obj


def run_migrations_offline():
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = flask_app_instance.config.get('SQLALCHEMY_DATABASE_URI')
    context.configure(
        url=url, target_metadata=get_metadata(), literal_binds=True
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    def process_revision_directives(context, revision, directives):
        if getattr(config.cmd_opts, 'autogenerate', False):
            script = directives[0]
            if script.upgrade_ops.is_empty():
                directives[:] = []
                logger.info('No changes in schema detected.')

    # connectable = get_engine()
    # Using the engine from the app context directly
    connectable = db.engine # Assuming db is the app-aware instance from flask_app_instance.app_context()

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=get_metadata(),
            process_revision_directives=process_revision_directives,
            **current_app.extensions['migrate'].configure_args
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
