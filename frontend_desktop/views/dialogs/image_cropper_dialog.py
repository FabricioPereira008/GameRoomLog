import os
import uuid
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QLabel
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QWheelEvent

class ImageCropperDialog(QDialog):
    def __init__(self, image_path: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ajustar Capa do Jogo")
        self.setFixedSize(540, 600)
        
        qss_path = os.path.join(os.path.dirname(__file__), "..", "..", "styles", "dark_theme.qss")
        if os.path.exists(qss_path):
            with open(qss_path, "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())

        self.image_path = image_path
        self.cropped_filepath = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)
        
        lbl = QLabel("Arraste a imagem para reposicionar e use a roda do mouse para dar zoom.")
        lbl.setStyleSheet("color: #94a3b8; font-weight: bold;")
        lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl)
        
        self.view = QGraphicsView()
        self.view.setFixedSize(300, 450)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.view.setDragMode(QGraphicsView.ScrollHandDrag)
        self.view.setStyleSheet("border: 2px dashed #7f5af0; background-color: #0c0d12; border-radius: 8px;")
        
        self.scene = QGraphicsScene(self)
        self.scene.setSceneRect(-2000, -2000, 4000, 4000)
        self.view.setScene(self.scene)
        
        # Load pixmap
        pixmap = QPixmap(self.image_path)
        self.pixmap_item = QGraphicsPixmapItem(pixmap)
        
        # Define o ponto de origem da transformação no centro da imagem
        pw = pixmap.width()
        ph = pixmap.height()
        self.pixmap_item.setTransformOriginPoint(pw / 2.0, ph / 2.0)
        self.pixmap_item.setPos(-pw / 2.0, -ph / 2.0)
        self.scene.addItem(self.pixmap_item)
        
        # Escala inicial perfeita para preencher o enquadramento 300x450 mantendo o centro
        if pw > 0 and ph > 0:
            scale_w = 300.0 / pw
            scale_h = 450.0 / ph
            scale = max(scale_w, scale_h)
            self.pixmap_item.setScale(scale)
            
        layout.addWidget(self.view, alignment=Qt.AlignCenter)
        
        btn_box = QHBoxLayout()
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setProperty("class", "cancel-btn")
        btn_cancel.clicked.connect(self.reject)
        
        btn_save = QPushButton("Cortar e Salvar")
        btn_save.setProperty("class", "action-btn")
        btn_save.clicked.connect(self.crop_and_accept)
        
        btn_box.addStretch()
        btn_box.addWidget(btn_cancel)
        btn_box.addWidget(btn_save)
        layout.addLayout(btn_box)

        self.view.wheelEvent = self.on_wheel_event
        self.view.centerOn(0, 0)

    def on_wheel_event(self, event: QWheelEvent):
        zoom_in_factor = 1.1
        zoom_out_factor = 1.0 / zoom_in_factor
        if event.angleDelta().y() > 0:
            zoom_factor = zoom_in_factor
        else:
            zoom_factor = zoom_out_factor

        current_scale = self.pixmap_item.scale()
        self.pixmap_item.setScale(current_scale * zoom_factor)

    def crop_and_accept(self):
        self.view.setStyleSheet("border: none; background-color: transparent;")
        cropped_pixmap = self.view.grab()
        
        temp_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "backend", "storage", "covers")
        os.makedirs(temp_dir, exist_ok=True)
        filename = f"crop_{uuid.uuid4().hex}.jpg"
        filepath = os.path.join(temp_dir, filename)
        
        cropped_pixmap.save(filepath, "JPG", quality=92)
        self.cropped_filepath = filepath
        
        self.accept()
