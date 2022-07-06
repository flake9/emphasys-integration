from email import header
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
    
    # params = {
    #     'SearchFullAddress': '04 12ND STREET BBDBB PA 11311',
    #     'ScheduledDate': '05/08/2021,08/10/2022',
    #     'is_agency_instance': 1
    # }

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
    exit()

ret_val, bob_inspections_response = _check_inspection_from_bob_ai(start_date.strftime("%m/%d/%Y"), end_date.strftime("%m/%d/%Y"))

if not ret_val:
    logger.debug("Error while checking inspection on bob. Error {}".format(bob_inspections_response))
    exit()

headers = {
    'Ocp-Apim-Subscription-Key': EMPHASYS_SUBSCRIPTION_KEY,
    'x-ecs-client': EMPHASYS_ECS_CLIENT,
    'Cache-Control': 'no-cache'
}

ret_val, emphasys_inspectors_results = _make_rest_call(url="https://api.gw.emphasyspha.com/inspections/v11/Setups/Inspectors", headers=headers, method="get")

emphasys_inspectors = {}
if not ret_val:
    logger.debug("Error while fetching inspections from emphasys. Error {}".format(emphasys_inspectors_results))
else:
    emphasys_inspectors = {i['inspectorName']:i['pk'] for i in emphasys_inspectors_results}

logger.debug("inspectors available on emphasys".format(emphasys_inspectors))


inspections_results_mapping = {
    "Test":
    {
        "Pass": 100001,
        "Fail": 100002,
        "No access": 100005,
        "Inconclusive": 100004,
        "Fail - Self Certify": 100010,
        "Fail - Emergency": 100003,
        "Vacant": 100008,
        "Canceled ": 100007
    },
    "HAKC":
    {
        "Pass": 100001,
        "Fail": 100002,
        "No access": 100002,
        "Inconclusive": 100003,
        "Fail - Self Certify": 100002,
        "Fail - Emergency": 100002,
        "Vacant": 100015,
        "Canceled ": 100011
    }
}

for inspection in bob_inspections_response.get('data', []):
    inspection_agency_id = inspection.get('agency_instance_id')
    inspection_inspector = inspection.get('WorkerName')
    app_from = inspection.get('AppointmentFrom')
    inspection_date = inspection.get('ScheduledDate')
    inspection_result = inspection.get('Result')
    
    # inspection_agency_id = 119090
    # inspection_inspector = "Roberta Camp"
    # app_from = "09:00"
    # inspection_result = "Fail"

    logger.debug("inspector {}".format(inspection_inspector))
    logger.debug("date {}".format(inspection_date))
    logger.debug("app_from {}".format(app_from))
    logger.debug("result {}".format(inspection_result))

    if inspection_agency_id:
        params = {
            "InspectionPK": inspection_agency_id
        }

        ret_val, emphasys_instance_details = _make_rest_call(url="https://api.gw.emphasyspha.com/inspections/v11//Inspections/GetInspection/", params=params, headers=headers, method="get")

        if not ret_val:
            logger.debug("Error while fetching inspections instance. Error {}".format(emphasys_instance_details))
            continue

        instance_list = emphasys_instance_details.get('instanceList', [])
        if instance_list:
            instance_list = instance_list[0]

        if inspection_result:
            instance_list['fkOverallResult'] = inspections_results_mapping[CUSTOMER][inspection_result]
            logger.debug("overall result {}".format(instance_list['fkOverallResult']))

        if inspection_inspector and emphasys_inspectors.get(inspection_inspector):
            instance_list['fkInspector'] = emphasys_inspectors[inspection_inspector]

        if inspection_date and app_from:
            inspection_date_new = "{} {}".format(inspection_date, app_from)
            instance_list['inspectionDate'] = datetime.strptime(inspection_date_new, '%m/%d/%Y %H:%M').strftime('%Y-%m-%dT%H:%M:%SZ')
        elif inspection_date and not app_from:
            instance_list['inspectionDate'] = datetime.strptime(inspection_date, '%m/%d/%Y').strftime('%Y-%m-%dT%H:%M:%SZ')


        headers['Content-Type'] = 'application/json'

        if inspection_result:

            payload = json.dumps({
                "Instance": instance_list
            })

            ret_val, update_instance_details = _make_rest_call(url="https://api.gw.emphasyspha.com/inspections/v11/Inspections/UpdateInstance", headers=headers, data=payload, method="put")

            if not ret_val:
                logger.debug("Error while updating instance. Error {}".format(update_instance_details))
                continue

            logger.debug("API call to update inspection on emphasys success")
        # Will need if need to inspection back to emphasys without results.
        # else:

        #     schedule_payload = {}

        #     schedule_payload['InspectionInstancePK'] = inspection_agency_id

        #     if inspection_inspector and emphasys_inspectors.get(inspection_inspector):
        #         schedule_payload['InspectorPK'] = emphasys_inspectors[inspection_inspector]
        
        #     if inspection_date and app_from:
        #         inspection_date_new = "{} {}".format(inspection_date, app_from)
        #         schedule_payload['DateTime'] = datetime.strptime(inspection_date_new, '%m/%d/%Y %H:%M').strftime('%Y-%m-%dT%H:%M:%SZ')
        #     elif inspection_date:
        #         schedule_payload['DateTime'] = datetime.strptime(inspection_date, '%m/%d/%Y').strftime('%Y-%m-%dT%H:%M:%SZ')
            
        #     schedule_payload_final = json.dumps(schedule_payload)

        #     ret_val, schedule_instance_response = _make_rest_call(url="https://api.gw.emphasyspha.com/inspections/v11/Inspections/ScheduleInstance", headers=headers, data=schedule_payload_final, method="post")

        #     if not ret_val:
        #         logger.debug("Error while scheduling instance. Error {}".format(schedule_instance_response))
        #         continue

        #     logger.debug("schedule call success")
    else:
        logger.debug("Inspection agency ID not found")