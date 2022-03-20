import voluptuous as vol

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

DOMAIN = "xolta_batt"
UPDATE_INTERVAL_SEC = 60

# Validation of the user's configuration
XOLTA_CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)
