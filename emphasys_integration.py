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


def _check_inspection_from_bob_ai(scheduled_date, full_address):
    ''' 
    function to check whether an inspection is available in the Bob.ai or not.
    '''

    params = {
        'ScheduledDate': scheduled_date,
        'SearchFullAddress': full_address,
        'sort': 'ScheduledDate-D'
    }
    
    headers = {
        'Authorization': 'Bearer {}'.format(access_token)
    }

    ret_val, response = _make_rest_call(url=BOB_AI_INSPECTION_GET_URL, params=params, headers=headers)

    return ret_val, response

def _update_emphasys_inspection_id_bob(BOB_inspection_id, instance_id):
    ''' 
    function to check whether an inspection is available in the Bob.ai or not using instance id.
    '''

    params = {
        'inspection_id': BOB_inspection_id
    }
    
    headers = {
        'Authorization': 'Bearer {}'.format(access_token)
    }

    payload = json.dumps({
        "agency_instance_id": instance_id
    })

    ret_val, response = _make_rest_call(url=BOB_AI_UPDATE_INSTANCE_ID, params=params, headers=headers, data=payload, method="post")

    return ret_val, response

def _propose_available_date_time(scheduled_date, full_address, inspection_type):
    ''' 
    function to propose date and time for an inspection
    '''

    if inspection_type:
        payload = json.dumps({
            'UnitAddress': full_address,
            'InspectionType': inspection_type,
            'Medium': "Onsite",
            'AvailableInspectionDate': [scheduled_date, scheduled_date]
        })
    else:
            payload = json.dumps({
            'UnitAddress': full_address,
            'Medium': "Onsite",
            'AvailableInspectionDate': [scheduled_date, scheduled_date]
        })

    headers = {
        'Authorization': 'Bearer {}'.format(access_token)
    }

    ret_val, response = _make_rest_call(url=BOB_AI_PROPOSE_AVAILABLE_SLOT, data=payload, headers=headers, method="post")

    return ret_val, response

def _create_inspection(scheduled_date, full_address, worker_id, sequence, list_schedules, inspection_type):
    ''' 
    function to create an inspection
    '''

    if inspection_type:
        payload = json.dumps({
            'UnitAddress': full_address,
            'ScheduledDate': scheduled_date,
            'WorkerID': worker_id,
            'Sequence': sequence,
            'ListSchedules': list_schedules
        })
    else:
        payload = json.dumps({
        'UnitAddress': full_address,
        'InspectionType': inspection_type,
        'ScheduledDate': scheduled_date,
        'WorkerID': worker_id,
        'Sequence': sequence,
        'ListSchedules': list_schedules
    })
    
    headers = {
        'Authorization': 'Bearer {}'.format(access_token)
    }

    ret_val, response = _make_rest_call(url=BOB_AI_CREATE_INSPECTION, data=payload, headers=headers, method="post")

    return ret_val, response

def _create_unit(address, city, state, zipcode):
    ''' 
    function to create an unit
    '''

    payload = json.dumps({
        'Address1': address,
        'City': city,
        'State': state,
        'Zipcode': zipcode
    })
    
    headers = {
        'Authorization': 'Bearer {}'.format(access_token)
    }

    ret_val, response = _make_rest_call(url=BOB_AI_CREATE_UNIT, data=payload, headers=headers, method="post")

    logger.debug("response create unit {}".format(response))

    return ret_val, response

end_date = datetime.now()
start_date = end_date - timedelta(days=7)

logger.debug("end date {}".format(end_date))
logger.debug("start date {}".format(start_date))

page_number = 1
while True:

    global access_token
    ret_val, access_token = _login()
    if not ret_val:
        logger.debug("Failed to create access token for BOB. Error: {}".format(access_token))
        break
    
    inspection_type_mapping = {
        100001:'Annual',
        100002:'Initial',
        100003:'QC',
        100004:'Complaint'
    }
    
    logger.debug("page number {}".format(page_number))

    params = {
        'StartDate': start_date.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        'EndDate': end_date.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        'Page': page_number,
        'PageSize': EMPHASYS_DEFAULT_PAGE_SIZE
    }

    headers = {
    'Ocp-Apim-Subscription-Key': EMPHASYS_SUBSCRIPTION_KEY,
    'x-ecs-client': EMPHASYS_ECS_CLIENT,
    'Cache-Control': 'no-cache'
    }

    ret_val, emphasys_response = _make_rest_call(url=EMPHASYS_INSPECTION_API_URL, params=params, headers=headers, method="get")

    if not ret_val:
        logger.debug("Error while fetching inspections from emphasys. Error {}".format(emphasys_response))
        break

    if not emphasys_response.get('inspections'):
        logger.debug("No inspections found on emphasys in last 7 days")
        break

    for unit in emphasys_response.get('inspections'):

        try:
            if unit.get('unitSuite'):
                full_address = "{} {} {} {} {}".format(unit.get('unitPrimaryStreet'),unit.get('unitSuite'),
                unit.get('unitCity'), unit.get('unitState'), unit.get('unitZip')).upper()
            else:
                full_address = "{} {} {} {}".format(unit.get('unitPrimaryStreet'),unit.get('unitCity'),
                unit.get('unitState'), unit.get('unitZip')).upper()
        except Exception as e:
            logger.debug("Error occured while creating address from emphasys inspections for inspection {}. Error {}".format(unit['inspectionID'], _get_error_message_from_exception(e)))

        try:
            scheduled_date = unit.get("instanceList")[0]['scheduledDate']
        except Exception as e:
            logger.debug("Error occured while getting the scheduled date of an inspection {}. Error {}".format(unit['inspectionID'], _get_error_message_from_exception(e)))

        if scheduled_date:
            scheduled_date = datetime.strptime(scheduled_date, '%Y-%m-%dT%H:%M:%SZ').strftime('%m/%d/%Y')

        if unit.get('fkInspectionType'):
            inspection_type = inspection_type_mapping[unit['fkInspectionType']]
        else:
            inspection_type = None
        
        if unit.get('inspectionID'):
            emphasys_inspection_id = unit['inspectionID']
        else:
            emphasys_inspection_id = None

        # check whether the inspection is available on BOB or not
        if scheduled_date and full_address:
            ret_val, response = _check_inspection_from_bob_ai("{},{}".format(scheduled_date,scheduled_date), full_address)

            if not ret_val:
                logger.debug("Error while checking inspection on bob. Error {}".format(response))
                continue
            
            try:
                total_count = response.get("total_count")
            except Exception as e:
                logger.debug("Error while fetching total count {}".format(_get_error_message_from_exception(e)))

            if total_count:
                logger.debug("inspection is already there")
                bob_inspection_list = response.get('data', [])
                if emphasys_inspection_id:
                    if bob_inspection_list:
                        bob_inspection_instance_id = bob_inspection_list[0].get('agency_instance_id')
                        if bob_inspection_instance_id == emphasys_inspection_id:
                            logger.debug("Bob instance id and emphasys instance id matched for emphasys instance id: {}".format(emphasys_inspection_id))
                            continue
                        else:
                            ret_val, response = _update_emphasys_inspection_id_bob(bob_inspection_list[0].get('ID'), emphasys_inspection_id)

                            if not ret_val:
                                logger.debug("Error while updating instance id to bob. continuing with the next inspection. Error {}".format(propose_slot_response))
                                continue
            else:
                # If inspection is not available propose date and time to create an inspection
                ret_val, propose_slot_response = _propose_available_date_time(scheduled_date, full_address, inspection_type)

                if not ret_val:
                    logger.debug("Error while proposing available date time in bob. continuing with the next inspection. Error {}".format(propose_slot_response))
                    continue

                # If unit is not available in the BOB, create the unit in the BOB
                if "Unit information not found" in propose_slot_response.get('message'):
                    if unit.get('unitSuite'):
                        ret_val, response = _create_unit('{} {}'.format(unit.get('unitPrimaryStreet'), unit.get('unitSuite')), unit.get('unitCity'), unit.get('unitState'), unit.get('unitZip'))
                    else:
                        ret_val, response = _create_unit(unit.get('unitPrimaryStreet'), unit.get('unitCity'), unit.get('unitState'), unit.get('unitZip'))

                        if not ret_val:
                            logger.debug("Error while creating an unit to BOB. Error {}".format(response))
                            continue

                        # If inspection is not available propose date and time to create an inspection
                        ret_val, propose_slot_response = _propose_available_date_time(scheduled_date, full_address, inspection_type)

                        if not ret_val:
                            logger.debug("Error while proposing available date time in bob. continuing with the next inspection. Error {}".format(propose_slot_response))
                            continue

                # If slots are not available
                if not propose_slot_response.get('slots'):
                    logger.debug("No available slots for given address on scheduled date. continuing with the next inspection")
                    continue

                worker_id = propose_slot_response.get('slots')[0].get("WorkerID")
                sequence = propose_slot_response.get('slots')[0].get("Sequence")
                list_schedules = propose_slot_response.get('slots')[0].get("ListSchedules")
                create_inspection_scheduled_date = propose_slot_response.get('slots')[0].get("ScheduledDate")


                # Finally create an inspection
                if unit.get('unitSuite'):
                    create_inspection_address = '{} {} {} {} {}'.format(unit.get('unitPrimaryStreet').upper(), unit.get('unitSuite').upper(), unit.get('unitCity').upper(), unit.get('unitState').upper(), unit.get('unitZip'))
                else:
                    create_inspection_address = '{} {} {} {}'.format(unit.get('unitPrimaryStreet').upper(), unit.get('unitCity').upper(), unit.get('unitState').upper(), unit.get('unitZip'))

                ret_val, response = _create_inspection(create_inspection_scheduled_date, create_inspection_address, worker_id, sequence, list_schedules, inspection_type)

                if not ret_val:
                    logger.debug("Error while creating an inspection in bob. continuing with the next inspection. Error {}".format(response))
                    continue
                
                if response.get('message') == "success":
                    logger.debug("successfully created inspection")
                else:
                    logger.debug("Error occured in creating an inspection {}".format(response))

    try:
        # When page count matches break the loop
        if page_number == emphasys_response.get("pageCount"):
            logger.debug("page count {}".format(emphasys_response.get("pageCount")))
            logger.debug("breaking.....")
            break
    except Exception as e:
        logger.debug("Exception occured while fetching the page count from the response. Breaking....")
        break

    page_number = page_number + 1
