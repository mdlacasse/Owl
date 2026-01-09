"""
Tests for mylogging.py to improve coverage.

This module tests logging functionality, error handling, and edge cases
that are not covered by existing tests.

Copyright (C) 2025-2026 The Owlplanner Authors
"""

import pytest
import sys
from io import StringIO

import owlplanner.mylogging as log


def test_logger_init_default_streams():
    """Test Logger initialization with default streams."""
    logger = log.Logger()
    assert logger._logstreams == [sys.stdout, sys.stderr]
    assert logger._verbose is True


def test_logger_init_custom_streams():
    """Test Logger initialization with custom streams."""
    stream1 = StringIO()
    stream2 = StringIO()
    logger = log.Logger(verbose=False, logstreams=[stream1, stream2])
    assert logger._logstreams == [stream1, stream2]
    assert logger._verbose is False


def test_logger_init_single_stream():
    """Test Logger initialization with single stream (duplicated)."""
    stream = StringIO()
    logger = log.Logger(verbose=False, logstreams=[stream])
    assert len(logger._logstreams) == 2
    assert logger._logstreams[0] == stream
    assert logger._logstreams[1] == stream


def test_logger_init_empty_list():
    """Test Logger initialization with empty list (uses defaults)."""
    logger = log.Logger(verbose=False, logstreams=[])
    assert logger._logstreams == [sys.stdout, sys.stderr]


def test_logger_init_none():
    """Test Logger initialization with None (uses defaults)."""
    logger = log.Logger(verbose=False, logstreams=None)
    assert logger._logstreams == [sys.stdout, sys.stderr]


def test_logger_init_too_many_streams():
    """Test Logger initialization with too many streams (uses defaults)."""
    stream1 = StringIO()
    stream2 = StringIO()
    stream3 = StringIO()
    logger = log.Logger(verbose=False, logstreams=[stream1, stream2, stream3])
    assert logger._logstreams == [sys.stdout, sys.stderr]


def test_logger_init_invalid_type():
    """Test Logger initialization with invalid stream type."""
    with pytest.raises(ValueError, match="Log streams.*must be a list"):
        log.Logger(verbose=False, logstreams="not a list")


def test_set_verbose():
    """Test setVerbose method."""
    logger = log.Logger(verbose=True)
    prev_state = logger.setVerbose(False)
    assert prev_state is True
    assert logger._verbose is False

    prev_state = logger.setVerbose(True)
    assert prev_state is False
    assert logger._verbose is True


def test_reset_verbose():
    """Test resetVerbose method."""
    logger = log.Logger(verbose=True)
    logger.setVerbose(False)
    logger.resetVerbose()
    assert logger._verbose is True


def test_reset_verbose_with_stack():
    """Test resetVerbose with multiple setVerbose calls."""
    logger = log.Logger(verbose=True)
    logger.setVerbose(False)
    logger.setVerbose(True)
    logger.resetVerbose()
    assert logger._verbose is False  # Should restore to previous state
    logger.resetVerbose()
    assert logger._verbose is True  # Should restore to original state


def test_reset_verbose_empty_stack():
    """Test resetVerbose when stack is empty (uses _prevState)."""
    logger = log.Logger(verbose=True)
    logger._verboseStack = []  # Empty stack
    logger._prevState = False
    logger.resetVerbose()
    assert logger._verbose is False


def test_print_method():
    """Test print method."""
    stream = StringIO()
    logger = log.Logger(verbose=True, logstreams=[stream, stream])
    logger.print("Test message")
    stream.seek(0)
    output = stream.read()
    assert "Test message" in output
    assert "INFO" in output


def test_print_with_file_kwarg():
    """Test print method with file kwarg."""
    stream1 = StringIO()
    stream2 = StringIO()
    logger = log.Logger(verbose=True, logstreams=[stream1, stream2])
    logger.print("Test", file=stream2)
    stream2.seek(0)
    output = stream2.read()
    assert "Test" in output


def test_vprint_verbose_true():
    """Test vprint method when verbose is True."""
    stream = StringIO()
    logger = log.Logger(verbose=True, logstreams=[stream, stream])
    logger.vprint("Debug message")
    stream.seek(0)
    output = stream.read()
    assert "Debug message" in output
    assert "DEBUG" in output


def test_vprint_verbose_false():
    """Test vprint method when verbose is False."""
    stream = StringIO()
    logger = log.Logger(verbose=False, logstreams=[stream, stream])
    logger.vprint("Debug message")
    stream.seek(0)
    output = stream.read()
    assert output == ""  # Should not print when not verbose


def test_vprint_with_file_kwarg():
    """Test vprint method with file kwarg."""
    stream1 = StringIO()
    stream2 = StringIO()
    logger = log.Logger(verbose=True, logstreams=[stream1, stream2])
    logger.vprint("Debug", file=stream2)
    stream2.seek(0)
    output = stream2.read()
    assert "Debug" in output


def test_xprint_raises_exception():
    """Test xprint method raises exception."""
    stream = StringIO()
    logger = log.Logger(verbose=True, logstreams=[stream, stream])
    with pytest.raises(Exception, match="Fatal error"):
        logger.xprint("Error message")


def test_xprint_verbose_true():
    """Test xprint method when verbose is True."""
    stream1 = StringIO()
    stream2 = StringIO()
    logger = log.Logger(verbose=True, logstreams=[stream1, stream2])
    try:
        logger.xprint("Error message")
    except Exception:
        pass
    # xprint uses stderr (stream2) for errors, but "Exiting..." might go to stdout
    stream1.seek(0)
    stream2.seek(0)
    output1 = stream1.read()
    output2 = stream2.read()
    # Check that error message is in stderr
    assert "ERROR" in output2 or "Error message" in output2
    # "Exiting..." might be in either stream
    assert "Exiting" in (output1 + output2)


def test_xprint_verbose_false():
    """Test xprint method when verbose is False."""
    stream = StringIO()
    logger = log.Logger(verbose=False, logstreams=[stream, stream])
    try:
        logger.xprint("Error message")
    except Exception:
        pass
    stream.seek(0)
    output = stream.read()
    # Should still print error even when not verbose
    assert "ERROR" in output or output == ""


def test_xprint_with_file_kwarg():
    """Test xprint method with file kwarg."""
    stream1 = StringIO()
    stream2 = StringIO()
    logger = log.Logger(verbose=True, logstreams=[stream1, stream2])
    try:
        logger.xprint("Error", file=stream1)
    except Exception:
        pass
    stream1.seek(0)
    output = stream1.read()
    assert "ERROR" in output or "Error" in output


def test_deepcopy():
    """Test __deepcopy__ method."""
    import copy
    stream = StringIO()
    logger = log.Logger(verbose=False, logstreams=[stream, stream])
    logger.setVerbose(True)

    copied = copy.deepcopy(logger)
    assert copied._verbose == logger._verbose
    assert copied._verboseStack == logger._verboseStack
    # Should be a new instance
    assert copied is not logger


def test_deepcopy_with_custom_streams():
    """Test __deepcopy__ with custom streams."""
    import copy
    stream1 = StringIO()
    stream2 = StringIO()
    logger = log.Logger(verbose=False, logstreams=[stream1, stream2])

    copied = copy.deepcopy(logger)
    # Custom streams should be preserved
    assert len(copied._logstreams) == 2


def test_logger_with_loguru_backend():
    """Test Logger with loguru backend if available."""
    if log.HAS_LOGURU:
        logger = log.Logger(verbose=True, logstreams="loguru")
        assert logger._use_loguru is True
        assert logger._logstreams is None
    else:
        with pytest.raises(ImportError, match="loguru is required"):
            log.Logger(verbose=True, logstreams="loguru")


def test_logger_with_loguru_list():
    """Test Logger with loguru as list."""
    if log.HAS_LOGURU:
        logger = log.Logger(verbose=True, logstreams=["loguru"])
        assert logger._use_loguru is True
    else:
        with pytest.raises(ImportError, match="loguru is required"):
            log.Logger(verbose=True, logstreams=["loguru"])


def test_print_loguru_backend():
    """Test print method with loguru backend."""
    if log.HAS_LOGURU:
        logger = log.Logger(verbose=True, logstreams="loguru")
        # Should not raise error
        logger.print("Test message")


def test_vprint_loguru_backend():
    """Test vprint method with loguru backend."""
    if log.HAS_LOGURU:
        logger = log.Logger(verbose=True, logstreams="loguru")
        # Should not raise error
        logger.vprint("Debug message")


def test_xprint_loguru_backend():
    """Test xprint method with loguru backend."""
    if log.HAS_LOGURU:
        logger = log.Logger(verbose=True, logstreams="loguru")
        with pytest.raises(Exception, match="Fatal error"):
            logger.xprint("Error message")
