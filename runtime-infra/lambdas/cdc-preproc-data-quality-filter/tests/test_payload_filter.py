import pytest

from processor.payload_filter import apply_filters


def _payload_with_addresshash():
    return {
        "dynamodb": {
            "NewImage": {
                "pk": {"S": "AB#PF-1"},
                "addresshash": {"S": "hash"},
            },
            "OldImage": {
                "pk": {"S": "AB#PF-1"},
                "addresshash": {"S": "hash"},
            },
        }
    }


# test che verifica quando il filtro "remove_fields" viene applicato o meno, in base a processing layer,
# applyTo e immagini indicate
@pytest.mark.parametrize(
    "processing_layer,filters,removed_from_new,removed_from_old",
    [
        pytest.param(
            "clean",
            [{"type": "remove_fields", "fields": ["addresshash"], "applyTo": ["clean", "quarantine"]}],
            True,
            True,
            id="applies-when-layer-in-apply-to",
        ),
        pytest.param(
            "clean",
            [{"type": "remove_fields", "fields": ["addresshash"], "applyTo": ["quarantine"]}],
            False,
            False,
            id="skips-when-layer-not-in-apply-to",
        ),
        pytest.param(
            "excluded",
            [{"type": "remove_fields", "fields": ["addresshash"]}],
            True,
            True,
            id="applies-always-when-apply-to-empty",
        ),
        pytest.param(
            "clean",
            [{"type": "remove_fields", "fields": ["addresshash"], "images": ["NewImage"]}],
            True,
            False,
            id="respects-custom-image-names",
        ),
    ],
)
def test_apply_filters_remove_fields(processing_layer, filters, removed_from_new, removed_from_old):
    payload = _payload_with_addresshash()

    result = apply_filters(payload, processing_layer=processing_layer, filters=filters)

    assert ("addresshash" not in result["dynamodb"]["NewImage"]) == removed_from_new
    assert ("addresshash" not in result["dynamodb"]["OldImage"]) == removed_from_old


# test che verifica che il payload resti invariato quando non è configurato alcun filtro:
# il confronto è con una copia costruita a parte, perché apply_filters restituisce lo
# stesso oggetto ricevuto e un assert result == payload sarebbe sempre vero
def test_apply_filters_with_no_filters_returns_payload_unchanged():
    payload = _payload_with_addresshash()

    result = apply_filters(payload, processing_layer="clean", filters=[])

    assert result == _payload_with_addresshash()


# test che verifica che venga sollevato un errore per un tipo di filtro non supportato
def test_apply_filters_unsupported_type_raises_value_error():
    payload = _payload_with_addresshash()
    filters = [{"type": "unsupported_filter"}]

    with pytest.raises(ValueError):
        apply_filters(payload, processing_layer="clean", filters=filters)
