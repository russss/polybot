from io import BytesIO
from pathlib import Path

from PIL import Image as PILImage

from polybot.image import Image


def count_pixels(image):
    img = PILImage.open(BytesIO(image.data))
    return img.size[0] * img.size[1]


def test_image_resize():
    img = Image(
        path=Path(__file__).parent / "images" / "sample.png", mime_type="image/png"
    )

    original_size = len(img.data)

    resized = img.resize_to_target(original_size + 1)
    assert img == resized

    for target_bytes in (1000000, 1500000):
        resized = img.resize_to_target(target_bytes)
        assert img.mime_type == resized.mime_type
        assert len(resized.data) <= target_bytes

    for target_pixels in (1200 * 1200, 1000 * 1000):
        resized = img.resize_to_target(5000000, target_pixels)
        assert count_pixels(resized) <= target_pixels
