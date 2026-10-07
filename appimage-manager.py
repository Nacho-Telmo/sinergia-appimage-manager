#!/usr/bin/env python3
import json
import logging
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QColor, QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

# Configuración del sistema de logging para depuración profesional
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)


class DropZoneWidget(QFrame):

  def __init__(self, main_window):
    super().__init__()
    self.main_window = main_window
    self.setAcceptDrops(True)
    self.setObjectName("dropZone")
    self.setMinimumHeight(75)

    layout = QVBoxLayout()
    self.label = QLabel(
        "📥  Arrastra nuevos .AppImage aquí\n(o haz clic para seleccionarlos con"
        " el explorador)"
    )
    self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(self.label)
    self.setLayout(layout)

    self.setStyleSheet("""
            QFrame#dropZone {
                background-color: #1f2335;
                border: 2px dashed #3b4261;
                border-radius: 12px;
            }
            QFrame#dropZone:hover {
                border-color: #7aa2f7;
                background-color: #24283b;
            }
            QLabel {
                color: #c0caf5;
                font-size: 13px;
                font-weight: bold;
                background: transparent;
            }
        """)

  def mousePressEvent(self, event):
    if event.button() == Qt.MouseButton.LeftButton:
      self.main_window.add_appimage_dialog()

  def dragEnterEvent(self, event):
    if event.mimeData().hasUrls():
      event.acceptProposedAction()
      self.setStyleSheet("""
                QFrame#dropZone {
                    background-color: #2a2b3c;
                    border: 2px solid #7aa2f7;
                    border-radius: 12px;
                }
                QLabel {
                    color: #ffffff;
                    font-size: 13px;
                    font-weight: bold;
                    background: transparent;
                }
            """)
    else:
      event.ignore()

  def dragLeaveEvent(self, event):
    self.setStyleSheet("""
            QFrame#dropZone {
                background-color: #1f2335;
                border: 2px dashed #3b4261;
                border-radius: 12px;
            }
            QLabel {
                color: #c0caf5;
                font-size: 13px;
                font-weight: bold;
                background: transparent;
            }
        """)

  def dropEvent(self, event):
    self.dragLeaveEvent(event)
    for url in event.mimeData().urls():
      file_path = url.toLocalFile()
      logging.debug(f"Archivo soltado en DropZone -> {file_path}")
      if file_path.lower().endswith(".appimage"):
        self.main_window.process_and_add_appimage(file_path)
    event.acceptProposedAction()


class AppImageManager(QMainWindow):

  def __init__(self):
    super().__init__()
    self.setWindowTitle("Sinergia AppImage Manager")
    self.resize(650, 520)
    self.appimages = []

    self.config_dir = Path.home() / ".config" / "appimage_manager"
    self.config_dir.mkdir(parents=True, exist_ok=True)
    self.config_file = self.config_dir / "apps.json"

    self.icon_cache_dir = Path.home() / ".cache" / "appimage_manager_icons"
    self.icon_cache_dir.mkdir(parents=True, exist_ok=True)

    self.desktop_apps_dir = Path.home() / ".local" / "share" / "applications"
    self.desktop_apps_dir.mkdir(parents=True, exist_ok=True)

    self.managed_appimages_dir = (
        Path.home() / ".local" / "share" / "sinergia" / "appimages"
    )
    self.managed_appimages_dir.mkdir(parents=True, exist_ok=True)

    self.setStyleSheet("""
            QMainWindow {
                background-color: #16161e;
            }
            QPushButton {
                background-color: #24283b;
                color: #c0caf5;
                border: 1px solid #292e42;
                border-radius: 8px;
                padding: 10px 16px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #292e42;
                border-color: #3b4261;
            }
            QPushButton#btn_run {
                background-color: #3d59a1;
                color: white;
                border: none;
            }
            QPushButton#btn_run:hover {
                background-color: #4c6fc1;
            }
            QPushButton#btn_remove {
                background-color: #f7768e;
                color: white;
                border: none;
            }
            QPushButton#btn_remove:hover {
                background-color: #db4b4b;
            }
            QListWidget {
                background-color: #1f2335;
                border: 1px solid #292e42;
                border-radius: 12px;
                font-size: 13px;
                color: #c0caf5;
                padding: 5px;
            }
            QListWidget::item {
                background-color: #24283b;
                margin: 4px 6px;
                padding: 10px;
                border-radius: 8px;
                border: 1px solid transparent;
            }
            QListWidget::item:hover {
                background-color: #292e42;
                border: 1px solid #3b4261;
            }
            QListWidget::item:selected {
                background-color: #3d59a1;
                color: #ffffff;
            }
        """)

    layout = QVBoxLayout()
    layout.setContentsMargins(20, 20, 20, 20)
    layout.setSpacing(15)

    self.drop_zone = DropZoneWidget(self)
    layout.addWidget(self.drop_zone)

    self.list_widget = QListWidget()
    self.list_widget.setIconSize(QSize(36, 36))
    layout.addWidget(self.list_widget)

    btn_layout = QHBoxLayout()
    self.btn_add = QPushButton("Añadir con Botón")
    self.btn_remove = QPushButton("Quitar de la lista")
    self.btn_remove.setObjectName("btn_remove")
    self.btn_run = QPushButton("Ejecutar Seleccionada")
    self.btn_run.setObjectName("btn_run")

    self.btn_add.clicked.connect(self.add_appimage_dialog)
    self.btn_run.clicked.connect(self.run_appimage)
    self.btn_remove.clicked.connect(self.remove_appimage)

    btn_layout.addWidget(self.btn_add)
    btn_layout.addWidget(self.btn_remove)
    btn_layout.addWidget(self.btn_run)
    layout.addLayout(btn_layout)

    container = QWidget()
    container.setLayout(layout)
    self.setCentralWidget(container)

    self.load_saved_apps()

  def load_saved_apps(self):
    if self.config_file.exists():
      try:
        with open(self.config_file, "r", encoding="utf-8") as f:
          saved_paths = json.load(f)
          for path_str in saved_paths:
            if os.path.exists(path_str):
              self.add_appimage_to_ui(path_str, save=False)
      except Exception as e:
        logging.error(f"Error al cargar las apps guardadas: {e}")

  def save_apps(self):
    try:
      with open(self.config_file, "w", encoding="utf-8") as f:
        json.dump(self.appimages, f, indent=4)
    except Exception as e:
      logging.error(f"Error al guardar las apps: {e}")

  def extract_assets_and_integrate(self, app_path):
    icon_dest_path = None
    try:
      with tempfile.TemporaryDirectory() as tmpdir:
        result = subprocess.run(
            [app_path, "--appimage-extract"],
            cwd=tmpdir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if result.returncode != 0:
          return None

        squashfs_root = Path(tmpdir) / "squashfs-root"
        if not squashfs_root.exists():
          return None

        desktop_files = list(squashfs_root.glob("*.desktop"))
        target_icon_name = None

        if desktop_files:
          try:
            with open(
                desktop_files[0], "r", encoding="utf-8", errors="ignore"
            ) as f:
              for line in f:
                if line.startswith("Icon="):
                  target_icon_name = line.strip().split("=", 1)[1]
                  break
          except Exception:
            pass

        png_files = list(squashfs_root.glob("**/*.png"))
        chosen_png = None

        if target_icon_name:
          for p in png_files:
            if (
                target_icon_name.lower() in p.stem.lower()
                or p.name == f"{target_icon_name}.png"
            ):
              chosen_png = p
              break

        if not chosen_png and png_files:
          chosen_png = png_files[0]

        if chosen_png and chosen_png.exists():
          icon_dest_path = (
              self.icon_cache_dir / f"{Path(app_path).stem}_{chosen_png.name}"
          )
          shutil.copy(chosen_png, icon_dest_path)

        if desktop_files:
          desktop_src = desktop_files[0]
          lines = []
          with open(desktop_src, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
              if line.startswith("Exec="):
                lines.append(f"Exec={app_path}\n")
              elif line.startswith("Icon=") and icon_dest_path:
                lines.append(f"Icon={icon_dest_path}\n")
              elif line.startswith("TryExec="):
                lines.append(f"TryExec={app_path}\n")
              else:
                lines.append(line)

          dest_desktop = (
              self.desktop_apps_dir / f"{Path(app_path).stem}.desktop"
          )
          with open(dest_desktop, "w", encoding="utf-8") as f:
            f.writelines(lines)
          os.chmod(dest_desktop, 0o755)

          subprocess.run(
              ["update-desktop-database", str(self.desktop_apps_dir)],
              stdout=subprocess.DEVNULL,
              stderr=subprocess.DEVNULL,
          )

    except Exception as e:
      logging.error(f"Error en la extracción/integración: {e}")

    return str(icon_dest_path) if icon_dest_path else None

  def add_appimage_to_ui(self, file_path, save=True):
    path = Path(file_path)
    if str(path) in self.appimages:
      return

    try:
      os.chmod(path, 0o755)
      icon_path = self.extract_assets_and_integrate(str(path))

      item = QListWidgetItem(path.name)
      if icon_path and os.path.exists(icon_path):
        item.setIcon(QIcon(icon_path))

      self.list_widget.addItem(item)
      self.appimages.append(str(path))

      if save:
        self.save_apps()
    except Exception as e:
      logging.error(f"Error al procesar el AppImage: {e}")

  def process_and_add_appimage(self, file_path):
    source_path = Path(file_path)

    if not source_path.is_relative_to(self.managed_appimages_dir):
      target_path = self.managed_appimages_dir / source_path.name
      try:
        shutil.move(str(source_path), str(target_path))
        file_path = str(target_path)
        logging.debug(f"AppImage movida a carpeta segura -> {file_path}")
      except Exception as e:
        logging.error(f"Error al mover el AppImage a la carpeta segura: {e}")
        file_path = str(source_path)

    self.add_appimage_to_ui(file_path, save=True)

  def add_appimage_dialog(self):
    file_path, _ = QFileDialog.getOpenFileName(
        self, "Seleccionar AppImage", "", "AppImages (*.AppImage);;Todos (*)"
    )
    if file_path:
      self.process_and_add_appimage(file_path)

  def remove_appimage(self):
    selected_items = self.list_widget.selectedItems()
    if not selected_items:
      QMessageBox.warning(
          self,
          "Atención",
          "Por favor selecciona de la lista el AppImage que deseas quitar.",
      )
      return

    index = self.list_widget.row(selected_items[0])
    removed_path = self.appimages[index]

    desktop_file = (
        self.desktop_apps_dir / f"{Path(removed_path).stem}.desktop"
    )
    if desktop_file.exists():
      desktop_file.unlink()
      subprocess.run(
          ["update-desktop-database", str(self.desktop_apps_dir)],
          stdout=subprocess.DEVNULL,
          stderr=subprocess.DEVNULL,
      )

    self.list_widget.takeItem(index)
    self.appimages.pop(index)
    self.save_apps()

  def run_appimage(self):
    selected_items = self.list_widget.selectedItems()
    if not selected_items:
      QMessageBox.warning(
          self, "Atención", "Por favor selecciona un AppImage de la lista."
      )
      return

    index = self.list_widget.row(selected_items[0])
    app_path = self.appimages[index]

    try:
      subprocess.Popen([app_path])
    except Exception as e:
      QMessageBox.critical(
          self, "Error", f"No se pudo ejecutar la aplicación: {e}"
      )


if __name__ == "__main__":
  app = QApplication(sys.argv)
  window = AppImageManager()
  window.show()
  sys.exit(app.exec())
