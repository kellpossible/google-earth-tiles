"""GeoTIFF format generator."""

import io
import logging
import math
from pathlib import Path

import numpy as np
from osgeo import gdal, osr
from PIL import Image

from src.core.base_tile_generator import BaseTileGenerator
from src.core.tile_calculator import TileCalculator
from src.models.extent import Extent
from src.models.layer_composition import LayerComposition

logger = logging.getLogger(__name__)

# Enable GDAL exceptions for better error handling
gdal.UseExceptions()


class GeoTIFFGenerator(BaseTileGenerator):
    """Generator for GeoTIFF format files.

    Creates georeferenced TIFF files with optional multi-zoom pyramids (overviews),
    compression, and proper coordinate reference system (EPSG:3857 Web Mercator).
    """

    # Web Mercator (EPSG:3857) constants
    EARTH_RADIUS = 6378137.0  # meters
    ORIGIN_SHIFT = math.pi * EARTH_RADIUS  # 20037508.34 meters

    @staticmethod
    def _lon_to_meters(lon: float) -> float:
        """Convert WGS84 longitude to Web Mercator X coordinate in meters.

        Args:
            lon: Longitude in degrees (-180 to 180)

        Returns:
            X coordinate in meters
        """
        return lon * GeoTIFFGenerator.ORIGIN_SHIFT / 180.0

    @staticmethod
    def _lat_to_meters(lat: float) -> float:
        """Convert WGS84 latitude to Web Mercator Y coordinate in meters.

        Args:
            lat: Latitude in degrees (-85.051129 to 85.051129)

        Returns:
            Y coordinate in meters
        """
        lat_rad = math.radians(lat)
        y = math.log(math.tan(math.pi / 4 + lat_rad / 2)) * GeoTIFFGenerator.EARTH_RADIUS
        return y

    def _calculate_geotransform(
        self, extent: Extent, zoom: int, width_px: int, height_px: int
    ) -> tuple[float, float, float, float, float, float]:
        """Calculate GDAL geotransform for Web Mercator raster.

        GeoTransform is a 6-element tuple that defines the relationship between
        pixel coordinates and geographic coordinates:
        [top_left_x, pixel_width, rotation_x, top_left_y, rotation_y, -pixel_height]

        Args:
            extent: Geographic extent in WGS84
            zoom: Zoom level
            width_px: Raster width in pixels
            height_px: Raster height in pixels

        Returns:
            Tuple of 6 geotransform values
        """
        # Convert WGS84 extent to Web Mercator meters
        min_x = self._lon_to_meters(extent.min_lon)
        max_x = self._lon_to_meters(extent.max_lon)
        min_y = self._lat_to_meters(extent.min_lat)
        max_y = self._lat_to_meters(extent.max_lat)

        # Calculate pixel resolution
        pixel_width = (max_x - min_x) / width_px
        pixel_height = (max_y - min_y) / height_px

        # Geotransform: [top_left_x, pixel_width, 0, top_left_y, 0, -pixel_height]
        # Note: pixel_height is negative because raster Y-axis goes top-to-bottom
        return (min_x, pixel_width, 0.0, max_y, 0.0, -pixel_height)

    def _create_spatial_reference(self) -> osr.SpatialReference:
        """Create EPSG:3857 (Web Mercator) spatial reference.

        Returns:
            OSR SpatialReference object for Web Mercator
        """
        srs = osr.SpatialReference()
        srs.ImportFromEPSG(3857)  # Web Mercator
        return srs

    def _create_geotiff_dataset(
        self,
        output_path: Path,
        width: int,
        height: int,
        bands: int,
        geotransform: tuple,
        compression: str = "lzw",
        tiled: bool = True,
        tile_size: int = 256,
    ) -> gdal.Dataset:
        """Create a new GeoTIFF dataset with specified parameters.

        Args:
            output_path: Path for output GeoTIFF file
            width: Raster width in pixels
            height: Raster height in pixels
            bands: Number of bands (3 for RGB, 4 for RGBA)
            geotransform: GDAL geotransform tuple
            compression: Compression type ("lzw", "deflate", "jpeg", "none")
            tiled: Use tiled format for efficient partial access
            tile_size: Internal tile size (256 or 512)

        Returns:
            GDAL Dataset object
        """
        driver = gdal.GetDriverByName("GTiff")

        # Build creation options
        options = []

        if tiled:
            options.extend(
                [
                    "TILED=YES",
                    f"BLOCKXSIZE={tile_size}",
                    f"BLOCKYSIZE={tile_size}",
                ]
            )

        # Add compression
        if compression != "none":
            options.append(f"COMPRESS={compression.upper()}")

        # BigTIFF support for large files
        options.append("BIGTIFF=IF_SAFER")

        # Multi-threaded compression
        options.append("NUM_THREADS=ALL_CPUS")

        # For JPEG compression, force RGB (no alpha)
        if compression == "jpeg":
            options.append("PHOTOMETRIC=YCBCR")
            if bands == 4:
                logger.warning("JPEG compression does not support alpha channel, using RGB only")
                bands = 3

        logger.info(f"Creating GeoTIFF: {width}x{height}px, {bands} bands, compression={compression}")
        logger.info(f"Creation options: {options}")

        # Create dataset
        dataset = driver.Create(
            str(output_path),
            width,
            height,
            bands,
            gdal.GDT_Byte,  # 8-bit unsigned integer per band
            options=options,
        )

        if dataset is None:
            raise RuntimeError(f"Failed to create GeoTIFF dataset: {output_path}")

        # Set geotransform
        dataset.SetGeoTransform(geotransform)

        # Set spatial reference (EPSG:3857)
        srs = self._create_spatial_reference()
        dataset.SetProjection(srs.ExportToWkt())

        logger.info("GeoTIFF dataset created successfully")
        return dataset

    def _write_tile_to_raster(
        self, dataset: gdal.Dataset, tile_data: bytes, x_offset: int, y_offset: int, bands: int
    ) -> None:
        """Write a single tile to the raster dataset.

        Args:
            dataset: GDAL dataset
            tile_data: PNG or JPEG tile data as bytes
            x_offset: Pixel X offset in raster
            y_offset: Pixel Y offset in raster
            bands: Number of bands in dataset (3 or 4)
        """
        # Decode tile to numpy array
        img = Image.open(io.BytesIO(tile_data))

        # Convert to RGBA if needed
        if img.mode != "RGBA":
            img = img.convert("RGBA")

        # Convert to numpy array
        tile_array = np.array(img)

        # Write each band
        for band_idx in range(min(bands, 4)):  # Write up to bands available
            band = dataset.GetRasterBand(band_idx + 1)  # GDAL bands are 1-indexed
            band_data = tile_array[:, :, band_idx]
            band.WriteArray(band_data, x_offset, y_offset)

    def _build_pyramids(self, dataset: gdal.Dataset, min_zoom: int, max_zoom: int) -> None:
        """Build internal overviews (pyramids) for multi-zoom support.

        Args:
            dataset: GDAL dataset
            min_zoom: Minimum zoom level
            max_zoom: Maximum zoom level (base raster)
        """
        if min_zoom >= max_zoom:
            logger.info("Single zoom level, skipping pyramid generation")
            return

        # Calculate overview factors for each zoom level below max_zoom
        # Factor = 2^(max_zoom - zoom)
        overview_factors = [2 ** (max_zoom - z) for z in range(max_zoom - 1, min_zoom - 1, -1)]

        logger.info(f"Building pyramids with overview factors: {overview_factors}")

        # Build overviews using AVERAGE resampling (best for imagery)
        dataset.BuildOverviews("AVERAGE", overview_factors)

        logger.info(f"Created {len(overview_factors)} overview levels")

    def _set_metadata(self, dataset: gdal.Dataset, attribution: str | None = None) -> None:
        """Set GeoTIFF metadata tags.

        Args:
            dataset: GDAL dataset
            attribution: Attribution text
        """
        # Set metadata
        if attribution:
            dataset.SetMetadataItem("TIFFTAG_IMAGEDESCRIPTION", attribution)

        dataset.SetMetadataItem("TIFFTAG_SOFTWARE", "Google Earth Tile Generator")

        # Area or point interpretation
        dataset.SetMetadataItem("AREA_OR_POINT", "Area")

    async def generate_geotiff(
        self,
        extent: Extent,
        min_zoom: int,
        max_zoom: int,
        layer_compositions: list[LayerComposition],
        compression: str = "lzw",
        multi_zoom: bool = True,
        jpeg_quality: int = 80,
        tiled: bool = True,
        tile_size: int = 256,
        attribution: str | None = None,
    ) -> Path:
        """Generate GeoTIFF file with composited layers.

        Args:
            extent: Geographic extent
            min_zoom: Minimum zoom level
            max_zoom: Maximum zoom level
            layer_compositions: List of enabled layer compositions
            compression: Compression type ("lzw", "deflate", "jpeg", "none")
            multi_zoom: Include pyramids for multi-zoom support
            jpeg_quality: JPEG quality 1-100 (only used if compression is jpeg)
            tiled: Use tiled GeoTIFF format
            tile_size: Internal tile size (256 or 512)
            attribution: Attribution text

        Returns:
            Path to created GeoTIFF file
        """
        logger.info(f"Generating GeoTIFF file: {self.output_path}")
        logger.info(f"Extent: {extent.min_lon:.6f},{extent.min_lat:.6f} to {extent.max_lon:.6f},{extent.max_lat:.6f}")
        logger.info(f"Zoom range: {min_zoom}-{max_zoom}, Compression: {compression}, Multi-zoom: {multi_zoom}")

        # Calculate raster dimensions at max_zoom (base resolution)
        tiles_at_max_zoom = TileCalculator.get_tiles_in_extent(
            extent.min_lon, extent.min_lat, extent.max_lon, extent.max_lat, max_zoom
        )

        if not tiles_at_max_zoom:
            raise ValueError("No tiles in extent at max zoom level")

        # Get tile bounds
        min_tile_x = min(x for x, _ in tiles_at_max_zoom)
        max_tile_x = max(x for x, _ in tiles_at_max_zoom)
        min_tile_y = min(y for _, y in tiles_at_max_zoom)
        max_tile_y = max(y for _, y in tiles_at_max_zoom)

        # Calculate raster dimensions
        width_tiles = max_tile_x - min_tile_x + 1
        height_tiles = max_tile_y - min_tile_y + 1
        width_px = width_tiles * 256
        height_px = height_tiles * 256

        logger.info(f"Raster dimensions: {width_px}x{height_px}px ({width_tiles}x{height_tiles} tiles)")

        # Calculate geotransform
        geotransform = self._calculate_geotransform(extent, max_zoom, width_px, height_px)

        # Determine number of bands
        # Use RGBA (4 bands) for PNG, RGB (3 bands) for JPEG compression
        bands = 3 if compression == "jpeg" else 4

        # Create GeoTIFF dataset
        dataset = self._create_geotiff_dataset(
            self.output_path,
            width_px,
            height_px,
            bands,
            geotransform,
            compression,
            tiled,
            tile_size,
        )

        try:
            # Set metadata
            self._set_metadata(dataset, attribution)

            # Calculate total tiles for progress tracking
            total_tiles = len(tiles_at_max_zoom)

            # Fetch and write tiles
            logger.info(f"Fetching and writing {total_tiles} tiles...")

            for processed, (x, y) in enumerate(sorted(tiles_at_max_zoom, key=lambda t: (t[1], t[0])), start=1):
                # Composite tile
                tile_data = await self.compositor.composite_tile(x, y, max_zoom, layer_compositions)

                if tile_data:
                    # Calculate pixel offset in raster
                    x_offset = (x - min_tile_x) * 256
                    y_offset = (y - min_tile_y) * 256

                    # Write tile to raster
                    self._write_tile_to_raster(dataset, tile_data, x_offset, y_offset, bands)

                if self.progress_callback:
                    self.progress_callback(processed, total_tiles, f"Writing tile {processed}/{total_tiles}...")

            # Flush to disk
            dataset.FlushCache()

            # Build pyramids if multi-zoom enabled
            if multi_zoom:
                logger.info("Building pyramids for multi-zoom support...")
                if self.progress_callback:
                    self.progress_callback(total_tiles, total_tiles, "Building pyramids...")
                self._build_pyramids(dataset, min_zoom, max_zoom)

            logger.info(f"Created GeoTIFF file: {self.output_path}")
            return self.output_path

        finally:
            # Close dataset to flush all data
            dataset = None
            await self.close()
