import requests
import json
import logging
from datetime import datetime, timedelta

from emphasys_integration_consts import *

logging.basicConfig(filename="emphasys.log",
                    format='%(asctime)s %(message)s',
                    filemode='w')

# Creating an object
logger = logging.getLogger()
 
# Setting the threshold of logger to DEBUG
logger.setLevel(logging.DEBUG)

def _make_rest_call(url=None, params=None, headers=None, data=None, method="get"):
    ''' 
    function to make rest call
    '''

    try:
        request_func = getattr(requests, method)
    except Exception as e:
        error_message = _get_error_message_from_exception(e)
        return False, error_message

    try:
        response = request_func(url, params=params, headers=headers, data=data)
    except Exception as e:
        error_message = _get_error_message_from_exception(e)
        return False, error_message

    return _process_response(response)

def _process_response(r):
    ''' 
    function to process response
    '''

    # Process a json response
    if 'json' in r.headers.get('Content-Type', ''):
        return _process_json_response(r)

    message = "Can't process response from server. Status Code: {0} Data from server: {1}".format(
            r.status_code, r.text.replace('{', '{{').replace('}', '}}'))

    return False, message

def _process_json_response(r):
    ''' 
    function to process json response
    '''

    # Try a json parse
    try:
        resp_json = r.json()
    except Exception as e:
        logger.debug('Cannot parse JSON')
        return False, "Unable to parse response as JSON"

    if (200 <= r.status_code < 205):
        return True, resp_json

    error_info = resp_json if type(resp_json) is str else resp_json.get('error', {})
    try:
        if error_info.get('code') and error_info.get('message') and type(resp_json):
            error_details = {
                'message': error_info.get('code'),
                'detail': error_info.get('message')
            }
            return False, "Error from server, Status Code: {0} data returned: {1}".format(r.status_code, error_details)
        else:
            return False, "Error from server, Status Code: {0} data returned: {1}".format(r.status_code, r.text.replace('{', '{{').replace('}', '}}'))
    except:
        return False, "Error from server, Status Code: {0} data returned: {1}".format(r.status_code, r.text.replace('{', '{{').replace('}', '}}'))

def _get_error_message_from_exception(e):
    """ 
    This function is used to get appropriate error message from the exception.
    """
    error_code = "Error code unavailable"
    error_msg = "Unknown error occured"
    try:
        if hasattr(e, 'args'):
            if len(e.args) > 1:
                error_code = e.args[0]
                error_msg = e.args[1]
            elif len(e.args) == 1:
                error_code = "Error code unavailable"
                error_msg = e.args[0]
    except Exception:
        logger.debug("Error occurred while retrieving exception information")

    return "Error Code: {0}. Error Message: {1}".format(error_code, error_msg)


def _login():
    ''' 
    function to get access_token from Bob.ai
    '''

    payload = json.dumps({
        "user_id": BOB_AI_USER_ID,
        "password": BOB_AI_PASSWORD
    })

    ret_val, response = _make_rest_call(url=BOB_AI_LOGIN_URL, data=payload, method="post")

    if type(response) == str:
        return False, response

    if response.get('access_token', None):
        return True, response['access_token']
    else:
        return False, "Failed to get access token from Bob.ai. Error {}".format(response)


def _check_inspection_from_bob_ai(start_date, end_date):
    ''' 
    function to check whether an inspection is available in the Bob.ai or not.
    '''
    params = {
        'sort': 'ScheduledDate-D',
        'ScheduledDate': '{},{}'.format(start_date, end_date),
        'Status': 'Pass,Fail,No_access',
        'is_agency_instance': 1
    }
    
    headers = {
        'Authorization': 'Bearer {}'.format(access_token)
    }

    ret_val, response = _make_rest_call(url=BOB_AI_INSPECTION_GET_URL, params=params, headers=headers)

    return ret_val, response

end_date = datetime.now()
start_date = end_date - timedelta(days=7)

logger.debug("end date {}".format(end_date))
logger.debug("start date {}".format(start_date))

global access_token
ret_val, access_token = _login()
if not ret_val:
    logger.debug("Failed to create access token for BOB. Error: {}".format(access_token))

ret_val, response = _check_inspection_from_bob_ai(start_date.strftime("%m/%d/%Y"), end_date.strftime("%m/%d/%Y"))

if not ret_val:
    logger.debug("Error while checking inspection on bob. Error {}".format(response))

headers = {
    'Ocp-Apim-Subscription-Key': EMPHASYS_SUBSCRIPTION_KEY,
    'x-ecs-client': EMPHASYS_ECS_CLIENT,
    'Cache-Control': 'no-cache'
}

ret_val, emphasys_overall_results = _make_rest_call(url="https://api.gw.emphasyspha.com/inspections/v11/Setups/OverallResults", headers=headers, method="get")

emphasys_results = {}
if not ret_val:
    logger.debug("Error while fetching inspections from emphasys. Error {}".format(emphasys_overall_results))
else:
    emphasys_results = {i['pk']:i['description'] for i in emphasys_overall_results}

logger.debug("results available in emphasys".format(emphasys_results))


ret_val, emphasys_inspectors_results = _make_rest_call(url="https://api.gw.emphasyspha.com/inspections/v11/Setups/Inspectors", headers=headers, method="get")

emphasys_inspectors = {}
if not ret_val:
    logger.debug("Error while fetching inspections from emphasys. Error {}".format(emphasys_inspectors_results))
else:
    emphasys_inspectors = {i['pk']:i['inspectorName'] for i in emphasys_inspectors_results}

logger.debug("inspectors available on emphasys".format(emphasys_inspectors))