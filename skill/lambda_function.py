#
# Copyright 2019 Amazon.com, Inc. or its affiliates.  All Rights Reserved.
# These materials are licensed under the Amazon Software License in connection with the Alexa Gadgets Program.
# The Agreement is available at https://aws.amazon.com/asl/.
# See the Agreement for the specific terms and conditions of the Agreement.
# Capitalized terms not defined in this file have the meanings given to them in the Agreement.
# (C) Copyright 2020 Darwin Tech, LLC, http://www.darwintechnologiesllc.com
#
import logging.handlers
import uuid

from ask_sdk_core.skill_builder import CustomSkillBuilder
from ask_sdk_core.api_client import DefaultApiClient
from ask_sdk_core.utils import is_request_type, is_intent_name
from ask_sdk_core.handler_input import HandlerInput
from ask_sdk_core.serialize import DefaultSerializer

from ask_sdk_model.interfaces.custom_interface_controller import (
    StartEventHandlerDirective, EventFilter, Expiration, FilterMatchAction,
    StopEventHandlerDirective,
    SendDirectiveDirective,
    Header,
    Endpoint
)

logger = logging.getLogger()
logger.setLevel(logging.INFO)
serializer = DefaultSerializer()
skill_builder = CustomSkillBuilder(api_client=DefaultApiClient())


@skill_builder.request_handler(can_handle_func=is_request_type("LaunchRequest"))
def launch_request_handler(handler_input: HandlerInput):
    logger.info("== Launch Intent ==")

    response_builder = handler_input.response_builder

    system = handler_input.request_envelope.context.system

    # Get connected gadget endpoint ID.
    endpoints = get_connected_endpoints(handler_input)
    logger.debug("Checking endpoint..")
    if not endpoints:
        logger.debug("No connected gadget endpoints available.")
        return (response_builder
                .speak("No gadgets found. Please try again after connecting your gadget.")
                .set_should_end_session(True)
                .response)

    endpoint_id = endpoints[0].endpoint_id

    # Store endpoint ID for using it to send custom directives later.
    logger.debug("Received endpoints. Storing Endpoint Id: %s", endpoint_id)
    session_attr = handler_input.attributes_manager.session_attributes
    session_attr['endpointId'] = endpoint_id

    # Create a token to be assigned to the EventHandler and store it
    # in session attributes for stopping the EventHandler later.
    token = str(uuid.uuid4())
    session_attr['token'] = token

    # Send the data request directive
    return (response_builder
            .add_directive(build_get_data_query(endpoint_id))
            .add_directive(build_start_event_handler_directive(token, 10000,
                                                               'Custom.ThunderGadget', 'GetDataReport',
                                                               FilterMatchAction.SEND_AND_TERMINATE,
                                                               {'data': "Sorry I couldn't read the thunder board sensor. Good bye!"}))
            .set_should_end_session(False)
            .response)

@skill_builder.request_handler(can_handle_func=is_request_type("CustomInterfaceController.EventsReceived"))
def custom_interface_event_handler(handler_input: HandlerInput):
    logger.info("== Received Custom Event ==")

    request = handler_input.request_envelope.request
    session_attr = handler_input.attributes_manager.session_attributes
    response_builder = handler_input.response_builder

    # Validate event handler token
    if session_attr['token'] != request.token:
        logger.info("EventHandler token doesn't match. Ignoring this event.")
        return (response_builder
                .speak("EventHandler token doesn't match. Ignoring this event.")
                .response)

    custom_event = request.events[0]
    payload = custom_event.payload
    namespace = custom_event.header.namespace
    name = custom_event.header.name

    if namespace == 'Custom.ThunderGadget' and name == 'GetDataReport':
        return (response_builder
                .speak('The current temperature is ' + str(payload['temperature']) + ' and the relative humidity is ' + str(payload['RH']) + ' percent')
                .set_should_end_session(True)
                .response)

    return response_builder.response


@skill_builder.request_handler(can_handle_func=is_request_type("CustomInterfaceController.Expired"))
def custom_interface_expiration_handler(handler_input):
    logger.info("== Custom Event Expiration Input ==")

    request = handler_input.request_envelope.request
    response_builder = handler_input.response_builder
    session_attr = handler_input.attributes_manager.session_attributes
    endpoint_id = session_attr['endpointId']

    # When the EventHandler expires end skill session.
    return (response_builder
            .speak(request.expiration_payload['data'])
            .set_should_end_session(True)
            .response)

@skill_builder.request_handler(can_handle_func=is_request_type("SessionEndedRequest"))
def session_ended_request_handler(handler_input):
    logger.info("Session ended with reason: " +
                handler_input.request_envelope.request.reason.to_str())
    return handler_input.response_builder.response


@skill_builder.exception_handler(can_handle_func=lambda i, e: True)
def error_handler(handler_input, exception):
    logger.info("==Error==")
    logger.error(exception, exc_info=True)
    return (handler_input.response_builder
            .speak("I'm sorry, something went wrong!").response)


@skill_builder.global_request_interceptor()
def log_request(handler_input):
    # Log the request for debugging purposes.
    logger.info("==Request==\r" +
                str(serializer.serialize(handler_input.request_envelope)))


@skill_builder.global_response_interceptor()
def log_response(handler_input, response):
    # Log the response for debugging purposes.
    logger.info("==Response==\r" + str(serializer.serialize(response)))
    logger.info("==Session Attributes==\r" +
                str(serializer.serialize(handler_input.attributes_manager.session_attributes)))


def get_connected_endpoints(handler_input: HandlerInput):
    return handler_input.service_client_factory.get_endpoint_enumeration_service().get_endpoints().endpoints


def build_get_data_query(endpoint_id):
    return SendDirectiveDirective(
        header=Header(namespace='Custom.ThunderGadget', name='GetData'),
        endpoint=Endpoint(endpoint_id=endpoint_id),
        payload={
            'get_state': 'true'
        }
    )

def build_start_event_handler_directive(token, duration_ms, namespace,
                                        name, filter_match_action, expiration_payload):
    return StartEventHandlerDirective(
        token=token,
        event_filter=EventFilter(
            filter_expression={
                'and': [
                    {'==': [{'var': 'header.namespace'}, namespace]},
                    {'==': [{'var': 'header.name'}, name]}
                ]
            },
            filter_match_action=filter_match_action
        ),
        expiration=Expiration(
            duration_in_milliseconds=duration_ms,
            expiration_payload=expiration_payload))


def build_stop_event_handler_directive(token):
    return StopEventHandlerDirective(token=token)


lambda_handler = skill_builder.lambda_handler()



