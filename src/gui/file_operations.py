"""File operations for saving and loading UI state."""

import logging
from pathlib import Path
from typing import Callable, Optional

import yaml
from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QFileDialog, QMessageBox, QWidget

logger = logging.getLogger(__name__)


class FileOperations:
    """Handles file save/load operations with user prompts."""

    def __init__(self, parent: QWidget):
        """
        Initialize file operations handler.

        Args:
            parent: Parent widget for dialogs
        """
        self.parent = parent
        self.current_file: Optional[Path] = None
        self.is_dirty = False
        self.settings = QSettings("AnthropicClaude", "GoogleEarthTileGenerator")
        self.max_recent_files = 10

    def save(self, get_state_callback: Callable) -> bool:
        """
        Save to current file or prompt for filename if new.

        Args:
            get_state_callback: Function that returns state dict

        Returns:
            True if saved successfully, False otherwise
        """
        # Validate before saving
        try:
            state = get_state_callback()
        except ValueError as e:
            QMessageBox.critical(
                self.parent,
                "Cannot Save",
                str(e)
            )
            return False

        if self.current_file is None:
            return self.save_as(get_state_callback)
        return self._do_save(self.current_file, state)

    def save_as(self, get_state_callback: Callable) -> bool:
        """
        Prompt for filename and save.

        Args:
            get_state_callback: Function that returns state dict

        Returns:
            True if saved successfully, False otherwise
        """
        # Validate BEFORE showing file dialog
        try:
            state = get_state_callback()
        except ValueError as e:
            QMessageBox.critical(
                self.parent,
                "Cannot Save",
                str(e)
            )
            return False

        file_path, _ = QFileDialog.getSaveFileName(
            self.parent,
            "Save Configuration",
            str(Path.home() / "config.yaml"),
            "YAML Files (*.yaml *.yml);;All Files (*)"
        )

        if not file_path:
            return False

        # Ensure .yaml extension if no extension provided
        file_path = Path(file_path)
        if not file_path.suffix:
            file_path = file_path.with_suffix('.yaml')

        return self._do_save(file_path, state)

    def _do_save(self, file_path: Path, state: dict) -> bool:
        """
        Actually perform the save operation.

        Args:
            file_path: Path to save to
            state: State dictionary to save

        Returns:
            True if saved successfully, False otherwise
        """
        try:
            with open(file_path, 'w') as f:
                yaml.dump(state, f, default_flow_style=False, sort_keys=False)

            self.current_file = file_path
            self.is_dirty = False
            self._add_to_recent_files(file_path)
            logger.info(f"Saved configuration to: {file_path}")
            return True

        except Exception as e:
            logger.exception("Error saving file")
            QMessageBox.critical(
                self.parent,
                "Save Error",
                f"Failed to save file:\n{str(e)}"
            )
            return False

    def open(self, load_state_callback: Callable, get_state_callback: Callable) -> bool:
        """
        Prompt for file and load.

        Args:
            load_state_callback: Function that accepts state dict
            get_state_callback: Function that returns current state dict (for saving before open)

        Returns:
            True if loaded successfully, False otherwise
        """
        # Prompt for unsaved changes
        if self.is_dirty:
            response = self._prompt_save_changes()
            if response == QMessageBox.StandardButton.Cancel:
                return False
            elif response == QMessageBox.StandardButton.Save:
                # Try to save first
                if not self.save(get_state_callback):
                    return False  # Save failed, cancel open

        file_path, _ = QFileDialog.getOpenFileName(
            self.parent,
            "Open Configuration",
            str(Path.home()),
            "YAML Files (*.yaml *.yml);;All Files (*)"
        )

        if not file_path:
            return False

        return self._do_open(Path(file_path), load_state_callback)

    def _do_open(self, file_path: Path, load_state_callback: Callable) -> bool:
        """
        Actually perform the open operation.

        Args:
            file_path: Path to load from
            load_state_callback: Function that accepts state dict

        Returns:
            True if loaded successfully, False otherwise
        """
        try:
            from src.cli import load_config, validate_config

            # Load and validate
            config = load_config(str(file_path))
            validate_config(config)

            # Load into UI
            load_state_callback(config)

            self.current_file = file_path
            self.is_dirty = False
            self._add_to_recent_files(file_path)
            logger.info(f"Loaded configuration from: {file_path}")
            return True

        except FileNotFoundError:
            QMessageBox.critical(
                self.parent,
                "File Not Found",
                f"File not found: {file_path}"
            )
            return False
        except yaml.YAMLError as e:
            QMessageBox.critical(
                self.parent,
                "Invalid YAML",
                f"Failed to parse YAML file:\n{str(e)}"
            )
            return False
        except ValueError as e:
            QMessageBox.critical(
                self.parent,
                "Invalid Configuration",
                f"Configuration validation failed:\n{str(e)}"
            )
            return False
        except Exception as e:
            logger.exception("Error loading file")
            QMessageBox.critical(
                self.parent,
                "Load Error",
                f"Failed to load file:\n{str(e)}"
            )
            return False

    def _prompt_save_changes(self) -> QMessageBox.StandardButton:
        """
        Prompt user to save changes.

        Returns:
            QMessageBox.StandardButton (Save, Discard, or Cancel)
        """
        filename = self.current_file.name if self.current_file else "Unsaved"

        msg = QMessageBox(self.parent)
        msg.setIcon(QMessageBox.Icon.Question)
        msg.setWindowTitle("Unsaved Changes")
        msg.setText(f"Do you want to save changes to '{filename}'?")
        msg.setStandardButtons(
            QMessageBox.StandardButton.Save |
            QMessageBox.StandardButton.Discard |
            QMessageBox.StandardButton.Cancel
        )
        msg.setDefaultButton(QMessageBox.StandardButton.Save)

        return msg.exec()

    def prompt_save_before_close(self, get_state_callback: Callable) -> bool:
        """
        Prompt to save changes before closing window.

        Args:
            get_state_callback: Function that returns state dict

        Returns:
            True if OK to close, False to cancel close
        """
        if not self.is_dirty:
            return True

        response = self._prompt_save_changes()

        if response == QMessageBox.StandardButton.Save:
            return self.save(get_state_callback)
        elif response == QMessageBox.StandardButton.Discard:
            return True
        else:  # Cancel
            return False

    def mark_dirty(self):
        """Mark the file as having unsaved changes."""
        self.is_dirty = True

    def _add_to_recent_files(self, file_path: Path):
        """
        Add a file to the recent files list.

        Args:
            file_path: Path to add to recent files
        """
        recent = self.settings.value("recentFiles", [], type=list)

        # Convert to string for storage
        file_str = str(file_path.resolve())

        # Remove if already exists (move to top)
        if file_str in recent:
            recent.remove(file_str)

        # Add to front
        recent.insert(0, file_str)

        # Limit to max_recent_files
        recent = recent[:self.max_recent_files]

        # Save
        self.settings.setValue("recentFiles", recent)

    def get_recent_files(self) -> list:
        """
        Get list of recent file paths (only existing files).

        Returns:
            List of file path strings for existing files
        """
        recent = self.settings.value("recentFiles", [], type=list)
        # Filter out files that no longer exist
        return [f for f in recent if Path(f).exists()]

    def clear_recent_files(self):
        """Clear the recent files list."""
        self.settings.setValue("recentFiles", [])

    def open_recent(
        self,
        file_path: Path,
        load_state_callback: Callable,
        get_state_callback: Callable
    ) -> bool:
        """
        Open a recent file with unsaved changes prompt.

        Args:
            file_path: Path to recent file
            load_state_callback: Function to load state
            get_state_callback: Function to get current state for saving

        Returns:
            True if opened successfully
        """
        # Check if file still exists
        if not file_path.exists():
            QMessageBox.warning(
                self.parent,
                "File Not Found",
                f"The file no longer exists:\n{file_path}"
            )
            # Remove from recent files
            recent = self.settings.value("recentFiles", [], type=list)
            file_str = str(file_path)
            if file_str in recent:
                recent.remove(file_str)
                self.settings.setValue("recentFiles", recent)
            return False

        # Prompt for unsaved changes
        if self.is_dirty:
            response = self._prompt_save_changes()
            if response == QMessageBox.StandardButton.Cancel:
                return False
            elif response == QMessageBox.StandardButton.Save:
                if not self.save(get_state_callback):
                    return False

        return self._do_open(file_path, load_state_callback)

    def get_display_title(self, base_title: str = "Google Earth Tile Generator") -> str:
        """
        Get window title with file and dirty status.

        Args:
            base_title: Base application title

        Returns:
            Formatted window title
        """
        if self.current_file is None:
            filename = "*Unsaved"
        else:
            filename = self.current_file.name
            if self.is_dirty:
                filename = "*" + filename

        return f"{filename} - {base_title}"
