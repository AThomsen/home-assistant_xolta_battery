import voluptuous as vol

DOMAIN = "xolta_batt"
CONF_REFRESH_TOKEN = "refresh_token"
CONF_SITE_ID = "site_id"
UPDATE_INTERVAL_SEC = 60

# Validation of the user's configuration
XOLTA_CONFIG_SCHEMA = vol.Schema(
    {vol.Required(CONF_REFRESH_TOKEN): str, vol.Required(CONF_SITE_ID): str}
)
