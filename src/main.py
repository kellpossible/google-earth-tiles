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
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
        ]
    )


def cmd_download(args):
    """Handle download subcommand."""
    setup_logging(args.verbose)
    from src.cli import run_cli
    return run_cli(args.config)


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


def main():
    """Main application entry point."""
    parser = argparse.ArgumentParser(
        description='Google Earth Tile Generator - Generate KMZ files from WMTS tiles',
        epilog='Run without arguments to launch GUI mode.'
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Download subcommand
    download_parser = subparsers.add_parser(
        'download',
        help='Download tiles and generate KMZ file'
    )
    download_parser.add_argument(
        'config',
        help='YAML configuration file'
    )
    download_parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    download_parser.set_defaults(func=cmd_download)

    # List layers subcommand
    list_parser = subparsers.add_parser(
        'list-layers',
        help='List available WMTS layers'
    )
    list_parser.set_defaults(func=cmd_list_layers)

    args = parser.parse_args()

    # If no subcommand provided, launch GUI
    if args.command is None:
        import signal
        from PyQt6.QtCore import QTimer
        from PyQt6.QtWidgets import QApplication
        from src.gui.main_window import MainWindow

        app = QApplication(sys.argv)
        app.setApplicationName("Google Earth Tile Generator")

        # Set up Ctrl+C handling
        signal.signal(signal.SIGINT, signal.SIG_DFL)

        # Create a timer to allow Python to process signals
        # This is necessary for Ctrl+C to work with Qt
        timer = QTimer()
        timer.timeout.connect(lambda: None)  # No-op, just lets Python process signals
        timer.start(500)  # Check every 500ms

        window = MainWindow()
        window.show()

        sys.exit(app.exec())
    else:
        # Run the subcommand
        return args.func(args)


if __name__ == '__main__':
    main()
