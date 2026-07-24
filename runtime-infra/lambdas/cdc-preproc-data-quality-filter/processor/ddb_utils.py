DDB_VALUE_TYPES = (
    "S",
    "N",
    "BOOL",
    "NULL",
    "B",
    "SS",
    "NS",
    "BS",
    "L",
    "M",
)


def get_dynamodb(payload):
    dynamodb = payload.get("dynamodb", {})

    if not isinstance(dynamodb, dict):
        return {}

    return dynamodb


def get_image(payload, priority=None):
    priority = priority or [
        "NewImage",
        "OldImage",
        "Keys",
    ]

    dynamodb = get_dynamodb(payload)

    for image_name in priority:
        image = dynamodb.get(image_name)

        if isinstance(image, dict) and image:
            return image, image_name

    return {}, "Missing"


def get_value(image, field_name):
    if not isinstance(image, dict):
        return None

    attribute = image.get(field_name)

    if not isinstance(attribute, dict):
        return None

    if attribute.get("NULL") is True:
        return None

    for value_type in DDB_VALUE_TYPES:
        if value_type in attribute:
            return attribute[value_type]

    return None


def has_value(image, field_name):
    value = get_value(image, field_name)

    if value is None:
        return False

    if isinstance(value, str):
        return bool(value.strip())

    return True


def remove_fields(payload, field_names, image_names=None):
    image_names = image_names or [
        "NewImage",
        "OldImage",
    ]

    dynamodb = get_dynamodb(payload)

    for image_name in image_names:
        image = dynamodb.get(image_name)

        if not isinstance(image, dict):
            continue

        for field_name in field_names:
            image.pop(field_name, None)

    return payload