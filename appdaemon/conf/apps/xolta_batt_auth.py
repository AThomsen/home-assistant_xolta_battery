from seleniumwire import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By 
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait 
from seleniumwire.utils import decode
import appdaemon.plugins.hass.hassapi as hass
import time
import datetime
import json

class XoltaBattAuthenticator(hass.Hass):

    def initialize(self):
        self.log("Starting Xolta battery authenticator app")
        self.listen_event(self.get_auth_cb, "XOLTA_BATT_AUTH_REQUEST")


    # Callback Function to Start the process 
    def get_auth_cb(self, event_id, event_args, kwargs):
        timeout = 10

        start_time = time.perf_counter()
        auth_response = { "corr_id": event_args["corr_id"] }

        try:
            self.log("Xolta: requesting site")
            chrome_options = Options()
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--disable-dev-shm-usage')
            browser = webdriver.Chrome('chromedriver', options=chrome_options)
                    
            try:
                self.log("Start Request")
                browser.get('https://app.xolta.com/')
                #time.sleep(timeout)

                self.log("Login form")

                email_field = WebDriverWait(browser, timeout).until(lambda d: d.find_element(By.ID, 'email'))
                email_field.clear()
                email_field.send_keys(event_args['username'])
                pswd_field = browser.find_element(By.ID, 'password')
                pswd_field.clear()
                pswd_field.send_keys(event_args['password'])
                
                # this doesn't always work, so wait an extra ½ second
                submitButton = WebDriverWait(browser, timeout).until(EC.element_to_be_clickable((By.ID, 'next')) )
                time.sleep(0.5)
                submitButton.click()

                # check if username/password is correct
                submitRequest = browser.wait_for_request('B2C_1_sisu/SelfAsserted', timeout)
                submitResponse = submitRequest.response
                body = decode(submitResponse.body, submitResponse.headers.get('Content-Encoding', 'identity'))
                body = body.decode('utf-8')
                data = json.loads(body)

                # copy login status and any messages to result
                auth_response.update(data)

                if data["status"] == '200':
                    # login successful. Wait for token...
                    tokenRequest = browser.wait_for_request('b2c_1_sisu/oauth2/v2.0/token', timeout)
                    tokenResponse = tokenRequest.response
                    body = decode(tokenResponse.body, tokenResponse.headers.get('Content-Encoding', 'identity'))
                    body = body.decode('utf-8')
                    data = json.loads(body)
                    
                    auth_response.update({
                        "access_token": data['access_token'],
                        "refresh_token": data['refresh_token']
                    })

                browser.quit()
                self.log("Browser closed")
                
            except Exception as e:
                browser.quit()
                raise
        except Exception as e:
            self.log("XoltaBattAuthenticator Error: " + str(e))
            auth_response.update({
                "status": '500',
                "message": str(e)
            })
    
        auth_response.update({
            "duration": time.perf_counter() - start_time
        })

        # Set the JSON back to HA
        self.fire_event("XOLTA_BATT_AUTH_RESPONSE", **auth_response)
        self.log("Return: " + str(auth_response))
