from copy import deepcopy

import pytest

from processor.ddb_utils import (
    get_dynamodb,
    get_image,
    get_value,
    has_value,
    remove_fields,
)


# Verify that the "dynamodb" section is extracted, and that an empty dict is
# returned when it's missing or not a dict.
@pytest.mark.parametrize(
    "payload,expected",
    [
        pytest.param({}, {}, id="dynamodb-key-missing"),
        pytest.param({"dynamodb": "not-a-dict"}, {}, id="dynamodb-not-a-dict"),
        pytest.param(
            {"dynamodb": {"NewImage": {"pk": {"S": "value"}}}},
            {"NewImage": {"pk": {"S": "value"}}},
            id="returns-dynamodb-section",
        ),
    ],
)
def test_get_dynamodb(payload, expected):
    assert get_dynamodb(payload) == expected


# Verify that the correct image (NewImage/OldImage/Keys) is picked, using the
# default priority order or a custom one.
@pytest.mark.parametrize(
    "payload,priority,expected_image,expected_source",
    [
        pytest.param(
            {
                "dynamodb": {
                    "NewImage": {"pk": {"S": "new"}},
                    "OldImage": {"pk": {"S": "old"}},
                    "Keys": {"pk": {"S": "keys"}},
                }
            },
            None,
            {"pk": {"S": "new"}},
            "NewImage",
            id="prefers-new-image-over-old-image-and-keys",
        ),
        pytest.param(
            {
                "dynamodb": {
                    "OldImage": {"pk": {"S": "old"}},
                    "Keys": {"pk": {"S": "keys"}},
                }
            },
            None,
            {"pk": {"S": "old"}},
            "OldImage",
            id="falls-back-to-old-image-when-new-image-missing",
        ),
        pytest.param(
            {
                "dynamodb": {
                    "NewImage": {},
                    "OldImage": {"pk": {"S": "old"}},
                }
            },
            None,
            {"pk": {"S": "old"}},
            "OldImage",
            id="skips-empty-dict-images",
        ),
        pytest.param(
            {"dynamodb": {"Keys": {"pk": {"S": "keys"}}}},
            None,
            {"pk": {"S": "keys"}},
            "Keys",
            id="falls-back-to-keys-when-no-images-present",
        ),
        pytest.param(
            {"dynamodb": {}},
            None,
            {},
            "Missing",
            id="returns-missing-when-nothing-available",
        ),
        pytest.param(
            {
                "dynamodb": {
                    "NewImage": {"pk": {"S": "new"}},
                    "OldImage": {"pk": {"S": "old"}},
                }
            },
            ["OldImage", "NewImage"],
            {"pk": {"S": "old"}},
            "OldImage",
            id="honors-custom-priority",
        ),
    ],
)
def test_get_image(payload, priority, expected_image, expected_source):
    # priority is None for the cases exercising the function's default priority order.
    if priority is None:
        image, source = get_image(payload)
    else:
        image, source = get_image(payload, priority=priority)

    assert image == expected_image
    assert source == expected_source


# Verify that a typed DynamoDB attribute is unwrapped correctly, including the
# NULL, missing-field, and invalid-shape edge cases.
@pytest.mark.parametrize(
    "image,expected",
    [
        pytest.param({"field": {"S": "hello"}}, "hello", id="string"),
        pytest.param({"field": {"N": "42"}}, "42", id="number"),
        pytest.param({"field": {"BOOL": True}}, True, id="bool-true"),
        pytest.param({"field": {"BOOL": False}}, False, id="bool-false"),
        pytest.param({"field": {"B": "base64blob"}}, "base64blob", id="binary"),
        pytest.param({"field": {"SS": ["a", "b"]}}, ["a", "b"], id="string-set"),
        pytest.param({"field": {"NS": ["1", "2"]}}, ["1", "2"], id="number-set"),
        pytest.param({"field": {"BS": ["a"]}}, ["a"], id="binary-set"),
        pytest.param({"field": {"L": [{"S": "a"}]}}, [{"S": "a"}], id="list"),
        pytest.param({"field": {"M": {"nested": {"S": "x"}}}}, {"nested": {"S": "x"}}, id="map"),
        pytest.param({"field": {"NULL": True}}, None, id="null"),
        pytest.param({"field": {"UNKNOWN": "x"}}, None, id="unknown-value-type"),
        pytest.param({"field": "not-a-dict"}, None, id="attribute-not-dict"),
        pytest.param({}, None, id="field-missing"),
        pytest.param("not-a-dict", None, id="image-not-dict"),
    ],
)
def test_get_value(image, expected):
    assert get_value(image, "field") == expected


# Verify that a field is considered to have a value unless it's None or a
# blank/whitespace-only string.
@pytest.mark.parametrize(
    "image,expected",
    [
        pytest.param({"field": {"S": "hello"}}, True, id="non-empty-string"),
        pytest.param({"field": {"S": "   "}}, False, id="blank-or-empty-string"),
        pytest.param({"field": {"BOOL": False}}, True, id="falsy-non-string-value"),
        pytest.param({}, False, id="value-missing"),
    ],
)
def test_has_value(image, expected):
    assert has_value(image, "field") is expected


PK = {"S": "a"}
HASH = {"S": "hash"}


# Verify that fields are removed from the default or an explicit list of images,
# and that the no-op cases don't raise. expected_dynamodb is the "dynamodb" section
# as it should look after the call.
@pytest.mark.parametrize(
    "dynamodb,field_names,image_names,expected_dynamodb",
    [
        pytest.param(
            {
                "NewImage": {"pk": PK, "addresshash": HASH},
                "OldImage": {"pk": PK, "addresshash": HASH},
            },
            ["addresshash"],
            None,
            {"NewImage": {"pk": PK}, "OldImage": {"pk": PK}},
            id="removes-from-both-default-images",
        ),
        pytest.param(
            {
                "NewImage": {"pk": PK, "addresshash": HASH},
                "OldImage": {"pk": PK, "addresshash": HASH},
            },
            ["addresshash"],
            ["NewImage"],
            {
                "NewImage": {"pk": PK},
                "OldImage": {"pk": PK, "addresshash": HASH},
            },
            id="only-targets-specified-images",
        ),
        pytest.param(
            {"NewImage": "not-a-dict"},
            ["addresshash"],
            None,
            {"NewImage": "not-a-dict"},
            id="ignores-non-dict-images",
        ),
        pytest.param(
            {"NewImage": {"pk": PK}},
            ["missing_field"],
            None,
            {"NewImage": {"pk": PK}},
            id="no-op-when-field-absent",
        ),
        pytest.param(
            {},
            ["addresshash"],
            None,
            {},
            id="no-op-when-no-images-present",
        ),
    ],
)
def test_remove_fields(dynamodb, field_names, image_names, expected_dynamodb):
    # Deep-copy because remove_fields mutates in place, and parametrize builds these
    # params once at collection time; without the copy, test cases would leak into
    # each other.
    payload = {"dynamodb": deepcopy(dynamodb)}

    # image_names is None for the cases exercising the function's default image list.
    if image_names is None:
        result = remove_fields(payload, field_names=field_names)
    else:
        result = remove_fields(
            payload, field_names=field_names, image_names=image_names
        )

    # remove_fields mutates in place and returns the same object it received.
    assert result is payload
    assert result["dynamodb"] == expected_dynamodb
