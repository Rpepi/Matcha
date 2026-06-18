import logging
import pytest


class TestSetupLogging:
    def test_configures_at_least_one_handler(self):
        from app.log import setup_logging
        setup_logging()
        root = logging.getLogger()
        assert len(root.handlers) > 0

    def test_uvicorn_access_silenced_to_warning(self):
        from app.log import setup_logging
        setup_logging()
        assert logging.getLogger("uvicorn.access").level == logging.WARNING

    def test_idempotent_second_call_does_not_duplicate_handlers(self):
        from app.log import setup_logging
        setup_logging()
        count_before = len(logging.getLogger().handlers)
        setup_logging()
        # basicConfig is a no-op when handlers already exist — count stays same
        assert len(logging.getLogger().handlers) == count_before


class TestGetLogger:
    def test_returns_logger_instance(self):
        from app.log import get_logger
        assert isinstance(get_logger("test.module"), logging.Logger)

    def test_logger_name_matches(self):
        from app.log import get_logger
        assert get_logger("app.routes.chat").name == "app.routes.chat"

    def test_same_name_returns_same_object(self):
        from app.log import get_logger
        assert get_logger("shared.mod") is get_logger("shared.mod")

    def test_different_names_are_different_loggers(self):
        from app.log import get_logger
        assert get_logger("mod.a") is not get_logger("mod.b")

    def test_dunder_name_pattern_works(self):
        from app.log import get_logger
        logger = get_logger(__name__)
        assert logger.name == __name__
