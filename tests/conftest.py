import os
from pathlib import Path
import pytest
from src.image_processing import load_image
ROOT=Path(__file__).resolve().parents[1]
@pytest.fixture
def image():return load_image(ROOT/'sample_images'/'perspective.png')

@pytest.fixture(autouse=True)
def isolate_persistent_data(tmp_path,monkeypatch):
    monkeypatch.setenv('SMARTSCAN_DATA_DIR',str(tmp_path/'app-data'))
