"""Geospatial data enrichment and analysis module.

This module provides functionality for:
- Geocoding addresses to coordinates
- Reverse geocoding coordinates to addresses
- Address normalization
- Geospatial clustering and analysis
- Provincial/regional inference
"""

import logging
from typing import Any, cast

import numpy as np
import pandas as pd

try:
    from geopy.exc import GeocoderTimedOut, GeocoderUnavailable
    from geopy.geocoders import Nominatim

    GEOPY_AVAILABLE = True
except ImportError:
    GEOPY_AVAILABLE = False

try:
    import geopandas as gpd
    from shapely.geometry import Point

    GEOPANDAS_AVAILABLE = True
except ImportError:
    GEOPANDAS_AVAILABLE = False

logger = logging.getLogger(__name__)


class GeospatialError(RuntimeError):
    """Raised when geospatial helpers cannot complete their work."""


class Geocoder:
    """Geocoding service wrapper with caching and error handling."""

    def __init__(self, user_agent: str = "Hotpass/1.0", timeout: int = 10):
        """Initialize geocoder.

        Args:
            user_agent: User agent string for geocoding service
            timeout: Timeout for geocoding requests in seconds
        """
        if not GEOPY_AVAILABLE:
            logger.warning("Geopy not available, geocoding will not work")
            self.geolocator = None
        else:
            self.geolocator = Nominatim(user_agent=user_agent, timeout=timeout)

    def geocode_address(self, address: str, country: str | None = None) -> dict[str, Any] | None:
        """Geocode an address to coordinates.

        Args:
            address: Address string to geocode
            country: Optional country to limit search

        Returns:
            Dictionary with latitude, longitude, and formatted address, or None if failed
        """
        if not self.geolocator:
            logger.warning("Geocoder not initialized")
            return None

        if not address or pd.isna(address):
            return None

        try:
            # Build query
            query = address
            if country:
                query = f"{address}, {country}"

            location = self.geolocator.geocode(query)

            if location:
                return {
                    "latitude": location.latitude,
                    "longitude": location.longitude,
                    "formatted_address": location.address,
                    "raw": location.raw,
                }

            return None

        except (GeocoderTimedOut, GeocoderUnavailable) as e:
            logger.warning(f"Geocoding failed for '{address}': {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error geocoding '{address}': {e}")
            return None

    def reverse_geocode(self, latitude: float, longitude: float) -> dict[str, Any] | None:
        """Reverse geocode coordinates to an address.

        Args:
            latitude: Latitude coordinate
            longitude: Longitude coordinate

        Returns:
            Dictionary with address information, or None if failed
        """
        if not self.geolocator:
            logger.warning("Geocoder not initialized")
            return None

        try:
            location = self.geolocator.reverse((latitude, longitude))

            if location:
                return {
                    "formatted_address": location.address,
                    "raw": location.raw,
                }

            return None

        except (GeocoderTimedOut, GeocoderUnavailable) as e:
            logger.warning(f"Reverse geocoding failed: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error during reverse geocoding: {e}")
            return None


def normalize_address(address: str) -> str:
    """Normalize an address string.

    Args:
        address: Address string to normalize

    Returns:
        Normalized address string
    """
    if not address or pd.isna(address):
        return ""

    # Basic normalization
    normalized = address.strip()
    normalized = " ".join(normalized.split())  # Collapse whitespace

    # Common abbreviation expansions - must be done in specific order
    # First handle abbreviations at end of string
    if normalized.endswith(" St"):
        normalized = normalized[:-3] + " Street"
    elif normalized.endswith(" Ave"):
        normalized = normalized[:-4] + " Avenue"
    elif normalized.endswith(" Rd"):
        normalized = normalized[:-3] + " Road"
    elif normalized.endswith(" Blvd"):
        normalized = normalized[:-5] + " Boulevard"
    elif normalized.endswith(" Dr"):
        normalized = normalized[:-3] + " Drive"

    # Then handle abbreviations in the middle
    replacements = {
        " St ": " Street ",
        " St.": " Street",
        " Ave ": " Avenue ",
        " Ave.": " Avenue",
        " Rd ": " Road ",
        " Rd.": " Road",
        " Blvd ": " Boulevard ",
        " Blvd.": " Boulevard",
        " Dr ": " Drive ",
        " Dr.": " Drive",
    }

    for old, new in replacements.items():
        normalized = normalized.replace(old, new)

    return normalized


def geocode_dataframe(
    df: pd.DataFrame,
    address_column: str = "organization_address",
    country_column: str | None = None,
    user_agent: str = "Hotpass/1.0",
) -> pd.DataFrame:
    """Add geocoded coordinates to dataframe.

    Args:
        df: Input dataframe
        address_column: Column containing addresses
        country_column: Optional column containing country names
        user_agent: User agent string for geocoding service

    Returns:
        Dataframe with added latitude, longitude, and formatted_address columns
    """
    if address_column not in df.columns:
        logger.warning(f"Column {address_column} not found in dataframe")
        return df

    geocoder = Geocoder(user_agent=user_agent)
    enriched_df = df.copy()

    # Initialize new columns
    enriched_df["latitude"] = None
    enriched_df["longitude"] = None
    enriched_df["formatted_address"] = None
    enriched_df["geocoded"] = False

    # Geocode each address
    for idx, row in enriched_df.iterrows():
        address = row[address_column]

        if pd.isna(address) or not address:
            continue

        # Get country if available
        country = None
        if country_column and country_column in enriched_df.columns:
            country = row[country_column]

        result = geocoder.geocode_address(address, country=country)

        if result:
            enriched_df.at[idx, "latitude"] = result["latitude"]
            enriched_df.at[idx, "longitude"] = result["longitude"]
            enriched_df.at[idx, "formatted_address"] = result["formatted_address"]
            enriched_df.at[idx, "geocoded"] = True

    geocoded_count = enriched_df["geocoded"].sum()
    logger.info(
        f"Geocoded {geocoded_count}/{len(df)} addresses ({geocoded_count / len(df) * 100:.1f}%)"
    )

    return enriched_df


def infer_province_from_coordinates(
    latitude: float, longitude: float, country: str = "South Africa"
) -> str | None:
    """Infer province/region from coordinates.

    This is a simplified implementation that uses reverse geocoding.
    A production implementation would use proper boundary data.

    Args:
        latitude: Latitude coordinate
        longitude: Longitude coordinate
        country: Country name for context

    Returns:
        Province/region name, or None if inference failed
    """
    geocoder = Geocoder()
    result = geocoder.reverse_geocode(latitude, longitude)

    if result and "raw" in result:
        # Try to extract province from address components
        raw = result["raw"]
        address = raw.get("address", {})

        # Look for province/state in various fields
        province = (
            address.get("state")
            or address.get("province")
            or address.get("region")
            or address.get("county")
        )

        return cast(str | None, province)

    return None


def create_geodataframe(
    df: pd.DataFrame, lat_column: str = "latitude", lon_column: str = "longitude"
) -> "gpd.GeoDataFrame":
    """Convert pandas DataFrame to GeoDataFrame.

    Args:
        df: Input dataframe
        lat_column: Column containing latitude values
        lon_column: Column containing longitude values

    Returns:
        GeoDataFrame with geometry column

    Raises:
        ImportError: If geopandas is not available
    """
    if not GEOPANDAS_AVAILABLE:
        raise ImportError("Geopandas is required for creating GeoDataFrames")

    if lat_column not in df.columns or lon_column not in df.columns:
        raise ValueError(f"Columns {lat_column} and {lon_column} must exist in dataframe")

    # Filter rows with valid coordinates
    valid_coords = df[[lat_column, lon_column]].notna().all(axis=1)
    df_valid = df[valid_coords].copy()

    if len(df_valid) == 0:
        logger.warning("No valid coordinates found in dataframe")
        return gpd.GeoDataFrame(df, geometry=[])

    # Create geometry column
    geometry = [
        Point(lon, lat) for lon, lat in zip(df_valid[lon_column], df_valid[lat_column], strict=True)
    ]

    gdf = gpd.GeoDataFrame(df_valid, geometry=geometry, crs="EPSG:4326")

    logger.info(
        f"Created GeoDataFrame with {len(gdf)}/{len(df)} valid geometries "
        f"({len(gdf) / len(df) * 100:.1f}%)"
    )

    return gdf


def calculate_distance_matrix(
    df: pd.DataFrame, lat_column: str = "latitude", lon_column: str = "longitude"
) -> pd.DataFrame:
    """Calculate pairwise distance matrix between all locations.

    Args:
        df: Input dataframe with coordinates
        lat_column: Column containing latitude values
        lon_column: Column containing longitude values

    Returns:
        Distance matrix dataframe (distances in kilometers)

    Raises:
        GeospatialError: If coordinates are missing or invalid.
    """

    if lat_column not in df.columns or lon_column not in df.columns:
        raise GeospatialError(f"Columns {lat_column!r} and {lon_column!r} must exist in dataframe")

    coordinates = df[[lat_column, lon_column]].copy()
    coordinates = coordinates.dropna(how="any")

    if coordinates.empty:
        raise GeospatialError("No valid coordinates available for distance matrix computation")

    try:
        latitudes = np.radians(pd.to_numeric(coordinates[lat_column], errors="raise").to_numpy())
        longitudes = np.radians(pd.to_numeric(coordinates[lon_column], errors="raise").to_numpy())
    except (TypeError, ValueError) as exc:  # pragma: no cover - exercised via tests
        raise GeospatialError(f"Invalid coordinate data: {exc}") from exc

    lat_diff = latitudes[:, None] - latitudes[None, :]
    lon_diff = longitudes[:, None] - longitudes[None, :]

    sin_lat = np.sin(lat_diff / 2) ** 2
    sin_lon = np.sin(lon_diff / 2) ** 2
    cos_lat = np.cos(latitudes)[:, None] * np.cos(latitudes)[None, :]

    a = sin_lat + cos_lat * sin_lon
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(np.maximum(0.0, 1 - a)))

    earth_radius_km = 6371.0088
    distances_km = earth_radius_km * c

    np.fill_diagonal(distances_km, 0.0)

    logger.info("Calculated %dx%d distance matrix", len(distances_km), len(distances_km))

    return pd.DataFrame(distances_km, index=coordinates.index, columns=coordinates.index)


def cluster_by_proximity(
    df: pd.DataFrame,
    lat_column: str = "latitude",
    lon_column: str = "longitude",
    max_distance_km: float = 50.0,
) -> pd.DataFrame:
    """Cluster locations by geographical proximity.

    Args:
        df: Input dataframe with coordinates
        lat_column: Column containing latitude values
        lon_column: Column containing longitude values
        max_distance_km: Maximum distance for clustering in kilometers

    Returns:
        Dataframe with added cluster_id column
    """
    enriched_df = df.copy()
    enriched_df["geo_cluster_id"] = -1

    try:
        # Calculate distance matrix
        distances = calculate_distance_matrix(df, lat_column, lon_column)

        if distances.empty:
            return enriched_df

        # Simple proximity clustering algorithm
        cluster_id = 0
        unassigned = set(range(len(distances)))

        while unassigned:
            # Pick an unassigned point
            seed = min(unassigned)
            cluster = {seed}
            unassigned.remove(seed)

            # Find all points within max_distance
            for point in list(unassigned):
                if distances.iloc[seed, point] <= max_distance_km:
                    cluster.add(point)
                    unassigned.remove(point)

            # Assign cluster ID
            for point in cluster:
                enriched_df.at[point, "geo_cluster_id"] = cluster_id

            cluster_id += 1

        logger.info(
            f"Created {cluster_id} geographical clusters (max distance: {max_distance_km}km)"
        )

    except GeospatialError as exc:
        logger.error(f"Error clustering by proximity: {exc}")

    return enriched_df
