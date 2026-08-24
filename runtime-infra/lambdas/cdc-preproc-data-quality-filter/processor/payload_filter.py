from processor.ddb_utils import remove_fields


def _apply_remove_fields(payload, rule):
    return remove_fields(
        payload=payload,
        field_names=rule.get("fields", []),
        image_names=rule.get(
            "images",
            ["NewImage", "OldImage"],
        ),
    )


FILTER_HANDLERS = {
    "remove_fields": _apply_remove_fields,
}


def apply_filters(payload, processing_layer, filters):
    for rule in filters:
        apply_to = rule.get("applyTo", [])

        if apply_to and processing_layer not in apply_to:
            continue

        filter_type = rule.get("type")
        handler = FILTER_HANDLERS.get(filter_type)

        if handler is None:
            raise ValueError(
                f"Unsupported payload filter: {filter_type}"
            )

        payload = handler(payload, rule)

    return payload