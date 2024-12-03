from typing import BinaryIO, Optional
from io import BytesIO
from pathlib import Path
from PIL import Image as PILImage
import logging

log = logging.getLogger(__name__)


class Image:
    """Represents an image to be attached to a Polybot post."""

    def __init__(
        self,
        path: Optional[str | Path] = None,
        file: Optional[BinaryIO] = None,
        data: Optional[bytes] = None,
        mime_type: Optional[str] = None,
        description: Optional[str] = None,
    ):
        """
        Create a new Image object. Provide either a `path`, `file`, or `data`.
        The `mime_type` is required for Mastodon and Twitter.

        Arguments:
            path: Path to the image file.
            file: File-like object containing the image data.
            data: Image file data as bytes.
            mime_type: MIME type of the image.
            description: Description (alt text) of the image.
        """
        if path is not None:
            with open(path, "rb") as f:
                self.data = f.read()
        elif file is not None:
            self.data = file.read()
        elif data is not None:
            self.data = data
        else:
            raise ValueError("Must supply path, file, or data")

        self.mime_type = mime_type
        self.description = description

    def resize_to_target(self, target_bytes: int) -> "Image":
        """Resize the image to a target size in bytes. Returns a new Image object.
        This is required for Bluesky's silly image size limit.
        """
        original_bytes = len(self.data)
        if original_bytes < target_bytes:
            return self

        img = PILImage.open(BytesIO(self.data))

        margin = 0.9
        new_bytes = original_bytes

        while new_bytes > target_bytes:
            current_pixels = img.size[0] * img.size[1]
            new_pixels = int(current_pixels * (target_bytes * margin / original_bytes))
            ratio = (new_pixels / current_pixels) ** 0.5
            new_size = (int(img.width * ratio), int(img.height * ratio))

            new_img = img.resize(new_size)

            output_buf = BytesIO()
            new_img.save(output_buf, format=img.format)
            output_bytes = output_buf.getvalue()
            new_bytes = len(output_bytes)
            log.debug(
                (
                    "Image is too large %s (%d kB). Resizing image to %d%% %s to remain within "
                    "image size limit of %d kB. New size: %d kB"
                ),
                img.size,
                original_bytes // 1024,
                ratio * 100,
                new_size,
                target_bytes // 1024,
                new_bytes // 1024,
            )
            margin -= 0.05

        return Image(
            data=output_bytes, mime_type=self.mime_type, description=self.description
        )

    def __repr__(self):
        return f'Image({self.mime_type}, "{self.description}")'
