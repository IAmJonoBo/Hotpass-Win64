#!/usr/bin/env python3
"""
Data Optimization Script for Hotpass
Handles deduplication, validation, and enrichment of organization data.
"""

import logging
import re
import time

import pandas as pd

from .normalization import clean_string, normalize_email

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DataOptimizer:
    def __init__(self, data_path: str):
        self.df = pd.read_excel(data_path)
        self.original_shape = self.df.shape
        logger.info("Loaded %d records", self.original_shape[0])

    def normalize_organization_name(self, name: str | None) -> str:
        """Normalize organization names for better matching using existing utilities."""
        name = clean_string(name)
        if not name:
            return ""
        name = name.lower()
        # Remove common business suffixes
        suffixes = [
            r"\s*\(pty\)|\s*ltd|\s*limited|\s*cc|\s*inc|\s*corp|\s*corporation",
            r"\s*\(pty\)\s*ltd|\s*pty\s*ltd",
            r"\s*\(pvt\)|\s*\(private\)",
            r"\s*trading|\s*as|\s*t/a",
        ]
        for suffix in suffixes:
            name = re.sub(suffix, "", name, flags=re.IGNORECASE)
        # Clean up extra spaces and punctuation
        name = re.sub(r"[^\w\s]", " ", name)
        name = re.sub(r"\s+", " ", name).strip()
        return name

    def find_duplicates(self) -> dict[str, list[int]]:
        """Find potential duplicate organizations using normalized name matching."""
        logger.info("Finding potential duplicates...")
        self.df["normalized_name"] = self.df["organization_name"].apply(
            self.normalize_organization_name
        )

        duplicate_groups: dict[str, list[int]] = {}
        name_to_indices: dict[str, list[int]] = {}

        for idx, row in self.df.iterrows():
            name = row["normalized_name"]
            if name:
                if name not in name_to_indices:
                    name_to_indices[name] = []
                name_to_indices[name].append(idx)

        for normalized_name, indices in name_to_indices.items():
            if len(indices) > 1:
                key = f"{normalized_name} ({self.df.loc[indices[0], 'organization_name']})"
                duplicate_groups[key] = indices

        logger.info("Found %d potential duplicate groups", len(duplicate_groups))
        return duplicate_groups

    def validate_website(self, url: str | None) -> bool:
        """Basic website validation - check if URL format is valid."""
        if pd.isna(url) or not url:
            return False
        # Simple regex for URL validation
        url_pattern = re.compile(
            r"^https?://"  # http:// or https://
            r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"  # domain...
            r"localhost|"  # localhost...
            r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"  # ...or ip
            r"(?::\d+)?"  # optional port
            r"(?:/?|[/?]\S+)$",
            re.IGNORECASE,
        )

        return url_pattern.match(str(url)) is not None

    def validate_emails(self) -> None:
        """Validate and clean email addresses using existing normalization."""
        logger.info("Validating and cleaning emails...")

        email_cols = ["contact_primary_email", "contact_secondary_emails"]
        for col in email_cols:
            if col in self.df.columns:
                # Apply normalization
                self.df[f"{col}_normalized"] = self.df[col].apply(normalize_email)
                # Check validity
                self.df[f"{col}_valid"] = self.df[f"{col}_normalized"].notna()

    def validate_cipc_company(self, name: str) -> dict[str, str | float | None]:
        """Validate company name against CIPC registry.

        Note: This is a placeholder implementation. CIPC doesn't provide a public API,
        so this would need to be implemented with web scraping or a third-party service.
        """
        if not name or pd.isna(name):
            return {"status": "invalid", "registration_number": None, "confidence": 0.0}

        # Placeholder for CIPC validation
        # In a real implementation, this would:
        # 1. Use CIPC's web search interface
        # 2. Or integrate with a service like CompanyCheck.co.za
        # 3. Or use official CIPC APIs if available

        # For now, return a basic structure
        return {
            "status": "unknown",  # could be "active", "deregistered", "unknown"
            "registration_number": None,
            "confidence": 0.0,
            "last_updated": None,
        }

    def validate_organization_names_online(self) -> None:
        """Validate organization names against external registries."""
        logger.info("Validating organization names against external registries...")

        # Rate limiting - don't overwhelm external services
        validated_count = 0

        for idx, row in self.df.iterrows():
            name = row["organization_name"]
            if pd.notna(name) and name.strip():
                validation_result = self.validate_cipc_company(name)
                self.df.at[idx, "cipc_status"] = validation_result.get("status")
                self.df.at[idx, "cipc_registration"] = validation_result.get("registration_number")
                self.df.at[idx, "cipc_confidence"] = validation_result.get("confidence")

                validated_count += 1

                # Rate limiting
                if validated_count % 10 == 0:
                    time.sleep(1)  # Be respectful to external services

        logger.info("Validated %d organization names", validated_count)

    def geocode_address(
        self, address: str, province: str | None = None
    ) -> dict[str, str | float | None]:
        """Geocode address to validate and extract location data.

        Note: This is a placeholder implementation. In production, this would use
        Google Maps API, OpenStreetMap, or similar geocoding service.
        """
        if not address or pd.isna(address):
            return {
                "latitude": None,
                "longitude": None,
                "formatted_address": None,
                "province_validated": None,
                "area_validated": None,
                "confidence": 0.0,
            }

        # Placeholder geocoding logic
        # In a real implementation, this would:
        # 1. Call Google Maps Geocoding API
        # 2. Or use OpenStreetMap Nominatim
        # 3. Parse the response for coordinates and address components

        # For South African addresses, we could extract province/area patterns
        address_lower = str(address).lower()

        # Basic province detection for South Africa
        province_mapping = {
            "gauteng": "Gauteng",
            "western cape": "Western Cape",
            "kwazulu-natal": "KwaZulu-Natal",
            "eastern cape": "Eastern Cape",
            "north west": "North West",
            "limpopo": "Limpopo",
            "mpumalanga": "Mpumalanga",
            "free state": "Free State",
            "northern cape": "Northern Cape",
        }

        detected_province = None
        for key, value in province_mapping.items():
            if key in address_lower:
                detected_province = value
                break

        return {
            "latitude": None,  # Would be filled by geocoding API
            "longitude": None,
            "formatted_address": str(address).strip(),
            "province_validated": detected_province,
            "area_validated": None,  # Would extract area from geocoding
            "confidence": 0.5 if detected_province else 0.0,
        }

    def geocode_addresses(self) -> None:
        """Geocode and validate addresses for missing location data."""
        logger.info("Geocoding and validating addresses...")

        geocoded_count = 0

        for idx, row in self.df.iterrows():
            address = row.get("address_primary")
            province = row.get("province")

            if pd.notna(address) or pd.notna(province):
                geocode_result = self.geocode_address(address, province)

                self.df.at[idx, "latitude"] = geocode_result.get("latitude")
                self.df.at[idx, "longitude"] = geocode_result.get("longitude")
                self.df.at[idx, "address_formatted"] = geocode_result.get("formatted_address")
                self.df.at[idx, "province_geocoded"] = geocode_result.get("province_validated")
                self.df.at[idx, "area_geocoded"] = geocode_result.get("area_validated")
                self.df.at[idx, "geocode_confidence"] = geocode_result.get("confidence")

                geocoded_count += 1

                # Rate limiting for geocoding APIs
                if geocoded_count % 10 == 0:
                    time.sleep(0.1)

        logger.info("Geocoded %d addresses", geocoded_count)

    def optimize_data(self) -> pd.DataFrame:
        """Run all optimization processes."""
        logger.info("Starting data optimization...")

        # Find duplicates
        duplicate_groups = self.find_duplicates()

        # Validate websites
        logger.info("Validating websites...")
        self.df["website_valid"] = self.df["website"].apply(self.validate_website)

        # Validate emails
        self.validate_emails()

        # Validate organization names online
        self.validate_organization_names_online()

        # Geocode addresses
        self.geocode_addresses()

        # Add optimization flags
        self.df["duplicate_group"] = None
        for group_name, indices in duplicate_groups.items():
            for idx in indices:
                self.df.at[idx, "duplicate_group"] = group_name

        # Calculate optimization score
        self.df["optimization_score"] = (
            self.df["website_valid"].astype(int)
            + (~self.df["province"].isna()).astype(int)
            + (~self.df["address_primary"].isna()).astype(int)
            + (self.df.get("contact_primary_email_valid", False)).astype(int)
        ) / 4.0

        logger.info("Optimization complete. Original: %d records", self.original_shape[0])
        logger.info("Duplicates identified: %d groups", len(duplicate_groups))

        return self.df

    def save_optimized_data(self, output_path: str) -> None:
        """Save the optimized dataset."""
        self.df.to_excel(output_path, index=False)
        logger.info("Optimized data saved to %s", output_path)


if __name__ == "__main__":
    optimizer = DataOptimizer("data/refined_data.xlsx")
    optimized_df = optimizer.optimize_data()
    optimizer.save_optimized_data("data/optimized_data.xlsx")

    # Print summary
    duplicate_count = optimized_df["duplicate_group"].notna().sum()
    valid_websites = optimized_df["website_valid"].sum()
    valid_primary_emails = optimized_df.get("contact_primary_email_valid", pd.Series()).sum()
    valid_secondary_emails = optimized_df.get("contact_secondary_emails_valid", pd.Series()).sum()

    print("\nOptimization Summary:")
    print(f"Total records: {len(optimized_df)}")
    print(f"Records in duplicate groups: {duplicate_count}")
    print(f"Valid websites: {valid_websites}")
    print(f"Valid primary emails: {valid_primary_emails}")
    print(f"Valid secondary emails: {valid_secondary_emails}")
    print(f"Average optimization score: {optimized_df['optimization_score'].mean():.2f}")
