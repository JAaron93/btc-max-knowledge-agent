"""
Cryptographically-secure padding strategy for password generation.

This module implements a secure padding strategy that uses Python's `secrets` module
to ensure every extra character is selected uniformly at random from the full charset,
preserving entropy and cryptographic security.
"""

import secrets
from typing import List


class SecurePaddingStrategy:
    """
    A cryptographically-secure padding strategy that uses secrets.choice()
    to select random characters from the charset uniformly.

    This approach ensures:
    1. Cryptographic randomness using secrets module
    2. Uniform distribution across the entire charset
    3. Maximum entropy preservation
    4. No predictable patterns in padding
    """

    def __init__(self, charset: str):
        """
        Initialize the padding strategy with a character set.

        Args:
            charset: String containing all valid characters for padding
        """
        if not charset:
            raise ValueError("Charset cannot be empty")

        self.charset = charset

    def add_padding(self, base_password: str, target_length: int) -> str:
        """
        Add cryptographically-secure random padding to reach target length.

        Args:
            base_password: The base password to pad
            target_length: Desired final length of the password

        Returns:
            Padded password with secure random characters

        Raises:
            ValueError: If target_length is less than base password length
        """
        if target_length < len(base_password):
            raise ValueError("Target length must be >= base password length")

        padding_needed = target_length - len(base_password)

        if padding_needed == 0:
            return base_password

        # Generate cryptographically secure random padding
        padding_chars = [secrets.choice(self.charset) for _ in range(padding_needed)]

        return base_password + "".join(padding_chars)

    def add_padding_distributed(self, base_password: str, target_length: int) -> str:
        """
        Add padding distributed throughout the password for better mixing.

        Args:
            base_password: The base password to pad
            target_length: Desired final length of the password

        Returns:
            Password with padding distributed throughout
        """
        if target_length < len(base_password):
            raise ValueError("Target length must be >= base password length")

        padding_needed = target_length - len(base_password)

        if padding_needed == 0:
            return base_password

        # Convert to list for easier manipulation
        result_chars = list(base_password)

        # Insert padding characters at random positions
        for _ in range(padding_needed):
            padding_char = secrets.choice(self.charset)
            # Choose random position to insert (including end)
            insert_position = secrets.randbelow(len(result_chars) + 1)
            result_chars.insert(insert_position, padding_char)

        return "".join(result_chars)

    def get_charset_info(self) -> dict:
        """
        Get information about the charset being used.

        Returns:
            Dictionary containing charset statistics
        """
        return {
            "charset": self.charset,
            "charset_length": len(self.charset),
            "entropy_per_char": len(self.charset).bit_length() - 1,
            "contains_lowercase": any(c.islower() for c in self.charset),
            "contains_uppercase": any(c.isupper() for c in self.charset),
            "contains_digits": any(c.isdigit() for c in self.charset),
            "contains_symbols": any(not c.isalnum() for c in self.charset),
        }


# Example usage and demonstration
if __name__ == "__main__":
    # Define a comprehensive charset
    FULL_CHARSET = (
        "abcdefghijklmnopqrstuvwxyz"
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        "0123456789"
        "!@#$%^&*()_+-=[]{}|;:,.<>?"
    )

    # Initialize the padding strategy
    padding_strategy = SecurePaddingStrategy(FULL_CHARSET)

    # Example base password
    base_password = "MySecure123"
    target_length = 20

    print("Cryptographically-Secure Padding Strategy Demo")
    print("=" * 50)
    print(f"Base password: {base_password}")
    print(f"Target length: {target_length}")
    print(f"Padding needed: {target_length - len(base_password)}")
    print()

    # Show charset information
    charset_info = padding_strategy.get_charset_info()
    print("Charset Information:")
    print(f"  Length: {charset_info['charset_length']} characters")
    print(f"  Entropy per character: ~{charset_info['entropy_per_char']} bits")
    print(f"  Contains lowercase: {charset_info['contains_lowercase']}")
    print(f"  Contains uppercase: {charset_info['contains_uppercase']}")
    print(f"  Contains digits: {charset_info['contains_digits']}")
    print(f"  Contains symbols: {charset_info['contains_symbols']}")
    print()

    # Demonstrate end padding
    print("End Padding Examples:")
    for i in range(3):
        padded = padding_strategy.add_padding(base_password, target_length)
        print(f"  {i+1}: {padded}")
    print()

    # Demonstrate distributed padding
    print("Distributed Padding Examples:")
    for i in range(3):
        padded = padding_strategy.add_padding_distributed(base_password, target_length)
        print(f"  {i+1}: {padded}")
    print()

    # Show entropy analysis
    total_entropy = charset_info["charset_length"].bit_length() - 1
    padding_entropy = (target_length - len(base_password)) * total_entropy
    print(f"Entropy Analysis:")
    print(f"  Entropy per padding character: ~{total_entropy} bits")
    print(f"  Total padding entropy: ~{padding_entropy} bits")
    print(f"  Security: Each padding character is cryptographically random")
