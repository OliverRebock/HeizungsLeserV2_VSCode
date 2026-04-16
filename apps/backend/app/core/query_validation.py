"""
Flux Query Whitelisting and Input Sanitization Module

Prevents query injection attacks by validating and sanitizing user inputs
before they are incorporated into Flux queries.
"""

import re
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


class QueryValidationError(ValueError):
    """Raised when input validation fails."""
    pass


class FluxQueryValidator:
    """
    Validates and sanitizes inputs for safe Flux query construction.
    
    Implements strict allowlisting for entity_ids to prevent injection attacks.
    """
    
    # Entity ID pattern: alphanumeric, underscore, dot, dash
    # Examples: sensor.temperature, binary_sensor.motion_detected, climate.heating_system
    ENTITY_ID_PATTERN = re.compile(r'^[a-zA-Z0-9_\.\-]+$')
    
    # Maximum allowed length for entity IDs (InfluxDB tag/field names are 255 chars)
    MAX_ENTITY_ID_LENGTH = 255
    
    # Bucket name pattern: alphanumeric, underscore, dash
    # Must not start with underscore (reserved by InfluxDB)
    BUCKET_PATTERN = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9_\-]*$')
    MAX_BUCKET_LENGTH = 64
    
    # Forbidden patterns in entity_id (Flux injection indicators)
    FORBIDDEN_PATTERNS = [
        r'[\"\'`]',  # Quotes
        r'\|>',      # Flux pipe operator
        r'[\n\r\t]',  # Whitespace that breaks queries
        r'[{}()[\]<>]',  # Special characters
    ]
    
    @classmethod
    def validate_entity_id(cls, entity_id: str) -> str:
        """
        Validates and returns a sanitized entity_id.
        
        Args:
            entity_id: Raw entity ID from user input
            
        Returns:
            Sanitized entity_id safe for use in Flux queries
            
        Raises:
            QueryValidationError: If validation fails
        """
        if not entity_id:
            raise QueryValidationError("Entity ID cannot be empty")
        
        # Strip whitespace
        entity_id = entity_id.strip()
        
        if len(entity_id) > cls.MAX_ENTITY_ID_LENGTH:
            raise QueryValidationError(
                f"Entity ID exceeds max length {cls.MAX_ENTITY_ID_LENGTH}: {len(entity_id)}"
            )
        
        # Check for forbidden patterns first (faster than regex)
        for pattern in cls.FORBIDDEN_PATTERNS:
            if re.search(pattern, entity_id):
                raise QueryValidationError(
                    f"Entity ID contains forbidden characters: {entity_id}"
                )
        
        # Check whitelist pattern
        if not cls.ENTITY_ID_PATTERN.match(entity_id):
            raise QueryValidationError(
                f"Entity ID does not match required pattern (alphanumeric._- only): {entity_id}"
            )
        
        return entity_id
    
    @classmethod
    def validate_entity_ids(cls, entity_ids: List[str]) -> List[str]:
        """
        Validates and returns a list of sanitized entity IDs.
        
        Args:
            entity_ids: List of raw entity IDs from user input
            
        Returns:
            List of sanitized entity_ids
            
        Raises:
            QueryValidationError: If any validation fails
        """
        if not entity_ids:
            raise QueryValidationError("Entity ID list cannot be empty")
        
        if len(entity_ids) > 100:
            raise QueryValidationError(
                f"Too many entity IDs requested: {len(entity_ids)} (max 100)"
            )
        
        validated = []
        for eid in entity_ids:
            validated.append(cls.validate_entity_id(eid))
        
        return validated
    
    @classmethod
    def validate_bucket_name(cls, bucket: str) -> str:
        """
        Validates and returns a sanitized bucket name.
        
        Args:
            bucket: Raw bucket name from database
            
        Returns:
            Sanitized bucket name safe for use in Flux queries
            
        Raises:
            QueryValidationError: If validation fails
        """
        if not bucket:
            raise QueryValidationError("Bucket name cannot be empty")
        
        bucket = bucket.strip()
        
        if len(bucket) > cls.MAX_BUCKET_LENGTH:
            raise QueryValidationError(
                f"Bucket name exceeds max length {cls.MAX_BUCKET_LENGTH}: {len(bucket)}"
            )
        
        # Check whitelist pattern
        if not cls.BUCKET_PATTERN.match(bucket):
            raise QueryValidationError(
                f"Bucket name does not match required pattern: {bucket}"
            )
        
        return bucket
    
    @classmethod
    def escape_flux_string_literal(cls, value: str) -> str:
        """
        Escapes a string for safe use in Flux string literals.
        
        Flux uses double quotes and backslash escaping:
        - \" becomes \\\"
        - \\ becomes \\\\
        
        Args:
            value: String to escape
            
        Returns:
            Escaped string safe for Flux string interpolation
        """
        if not isinstance(value, str):
            value = str(value)
        
        # First escape backslashes, then quotes
        value = value.replace('\\', '\\\\')
        value = value.replace('"', '\\"')
        
        return value
    
    @classmethod
    def build_flux_safe_filter(cls, entity_ids: List[str]) -> str:
        """
        Builds a safe Flux filter expression for entity_ids.
        
        Rather than interpolating entity_ids directly into the query string,
        this builds a filter that matches against InfluxDB tag/field values.
        
        Args:
            entity_ids: Validated entity IDs
            
        Returns:
            Flux filter expression: r["_measurement"] == "id1" or r["_measurement"] == "id2" or ...
        """
        validated_ids = cls.validate_entity_ids(entity_ids)
        
        # Build OR chain: r["_measurement"] == "id1" or r["_measurement"] == "id2" ...
        filter_parts = []
        for eid in validated_ids:
            escaped = cls.escape_flux_string_literal(eid)
            filter_parts.append(f'r["_measurement"] == "{escaped}"')
            filter_parts.append(f'r["entity_id"] == "{escaped}"')
        
        if not filter_parts:
            raise QueryValidationError("No valid entity IDs to filter")
        
        # Join with OR operators
        return ' or '.join(filter_parts)


def validate_query_inputs(entity_ids: List[str], bucket: str) -> tuple:
    """
    Convenience function to validate all query inputs at once.
    
    Args:
        entity_ids: List of entity IDs to validate
        bucket: Bucket name to validate
        
    Returns:
        Tuple of (validated_entity_ids, validated_bucket)
        
    Raises:
        QueryValidationError: If any validation fails
    """
    try:
        validated_eids = FluxQueryValidator.validate_entity_ids(entity_ids)
        validated_bucket = FluxQueryValidator.validate_bucket_name(bucket)
        return validated_eids, validated_bucket
    except QueryValidationError as e:
        logger.warning(f"Query input validation failed: {e}")
        raise
