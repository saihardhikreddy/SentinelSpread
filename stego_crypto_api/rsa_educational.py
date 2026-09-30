"""
Educational RSA & BigInt Module
-------------------------------
Demonstrates fundamental RSA key generation, Miller-Rabin primality testing,
and raw modular exponentiation cryptography for educational sandboxing.
"""

import random
from typing import Dict, Any, Tuple

def power(x: int, y: int, p: int) -> int:
    """Compute (x^y) % p in O(log y)."""
    res = 1
    x = x % p
    while y > 0:
        if y & 1:
            res = (res * x) % p
        y = y >> 1
        x = (x * x) % p
    return res

def miller_rabin(n: int, k: int = 20) -> bool:
    """
    Miller-Rabin probabilistic primality test for integer n with k rounds.
    """
    if n <= 1 or n == 4:
        return False
    if n <= 3:
        return True
    if n % 2 == 0:
        return False

    d = n - 1
    s = 0
    while d % 2 == 0:
        d //= 2
        s += 1

    for _ in range(k):
        a = random.randint(2, n - 2)
        x = power(a, d, n)
        if x == 1 or x == n - 1:
            continue
        
        composite = True
        for _ in range(s - 1):
            x = power(x, 2, n)
            if x == n - 1:
                composite = False
                break
        if composite:
            return False

    return True

def generate_large_prime(bits: int = 512) -> int:
    """Generate a random prime integer of specified bit length."""
    while True:
        num = random.getrandbits(bits)
        num |= (1 << (bits - 1)) | 1
        if miller_rabin(num, k=20):
            return num

def egcd(a: int, b: int) -> Tuple[int, int, int]:
    """Extended Euclidean Algorithm. Returns (g, x, y) such that a*x + b*y = g."""
    if a == 0:
        return b, 0, 1
    g, y, x = egcd(b % a, a)
    return g, x - (b // a) * y, y

def modinv(a: int, m: int) -> int:
    """Compute modular multiplicative inverse of a modulo m."""
    g, x, _ = egcd(a, m)
    if g != 1:
        raise Exception('Modular inverse does not exist')
    return x % m

def generate_key_pair(bits: int = 1024) -> Dict[str, Any]:
    """
    Generate BigInt RSA key pair (n, e, d).
    """
    p = generate_large_prime(bits // 2)
    q = generate_large_prime(bits // 2)
    while p == q:
        q = generate_large_prime(bits // 2)

    n = p * q
    phi = (p - 1) * (q - 1)
    e = 65537
    d = modinv(e, phi)

    return {
        "p": str(p),
        "q": str(q),
        "n": str(n),
        "phi": str(phi),
        "publicKey": {"e": str(e), "n": str(n)},
        "privateKey": {"d": str(d), "n": str(n)}
    }

def rsa_edu_encrypt(plaintext: str, public_key: Dict[str, str]) -> str:
    """Encrypt string to decimal ciphertext string using (m^e) % n."""
    e = int(public_key["e"])
    n = int(public_key["n"])
    
    m_int = int.from_bytes(plaintext.encode('utf-8'), byteorder='big')
    if m_int >= n:
        raise ValueError("Plaintext message is too large for modulus n.")
        
    c_int = power(m_int, e, n)
    return str(c_int)

def rsa_edu_decrypt(ciphertext_str: str, private_key: Dict[str, str]) -> str:
    """Decrypt decimal ciphertext string using (c^d) % n."""
    d = int(private_key["d"])
    n = int(private_key["n"])
    c_int = int(ciphertext_str)
    
    m_int = power(c_int, d, n)
    byte_len = (m_int.bit_length() + 7) // 8
    m_bytes = m_int.to_bytes(byte_len, byteorder='big')
    return m_bytes.decode('utf-8', errors='replace')

def format_public_key_pem(pub_key: Dict[str, str]) -> str:
    """Format educational public key to pseudo-PEM block for display."""
    return f"-----BEGIN PUBLIC KEY-----\nModulus (n): {pub_key['n']}\nExponent (e): {pub_key['e']}\n-----END PUBLIC KEY-----"

def format_private_key_pem(priv_key: Dict[str, str]) -> str:
    """Format educational private key to pseudo-PEM block for display."""
    return f"-----BEGIN PRIVATE KEY-----\nModulus (n): {priv_key['n']}\nExponent (d): {priv_key['d']}\n-----END PRIVATE KEY-----"
