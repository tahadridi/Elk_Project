# GeoIP database

Place `GeoLite2-Country.mmdb` in this directory.

Download it from MaxMind using a free account and license key:

```bash
export MAXMIND_LICENSE_KEY="your-key"
./scripts/download_geolite2.sh
```

The `.mmdb` file is git-ignored and must not be committed. Update it monthly.
