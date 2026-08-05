from tests.utils.builders import (
    boolean,
    dq_case,
    dq_error,
    field,
    number,
)
from tests.utils.classes import Category, DQCaseSpec, DQTestCase, PayloadInput, Table

# all registered payloads, across all tables
PAYLOADS = []


# ---------------------------------------------------------------------------
# pn-UserAttributes
# ---------------------------------------------------------------------------

UA_CLEAN_AS_IS = dq_case(
    DQCaseSpec(
        payload_input=PayloadInput(
            table=Table.USER_ATTRIBUTES,
            keys={
                "pk": field("AB#PF-2254ef33-7c38-46cf-8a87-04ec996499d7"),
                "sk": field("COURTESY#default#EMAIL"),
            },
            old_image={
                "created": field("2026-06-04T10:00:01.741913174Z"),
                "sk": field("COURTESY#default#EMAIL"),
                "addresshash": field(
                    "36f9e5c10b0a6da0f419711c07c137dbb442a0bec349357d9df3c97cd5a2134b"
                ),
                "pk": field("AB#PF-2254ef33-7c38-46cf-8a87-04ec996499d7"),
                "lastModified": field("2026-06-04T10:00:01.741913174Z"),
            },
        ),
        category=Category.CLEAN,
        name="as-is",
        record_id="clean-as-is",
        image_source="OldImage",
        removed_fields=["addresshash"],
    )
)

UA_QUARANTINE_AS_IS = dq_case(
    DQCaseSpec(
        payload_input=PayloadInput(
            table=Table.USER_ATTRIBUTES,
            keys={
                "pk": field("AB#PF-2254ef33-7c38-46cf-8a87-04ec996499d7"),
                "sk": field("TEST_PROVA#default#EMAIL"),
            },
            new_image={
                "created": field("2026-06-04T10:00:01.741913174Z"),
                "sk": field("TEST_PROVA#default#EMAIL"),
                "addresshash": field(
                    "36f9e5c10b0a6da0f419711c07c137dbb442a0bec349357d9df3c97cd5a2134b"
                ),
                "pk": field("AB#PF-2254ef33-7c38-46cf-8a87-04ec996499d7"),
                "lastModified": field("2026-06-04T10:00:01.741913174Z"),
            },
        ),
        category=Category.QUARANTINE,
        name="as-is",
        record_id="quarantine-as-is",
        image_source="NewImage",
        errors=[dq_error("DQ_INVALID_LEGAL_COURTESY", "check_invalid_legal_courtesy")],
        removed_fields=["addresshash"],
    )
)

UA_EXCLUDED_AS_IS = dq_case(
    DQCaseSpec(
        payload_input=PayloadInput(
            table=Table.USER_ATTRIBUTES,
            keys={
                "pk": field("VC#PF-b3ccac31-38ea-44cd-9601-9f2d19e853af"),
                "sk": field(
                    "5b12737bd46c14c8d587929f875bfc1bb97e90da595af226e40b83582b6d1aaf#EMAIL"
                ),
            },
            new_image={
                "failedAttempts": number(0),
                "addressType": field("COURTESY"),
                "lastModified": field("2026-07-08T10:21:53.298984901Z"),
                "senderId": field("default"),
                "created": field("2026-07-08T10:21:53.298984901Z"),
                "verificationCode": field("37034"),
                "pecValid": boolean(False),
                "ttl": number(1783506413),
                "sk": field(
                    "5b12737bd46c14c8d587929f875bfc1bb97e90da595af226e40b83582b6d1aaf#EMAIL"
                ),
                "codeValid": boolean(False),
                "pk": field("VC#PF-b3ccac31-38ea-44cd-9601-9f2d19e853af"),
                "requestId": field("d47355df-73cf-48fe-952b-cde2695df2f4"),
            },
            old_image={
                "failedAttempts": number(0),
                "addressType": field("COURTESY"),
                "lastModified": field("2026-07-08T10:21:53.298984901Z"),
                "senderId": field("default"),
                "created": field("2026-07-08T10:21:53.298984901Z"),
                "verificationCode": field("37034"),
                "pecValid": boolean(False),
                "ttl": number(1783506413),
                "sk": field(
                    "5b12737bd46c14c8d587929f875bfc1bb97e90da595af226e40b83582b6d1aaf#EMAIL"
                ),
                "codeValid": boolean(False),
                "pk": field("VC#PF-b3ccac31-38ea-44cd-9601-9f2d19e853af"),
            },
        ),
        category=Category.EXCLUDED,
        name="as-is",
        record_id="excluded-as-is",
        image_source="NewImage",
        exclusion="excluded_pk_prefix",
        # no field removed: the images don't contain addresshash
    )
)

UA_ERROR_NOT_JSON = DQTestCase(
    table=Table.USER_ATTRIBUTES,
    category=Category.ERROR,
    name="processing-failed",
    record_id="processing-failed-test",
    payload="this-is-not-json",
    expected={
        "result": "ProcessingFailed",
    },
)

# register pn-UserAttributes payloads in the global list used by tests
PAYLOADS.extend([
    UA_CLEAN_AS_IS,
    UA_QUARANTINE_AS_IS,
    UA_EXCLUDED_AS_IS,
    UA_ERROR_NOT_JSON,
])
