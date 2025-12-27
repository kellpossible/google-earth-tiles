"""Main application entry point."""

import argparse
import logging
import sys


def setup_logging(verbose: bool = False):
    """
    Set up logging configuration.

    Args:
        verbose: Enable verbose logging
    """
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
        ],
    )


def cmd_download(args):
    """Handle download subcommand - process one or more config files."""
    setup_logging(args.verbose)
    from src.cli import run_cli

    config_files = args.config if isinstance(args.config, list) else [args.config]
    total_files = len(config_files)
    failed_files = []
    successful_files = []

    # Process each config file sequentially
    for idx, config_path in enumerate(config_files, 1):
        if total_files > 1:
            logging.info(f"\n{'=' * 80}")
            logging.info(f"Processing config {idx}/{total_files}: {config_path}")
            logging.info(f"{'=' * 80}\n")

        try:
            exit_code = run_cli(config_path)

            if exit_code == 0:
                successful_files.append(config_path)
                if total_files > 1:
                    logging.info(f"✓ Successfully processed: {config_path}")
            else:
                failed_files.append(config_path)
                logging.error(f"✗ Failed to process: {config_path}")

                # Stop processing remaining files if --stop-on-error flag is set
                if args.stop_on_error:
                    logging.error("Stopping due to --stop-on-error flag")
                    break

        except KeyboardInterrupt:
            logging.warning(f"\n✗ Interrupted while processing: {config_path}")
            failed_files.append(config_path)
            break
        except Exception as e:
            logging.exception(f"Unexpected error processing {config_path}: {e}")
            failed_files.append(config_path)

            if args.stop_on_error:
                logging.error("Stopping due to --stop-on-error flag")
                break

    # Print summary if multiple files were processed
    if total_files > 1:
        logging.info(f"\n{'=' * 80}")
        logging.info("Processing Summary")
        logging.info(f"{'=' * 80}")
        logging.info(f"Total configs: {total_files}")
        logging.info(f"Successful:    {len(successful_files)}")
        logging.info(f"Failed:        {len(failed_files)}")

        if successful_files:
            logging.info("\nSuccessful configs:")
            for config in successful_files:
                logging.info(f"  ✓ {config}")

        if failed_files:
            logging.info("\nFailed configs:")
            for config in failed_files:
                logging.info(f"  ✗ {config}")

        logging.info(f"{'=' * 80}\n")

    # Return non-zero exit code if any files failed
    return 1 if failed_files else 0


def launch_gui(config_file: str | None = None):
    """
    Launch the GUI application.

    Args:
        config_file: Optional path to config file to load on startup
    """
    import signal

    from PyQt6.QtCore import QByteArray, QTimer
    from PyQt6.QtWebEngineCore import QWebEngineUrlScheme
    from PyQt6.QtWidgets import QApplication

    from src.gui.main_window import MainWindow

    # Register custom URL scheme BEFORE creating QApplication
    scheme = QWebEngineUrlScheme(QByteArray(b"preview"))
    scheme.setFlags(QWebEngineUrlScheme.Flag.LocalScheme | QWebEngineUrlScheme.Flag.LocalAccessAllowed)
    QWebEngineUrlScheme.registerScheme(scheme)

    # Create QApplication for GUI
    app = QApplication(sys.argv)
    _set_app_metadata(app)

    # Set up Ctrl+C handling
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    # Create a timer to allow Python to process signals
    # This is necessary for Ctrl+C to work with Qt
    timer = QTimer()
    timer.timeout.connect(lambda: None)  # No-op, just lets Python process signals
    timer.start(500)  # Check every 500ms

    # Create window with optional config file
    window = MainWindow(config_file=config_file)
    window.show()

    sys.exit(app.exec())


def cmd_open(args):
    """Handle open subcommand - launch GUI with config file loaded."""
    launch_gui(config_file=args.config)


def cmd_list_layers(args):
    """Handle list-layers subcommand."""
    from src.core.config import LAYERS

    print("Available WMTS Layers:")
    print()

    for key, layer in LAYERS.items():
        print(f"  {key:8} - {layer.display_name}")
        print(f"           {layer.description}")
        print(f"           Format: {layer.extension.upper()}, Zoom: {layer.min_zoom}-{layer.max_zoom}")
        print(f"           URL: {layer.url_template}")
        print()

    return 0


def cmd_schema(args):
    """Handle schema subcommand - print configuration schema documentation."""
    from pathlib import Path

    # Get the schema file path
    schema_path = Path(__file__).parent.parent / "schemas" / "config.schema.yaml"

    if not schema_path.exists():
        print(f"Error: Schema file not found at {schema_path}", file=sys.stderr)
        return 1

    try:
        # If --yaml flag is provided, just print the raw YAML
        if args.yaml:
            with open(schema_path) as f:
                print(f.read())
            return 0

        # Otherwise, convert to markdown and render with rich
        import yaml
        from jsonschema2md import Parser
        from rich.console import Console
        from rich.markdown import Markdown

        # Read YAML schema
        with open(schema_path) as f:
            schema_dict = yaml.safe_load(f)

        # Convert schema to markdown using jsonschema2md
        parser = Parser()
        md_lines = parser.parse_schema(schema_dict)
        markdown_text = "\n".join(md_lines)

        # Render markdown with rich
        console = Console()
        markdown = Markdown(markdown_text)
        console.print(markdown)

        return 0

    except Exception as e:
        print(f"Error generating schema documentation: {e}", file=sys.stderr)
        return 1


def _set_app_metadata(app):
    """
    Set organization and application metadata.

    This is used by QStandardPaths and QSettings to determine
    cache and configuration file locations.

    Args:
        app: QApplication or QCoreApplication instance
    """
    app.setOrganizationName("lukefrisken.com")
    app.setApplicationName("google-earth-tile-generator")


def main():
    """Main application entry point."""
    parser = argparse.ArgumentParser(
        description="Google Earth Tile Generator - Generate KMZ files from WMTS tiles",
        epilog="Run without arguments to launch GUI mode.",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Download subcommand
    download_parser = subparsers.add_parser("download", help="Download tiles and generate output files")
    download_parser.add_argument("config", nargs="+", help="YAML configuration file(s) to process")
    download_parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
    download_parser.add_argument(
        "--stop-on-error", action="store_true", help="Stop processing remaining configs if one fails"
    )
    download_parser.set_defaults(func=cmd_download)

    # Open subcommand (launch GUI with file)
    open_parser = subparsers.add_parser("open", help="Open config file in GUI")
    open_parser.add_argument("config", help="YAML configuration file to open")
    open_parser.set_defaults(func=cmd_open)

    # List layers subcommand
    list_parser = subparsers.add_parser("list-layers", help="List available WMTS layers")
    list_parser.set_defaults(func=cmd_list_layers)

    # Schema subcommand
    schema_parser = subparsers.add_parser("schema", help="Print configuration schema documentation")
    schema_parser.add_argument(
        "--yaml", action="store_true", help="Output raw YAML schema instead of formatted documentation"
    )
    schema_parser.set_defaults(func=cmd_schema)

    args = parser.parse_args()

    # If no subcommand provided, launch GUI
    if args.command is None:
        launch_gui()
    else:
        # For "open" command, don't create QCoreApplication (it creates QApplication itself)
        if args.command == "open":
            return args.func(args)

        # Create QCoreApplication for other CLI commands to ensure proper cache/settings paths
        from PyQt6.QtCore import QCoreApplication

        app = QCoreApplication(sys.argv)
        _set_app_metadata(app)

        # Run the subcommand
        return args.func(args)


if __name__ == "__main__":
    main()
