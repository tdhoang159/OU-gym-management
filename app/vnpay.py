import hashlib
import hmac
from urllib.parse import quote_plus


class Vnpay:
  def __init__(self):
    self.request_data = {}
    self.response_data = {}

  def add_param(self, key, value):
    if value is None or value == "":
      return
    self.request_data[key] = value

  def _sorted_query(self, data):
    sorted_items = sorted(data.items())
    query = ""
    for idx, (key, value) in enumerate(sorted_items):
      prefix = "&" if idx else ""
      query += f"{prefix}{key}={quote_plus(str(value))}"
    return query

  def get_payment_url(self, base_url, secret_key):
    query = self._sorted_query(self.request_data)
    secure_hash = self._hmacsha512(secret_key, query)
    return f"{base_url}?{query}&vnp_SecureHashType=HmacSHA512&vnp_SecureHash={secure_hash}"

  def validate_response(self, secret_key):
    response = self.response_data.copy()
    secure_hash = response.pop("vnp_SecureHash", None)
    response.pop("vnp_SecureHashType", None)

    hash_data = self._sorted_query({k: v for k, v in response.items() if str(k).startswith("vnp_")})
    expected_hash = self._hmacsha512(secret_key, hash_data)
    return secure_hash and secure_hash.upper() == expected_hash

  @staticmethod
  def _hmacsha512(key, data):
    return (
        hmac.new(key.encode("utf-8"), data.encode("utf-8"), hashlib.sha512)
        .hexdigest()
        .upper()
    )
