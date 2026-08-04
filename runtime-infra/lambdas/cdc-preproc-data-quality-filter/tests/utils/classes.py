from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any


# DynamoDB tables covered by the tests
class Table(Enum):
    USER_ATTRIBUTES = "pn-UserAttributes"


# DQ routing outcome, plus ERROR for technical failures
class Category(Enum):
    CLEAN = "clean"
    QUARANTINE = "quarantine"
    EXCLUDED = "excluded"
    ERROR = "error"


# only these categories can come out of execute_dq
def is_dq_routing(category: Category) -> bool:
    return category is not Category.ERROR


# fake Lambda context, providing just the attribute lambda_handler reads
class LambdaContext:
    aws_request_id = "test-request-id"


# raw input for build_payload: table plus DynamoDB images of the record
@dataclass
class PayloadInput:
    table: Table
    keys: dict | None = None
    new_image: dict | None = None
    old_image: dict | None = None

    # copy with the given fields dropped from new_image/old_image
    def without(self, *field_names: str) -> "PayloadInput":
        def drop(image):
            return (
                {k: v for k, v in image.items() if k not in field_names}
                if image is not None
                else None
            )

        return replace(
            self,
            new_image=drop(self.new_image),
            old_image=drop(self.old_image),
        )


# registered use case: input payload and expected result
@dataclass
class DQTestCase:
    table: Table
    category: Category
    name: str
    record_id: str
    payload: Any
    expected: dict[str, Any]


# declarative spec for a DQ-routing case, built into a DQTestCase by dq_case()
@dataclass
class DQCaseSpec:
    payload_input: PayloadInput
    category: Category
    name: str
    record_id: str
    image_source: str
    errors: list[dict] = field(default_factory=list)
    exclusion: str | None = None
    removed_fields: list[str] = field(default_factory=list)
