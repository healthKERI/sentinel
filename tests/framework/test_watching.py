"""
Tests for framework file watching service
"""

import pytest
import asyncio
import tempfile
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, MagicMock
from sentinel.framework.watching import FileWatchingService
from sentinel.framework.handlers import EventHandler
from sentinel.framework.events import KELEvent, TELEvent, CredentialEvent
from sentinel.framework.registry import register_handler, get_registry


class CollectingHandler(EventHandler):
    """Test handler that collects events"""

    def __init__(self):
        self.kel_events = []
        self.tel_events = []
        self.cred_events = []

    async def on_kel(self, event: KELEvent):
        self.kel_events.append(event)

    async def on_tel(self, event: TELEvent):
        self.tel_events.append(event)

    async def on_credential(self, event: CredentialEvent):
        self.cred_events.append(event)


@pytest.fixture
def temp_export_dir():
    """Create temporary export directory structure"""
    with tempfile.TemporaryDirectory() as tmpdir:
        export_dir = Path(tmpdir)
        (export_dir / "kel").mkdir()
        (export_dir / "tel").mkdir()
        (export_dir / "cred").mkdir()
        yield export_dir


@pytest.fixture
def mock_db():
    """Create mock database with file_state attribute that tracks state"""
    db = Mock()
    # Use a dict to track file states
    file_states = {}

    def mock_get(keys):
        """Mock get that returns stored state or None"""
        key = keys[0] if isinstance(keys, tuple) else keys
        return file_states.get(key)

    def mock_pin(keys, val):
        """Mock pin that stores the state"""
        key = keys[0] if isinstance(keys, tuple) else keys
        file_states[key] = val

    db.file_state = Mock()
    db.file_state.get = mock_get
    db.file_state.pin = mock_pin
    return db


@pytest.fixture
def mock_hby():
    """Create mock Habery with kvy attribute"""
    hby = Mock()
    hby.kvy = Mock()
    return hby


@pytest.fixture
def handler():
    """Create and register a collecting handler"""
    # Clear registry
    registry = get_registry()
    registry._handlers = set()

    # Create and register handler
    h = CollectingHandler()
    register_handler(h)
    yield h

    # Cleanup
    registry._handlers = set()


class TestFileWatchingService:
    """Test FileWatchingService"""

    def test_service_initialization(self, temp_export_dir, mock_db, mock_hby):
        """Test service can be initialized"""
        service = FileWatchingService(
            export_dir=str(temp_export_dir),
            poll_interval=0.1,
            hby=mock_hby,
            db=mock_db,
        )
        assert service.export_dir == temp_export_dir
        assert service.poll_interval == 0.1
        assert service._running is False
        assert service.db is mock_db
        assert service.hby is mock_hby

    def test_watch_dirs_created(self, temp_export_dir):
        """Test that watch directories are configured"""
        service = FileWatchingService(export_dir=str(temp_export_dir))
        assert "kel" in service.watch_dirs
        assert "tel" in service.watch_dirs
        assert "credential" in service.watch_dirs
        assert service.watch_dirs["kel"] == temp_export_dir / "kel"
        assert service.watch_dirs["credential"] == temp_export_dir / "cred"

    @pytest.mark.asyncio
    async def test_detect_new_kel_file(self, temp_export_dir, handler, mock_db, mock_hby):
        """Test detecting a new KEL file"""
        from unittest.mock import patch

        # Mock the Parser to avoid actual CESR parsing
        with patch('sentinel.framework.watching.parsing.Parser') as mock_parser_class:
            mock_parser = Mock()
            mock_parser.parse = Mock()
            mock_parser_class.return_value = mock_parser

            service = FileWatchingService(
                export_dir=str(temp_export_dir),
                poll_interval=0.1,
                hby=mock_hby,
                db=mock_db,
            )

            # Start service
            task = service.start()

            # Give service time to start
            await asyncio.sleep(0.2)

            # Create a KEL file
            kel_file = temp_export_dir / "kel" / "test_aid.cesr"
            kel_file.write_bytes(b"test kel data")

            # Wait for polling
            await asyncio.sleep(0.3)

            # Stop service
            service.stop()
            try:
                await asyncio.wait_for(task, timeout=1.0)
            except asyncio.TimeoutError:
                task.cancel()

            # Check that event was dispatched
            assert len(handler.kel_events) == 1
            event = handler.kel_events[0]
            assert event.aid == "test_aid"
            assert event.data == b"test kel data"
            assert event.filepath == str(kel_file)

    @pytest.mark.asyncio
    async def test_detect_modified_kel_file(self, temp_export_dir, handler, mock_db, mock_hby):
        """Test detecting a modified KEL file"""
        from unittest.mock import patch

        # Mock the Parser to avoid actual CESR parsing
        with patch('sentinel.framework.watching.parsing.Parser') as mock_parser_class:
            mock_parser = Mock()
            mock_parser.parse = Mock()
            mock_parser_class.return_value = mock_parser

            service = FileWatchingService(
                export_dir=str(temp_export_dir),
                poll_interval=0.1,
                hby=mock_hby,
                db=mock_db,
            )

            # Create a KEL file before starting service
            kel_file = temp_export_dir / "kel" / "test_aid.cesr"
            kel_file.write_bytes(b"initial data")

            # Start service
            task = service.start()
            await asyncio.sleep(0.2)

            # Should detect initial file
            assert len(handler.kel_events) == 1

            # Modify file - need to wait to ensure mtime changes
            await asyncio.sleep(1.1)  # Wait >1 second to ensure mtime changes
            kel_file.write_bytes(b"modified data")
            # Touch the file to update mtime
            import os
            import time
            mtime = os.path.getmtime(kel_file)
            os.utime(kel_file, (mtime + 2, mtime + 2))

            # Wait for polling
            await asyncio.sleep(0.3)

            # Stop service
            service.stop()
            try:
                await asyncio.wait_for(task, timeout=1.0)
            except asyncio.TimeoutError:
                task.cancel()

            # Check that both events were dispatched
            assert len(handler.kel_events) == 2
            assert handler.kel_events[0].data == b"initial data"
            assert handler.kel_events[1].data == b"modified data"

    @pytest.mark.asyncio
    async def test_detect_tel_file(self, temp_export_dir, handler, mock_db, mock_hby):
        """Test detecting TEL file"""
        from unittest.mock import patch

        # Mock the Parser to avoid actual CESR parsing
        with patch('sentinel.framework.watching.parsing.Parser') as mock_parser_class:
            mock_parser = Mock()
            mock_parser.parse = Mock()
            mock_parser_class.return_value = mock_parser

            service = FileWatchingService(
                export_dir=str(temp_export_dir),
                poll_interval=0.1,
                hby=mock_hby,
                db=mock_db,
            )

            task = service.start()
            await asyncio.sleep(0.2)

            # Create TEL file
            tel_file = temp_export_dir / "tel" / "test_tel.cesr"
            tel_file.write_bytes(b"tel data")

            await asyncio.sleep(0.3)

            service.stop()
            try:
                await asyncio.wait_for(task, timeout=1.0)
            except asyncio.TimeoutError:
                task.cancel()

            assert len(handler.tel_events) == 1
            assert handler.tel_events[0].aid == "test_tel"

    @pytest.mark.asyncio
    async def test_detect_credential_file(self, temp_export_dir, handler, mock_db, mock_hby):
        """Test detecting credential file"""
        from unittest.mock import patch

        # Mock the Parser to avoid actual CESR parsing
        with patch('sentinel.framework.watching.parsing.Parser') as mock_parser_class:
            mock_parser = Mock()
            mock_parser.parse = Mock()
            mock_parser_class.return_value = mock_parser

            service = FileWatchingService(
                export_dir=str(temp_export_dir),
                poll_interval=0.1,
                hby=mock_hby,
                db=mock_db,
            )

            task = service.start()
            await asyncio.sleep(0.2)

            # Create credential file
            cred_file = temp_export_dir / "cred" / "test_cred.cesr"
            cred_file.write_bytes(b"cred data")

            await asyncio.sleep(0.3)

            service.stop()
            try:
                await asyncio.wait_for(task, timeout=1.0)
            except asyncio.TimeoutError:
                task.cancel()

            assert len(handler.cred_events) == 1
            assert handler.cred_events[0].aid == "test_cred"

    @pytest.mark.asyncio
    async def test_no_duplicate_events_for_unchanged_files(
        self, temp_export_dir, handler, mock_db, mock_hby
    ):
        """Test that unchanged files don't trigger events"""
        from unittest.mock import patch

        # Mock the Parser to avoid actual CESR parsing
        with patch('sentinel.framework.watching.parsing.Parser') as mock_parser_class:
            mock_parser = Mock()
            mock_parser.parse = Mock()
            mock_parser_class.return_value = mock_parser

            service = FileWatchingService(
                export_dir=str(temp_export_dir),
                poll_interval=0.1,
                hby=mock_hby,
                db=mock_db,
            )

            # Create file
            kel_file = temp_export_dir / "kel" / "test_aid.cesr"
            kel_file.write_bytes(b"data")

            task = service.start()

            # Wait for multiple poll cycles
            await asyncio.sleep(0.5)

            service.stop()
            try:
                await asyncio.wait_for(task, timeout=1.0)
            except asyncio.TimeoutError:
                task.cancel()

            # Should only have one event (initial detection)
            assert len(handler.kel_events) == 1

    @pytest.mark.asyncio
    async def test_service_with_keri_infrastructure(self, temp_export_dir, handler):
        """Test that KERI infrastructure is passed to events"""
        from unittest.mock import patch

        # Create mock objects with proper structure
        mock_hby_test = Mock()
        mock_hby_test.kvy = Mock()

        mock_essr_test = Mock()

        # Create mock_db_test with state tracking
        mock_db_test = Mock()
        file_states_test = {}

        def mock_get_test(keys):
            key = keys[0] if isinstance(keys, tuple) else keys
            return file_states_test.get(key)

        def mock_pin_test(keys, val):
            key = keys[0] if isinstance(keys, tuple) else keys
            file_states_test[key] = val

        mock_db_test.file_state = Mock()
        mock_db_test.file_state.get = mock_get_test
        mock_db_test.file_state.pin = mock_pin_test

        # Mock the Parser to avoid actual CESR parsing
        with patch('sentinel.framework.watching.parsing.Parser') as mock_parser_class:
            mock_parser = Mock()
            mock_parser.parse = Mock()
            mock_parser_class.return_value = mock_parser

            service = FileWatchingService(
                export_dir=str(temp_export_dir),
                poll_interval=0.1,
                hby=mock_hby_test,
                essr=mock_essr_test,
                db=mock_db_test,
            )

            task = service.start()
            await asyncio.sleep(0.2)

            kel_file = temp_export_dir / "kel" / "test.cesr"
            kel_file.write_bytes(b"data")

            await asyncio.sleep(0.3)

            service.stop()
            try:
                await asyncio.wait_for(task, timeout=1.0)
            except asyncio.TimeoutError:
                task.cancel()

            assert len(handler.kel_events) == 1
            event = handler.kel_events[0]
            assert event.hby is mock_hby_test
            assert event.essr is mock_essr_test
            assert event.db is mock_db_test
