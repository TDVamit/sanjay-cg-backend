import uuid


def generate_uuid() -> str:
    """
    Generate a new UUID4 string
    
    Returns:
        str: A UUID4 string that can be used as a unique identifier
    """
    return str(uuid.uuid4())


def is_valid_uuid(uuid_string: str) -> bool:
    """
    Check if a string is a valid UUID
    
    Args:
        uuid_string: String to validate
        
    Returns:
        bool: True if valid UUID, False otherwise
    """
    try:
        uuid.UUID(uuid_string)
        return True
    except (ValueError, TypeError):
        return False 