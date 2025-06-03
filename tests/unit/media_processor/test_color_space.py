import pytest
from PIL import Image
from io import BytesIO
import numpy as np
from media_processor import MediaProcessor

@pytest.fixture
def media_processor():
    return MediaProcessor()

// ... existing code ...