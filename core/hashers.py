from django.contrib.auth.hashers import BasePasswordHasher


class PlainTextPasswordHasher(BasePasswordHasher):
    """
    A custom password hasher that stores passwords in plain text.
    This is for development/testing purposes only and should not be used in production.
    """
    
    algorithm = 'plain_text'
    
    def encode(self, password, salt):
        """
        Return the password as-is without any hashing.
        The salt parameter is ignored since we're storing plain text.
        """
        # For plain text storage, we don't need to use salt
        # We just return a string that indicates the algorithm and the password
        return f"plain_text${password}"
    
    def verify(self, password, encoded):
        """
        Verify the password by simple string comparison.
        """
        # Extract the plain text password from the encoded string
        if encoded.startswith('plain_text$'):
            stored_password = encoded[11:]  # Remove 'plain_text$' prefix
            return password == stored_password
        return False
    
    def safe_summary(self, encoded):
        """
        Return a summary of the encoded password for display purposes.
        """
        return {
            'algorithm': 'plain_text',
            'password': encoded if encoded.startswith('plain_text$') else 'Unknown'
        }
    
    def must_update(self, encoded):
        """
        Return False to indicate that the password doesn't need to be updated.
        """
        return False