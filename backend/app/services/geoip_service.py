import logging

from flask import current_app
from geoip2.database import Reader
from geoip2.errors import AddressNotFoundError

from ..utils.validators import is_private_ip

logger = logging.getLogger(__name__)


class GeoIPService:
    def __init__(self, db_path=None):
        self.db_path = db_path or current_app.config["GEOIP_DB_PATH"]
        self._reader = None
        self._error = None
        self._loaded = False

    def _load(self):
        if self._loaded:
            return self._reader
        self._loaded = True
        try:
            self._reader = Reader(self.db_path)
        except Exception as exc:
            self._error = str(exc)
            logger.warning("GeoIP database unavailable at %s: %s", self.db_path, exc)
        return self._reader

    @property
    def available(self):
        return self._load() is not None

    @property
    def error(self):
        self._load()
        return self._error

    def lookup(self, ip):
        if not ip:
            return {"country": None, "is_private": False, "error": "missing_ip"}

        if is_private_ip(ip):
            return {"country": None, "is_private": True}

        reader = self._load()
        if reader is None:
            return {
                "country": None,
                "is_private": False,
                "error": self._error or "geoip_unavailable",
            }

        try:
            response = reader.country(ip)
            return {
                "country": response.country.iso_code,
                "is_private": False,
            }
        except AddressNotFoundError:
            return {
                "country": None,
                "is_private": False,
                "error": "address_not_found",
            }
        except ValueError:
            return {"country": None, "is_private": False, "error": "invalid_ip"}

    def close(self):
        if self._reader is not None:
            self._reader.close()
            self._reader = None
            self._loaded = False


def get_geoip_service():
    service = current_app.extensions.get("geoip")
    if service is None:
        service = GeoIPService()
        current_app.extensions["geoip"] = service
    return service
