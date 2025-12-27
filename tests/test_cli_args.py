"""Tests for CLI argument parsing."""

from unittest.mock import patch


def test_open_subcommand():
    """Test that 'open' subcommand launches GUI with config file."""
    test_args = ["google-earth-tiles", "open", "test_config.yaml"]

    with patch("sys.argv", test_args), patch("src.main.launch_gui") as mock_launch_gui:
        from src.main import main

        # Run main
        main()

        # Verify launch_gui was called with the config file
        assert mock_launch_gui.called
        assert mock_launch_gui.call_args[1]["config_file"] == "test_config.yaml"


def test_download_subcommand_still_works():
    """Test that explicit 'download' subcommand still works (backward compatibility)."""
    test_args = ["google-earth-tiles", "download", "test_config.yaml"]

    with (
        patch("sys.argv", test_args),
        patch("src.main.cmd_download") as mock_download,
        patch("PyQt6.QtCore.QCoreApplication"),
    ):
        from src.main import main

        mock_download.return_value = 0
        main()

        assert mock_download.called
        args = mock_download.call_args[0][0]
        assert args.config == ["test_config.yaml"]


def test_list_layers_subcommand():
    """Test that list-layers subcommand still works."""
    test_args = ["google-earth-tiles", "list-layers"]

    with (
        patch("sys.argv", test_args),
        patch("src.main.cmd_list_layers") as mock_list,
        patch("PyQt6.QtCore.QCoreApplication"),
    ):
        from src.main import main

        mock_list.return_value = 0
        result = main()

        assert mock_list.called
        assert result == 0


def test_schema_subcommand():
    """Test that schema subcommand still works."""
    test_args = ["google-earth-tiles", "schema", "--yaml"]

    with (
        patch("sys.argv", test_args),
        patch("src.main.cmd_schema") as mock_schema,
        patch("PyQt6.QtCore.QCoreApplication"),
    ):
        from src.main import main

        mock_schema.return_value = 0
        main()

        assert mock_schema.called
        args = mock_schema.call_args[0][0]
        assert args.yaml is True


def test_no_args_launches_gui():
    """Test that no arguments launches GUI without config file."""
    test_args = ["google-earth-tiles"]

    with patch("sys.argv", test_args), patch("src.main.launch_gui") as mock_launch_gui:
        from src.main import main

        # Run main
        main()

        # Verify launch_gui was called without config file
        assert mock_launch_gui.called
        # Should be called with no config_file (or config_file=None)
        if mock_launch_gui.call_args[1]:
            assert mock_launch_gui.call_args[1].get("config_file") is None
            # Or called with no keyword args at all
