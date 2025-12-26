"""Utilities for encoding tile images to different formats."""

import io

from PIL import Image


class ImageEncoder:
    """Utilities for encoding tile images to different formats.

    Provides conversion between image formats, primarily for output handlers
    that support multiple image formats (e.g., MBTiles with PNG/JPEG support).
    """

    @staticmethod
    def encode_png_to_jpeg(png_data: bytes, quality: int = 80) -> bytes:
        """Convert PNG bytes to JPEG.

        JPEG doesn't support transparency (alpha channel), so RGBA images are
        composited onto a white background before conversion.

        Args:
            png_data: PNG image bytes
            quality: JPEG quality 1-100 (higher = better quality, larger file)

        Returns:
            JPEG image bytes

        Raises:
            ValueError: If quality is not in range 1-100
        """
        if not 1 <= quality <= 100:
            raise ValueError(f"JPEG quality must be 1-100, got {quality}")

        img = Image.open(io.BytesIO(png_data))

        # Convert RGBA to RGB (JPEG doesn't support alpha)
        if img.mode == "RGBA":
            # Create white background
            background = Image.new("RGB", img.size, (255, 255, 255))
            # Composite using alpha channel as mask
            background.paste(img, mask=img.split()[3])
            img = background
        elif img.mode != "RGB":
            # Convert other modes to RGB
            img = img.convert("RGB")

        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=quality)
        return buffer.getvalue()

    @staticmethod
    def encode_tile(tile_data_png: bytes, image_format: str, jpeg_quality: int = 80) -> bytes:
        """Encode tile to target format.

        This is a convenience method that routes to the appropriate encoder
        based on the requested format.

        Args:
            tile_data_png: PNG bytes from compositor
            image_format: "png" or "jpg"
            jpeg_quality: JPEG quality if format is jpg (1-100)

        Returns:
            Encoded image bytes

        Raises:
            ValueError: If image_format is not supported or jpeg_quality is invalid
        """
        if image_format == "png":
            # PNG passthrough - no conversion needed
            return tile_data_png
        elif image_format == "jpg":
            return ImageEncoder.encode_png_to_jpeg(tile_data_png, jpeg_quality)
        else:
            raise ValueError(f"Unsupported image format: {image_format}. Supported: 'png', 'jpg'")
