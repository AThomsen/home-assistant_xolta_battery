import voluptuous as vol

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

DOMAIN = "xolta_batt"
# CONF_REFRESH_TOKEN = "refresh_token"
CONF_SITE_ID = "site_id"
UPDATE_INTERVAL_SEC = 60

# Validation of the user's configuration
XOLTA_CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_SITE_ID): str,
    }
)
