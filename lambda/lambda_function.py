import os
import json
from supabase import create_client, Client
from datetime import datetime, timedelta

# Initialize Supabase client
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)


def get_named_parameter(event, name):
    """
    Get a parameter from the lambda event
    """
    return next(item for item in event["parameters"] if item["name"] == name)["value"]


def create_event(group_id, period, description):
    """
    Create a new event

    Args:
        group_id (string): The ID of the group creating the event
        period (string): The period for the event (e.g., "2023-07-01 to 2023-07-07")
        description (string): Description of the event
    """
    try:
        data, count = (
            supabase.table("events")
            .insert(
                {
                    "groupID": group_id,
                    "period": period,
                    "description": description,
                    "confirmedTime": None,  # This will be updated later when RSVP is processed
                }
            )
            .execute()
        )

        return {"eventID": data[1][0]["eventID"]}
    except Exception as e:
        return {"error": str(e)}


def parse_datetime(dt_string):
    return datetime.strptime(dt_string.lstrip("start:"), "%y-%m-%d:%H-%M").isoformat()


def rsvp(user_id, event_id, availiable_time):
    """
    Indicate a user's availability for an event

    Args:
        user_id (string): The ID of the user
        event_id (string): The ID of the event
        availiable_time (string): The user's available time range. The format is pairs of start:YYYY-MM-DD:HH-MM and end:YYYY-MM-DD:HH-MM indicating the start and end of the user's available time ranges. If the user has multiple available time ranges, submit multiple pairs
    """
    try:
        for i in range(len(availiable_time.split()), 2):
            try:
                start_time = parse_datetime(availiable_time[i])
                end_time = parse_datetime(availiable_time[i + 1])
            except Exception as e:
                return {"error": "Malformed available time data!" + str(e)}

        data, count = (
            supabase.table("availabilities")
            .insert(
                {
                    "userID": user_id,
                    "eventID": event_id,
                    "startTime": start_time,
                    "endTime": end_time,
                }
            )
            .execute()
        )

        return {"message": "Availability recorded successfully"}
    except Exception as e:
        return {"error: " + str(e)}


def select_time(event_id):
    """
    Find the time with the greatest overlapping time ranges for an event

    Args:
        event_id (string): The ID of the event
    """
    try:
        # Fetch all availabilities for the event
        data, count = (
            supabase.table("availabilities")
            .select("*")
            .eq("eventID", event_id)
            .execute()
        )
        availabilities = data[1]

        if not availabilities:
            return None

        # Convert string times to datetime objects
        for avail in availabilities:
            avail["startTime"] = datetime.fromisoformat(avail["startTime"])
            avail["endTime"] = datetime.fromisoformat(avail["endTime"])

        # Find the overall start and end times
        start_time = min(avail["startTime"] for avail in availabilities)
        end_time = max(avail["endTime"] for avail in availabilities)

        # Create a list of all possible 30-minute slots
        slots = []
        current_time = start_time
        while current_time < end_time:
            slots.append((current_time, current_time + timedelta(minutes=30)))
            current_time += timedelta(minutes=30)

        # Count the number of people available for each slot
        best_slot = max(
            slots,
            key=lambda slot: sum(
                1
                for avail in availabilities
                if avail["startTime"] <= slot[0] and avail["endTime"] >= slot[1]
            ),
        )

        return best_slot[0].isoformat()

    except Exception as e:
        print(f"Error finding best time: {str(e)}")
        return None


def update_event_time(event_id, confirmed_time):
    """
    Update the confirmed time for an event

    Args:
        event_id (string): The ID of the event
        confirmed_time (string): The confirmed time for the event
    """
    try:
        data, count = (
            supabase.table("events")
            .update({"confirmedTime": confirmed_time})
            .eq("eventID", event_id)
            .execute()
        )

        return {"message": "Event time updated successfully"}
    except Exception as e:
        return {"error": str(e)}


def find_best_time(event_id):
    """
    Process RSVP for an event

    Args:
        event_id (string): The ID of the event
    """
    best_time = select_time(event_id)
    if best_time:
        return update_event_time(event_id, best_time)
    else:
        return {"error": "Unable to find a suitable time"}


def lambda_handler(event, context):
    # Get the action group used during the invocation of the lambda function
    action_group = event.get("actionGroup", "")

    # Name of the function that should be invoked
    function = event.get("function", "")

    if function == "create_event":
        group_id = get_named_parameter(event, "group_id")
        period = get_named_parameter(event, "period")
        description = get_named_parameter(event, "description")

        if group_id and period and description:
            response = create_event(group_id, period, description)
            response_body = {"TEXT": {"body": json.dumps(response)}}
        else:
            response_body = {"TEXT": {"body": "Missing required parameters"}}

    elif function == "rsvp":
        user_id = get_named_parameter(event, "user_id")
        event_id = get_named_parameter(event, "event_id")
        availiable_time = get_named_parameter(event, "availiable_time")

        if user_id and event_id and start_time and end_time:
            response = rsvp(user_id, event_id, availiable_time)
            response_body = {"TEXT": {"body": json.dumps(response)}}
        else:
            response_body = {"TEXT": {"body": "Missing required parameters"}}

    elif function == "find_best_time`":
        event_id = get_named_parameter(event, "event_id")

        if event_id:
            response = find_best_time(event_id)
            response_body = {"TEXT": {"body": json.dumps(response)}}
        else:
            response_body = {"TEXT": {"body": "Missing event_id parameter"}}

    else:
        response_body = {"TEXT": {"body": "Invalid function"}}

    action_response = {
        "actionGroup": action_group,
        "function": function,
        "functionResponse": {"responseBody": response_body},
    }

    function_response = {
        "response": action_response,
        "messageVersion": event["messageVersion"],
    }
    print("Response: {}".format(function_response))

    return function_response
