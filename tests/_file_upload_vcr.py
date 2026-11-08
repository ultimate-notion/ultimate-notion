from __future__ import annotations

import re
from typing import Any

from tests.conftest import SECRET_PARAMS, normalize_response

FILE_UPLOAD_QUERY_PARAMS = [*SECRET_PARAMS, 'X-Amz-Credential', 'X-Amz-Security-Token', 'X-Amz-Signature']
SIGNED_QUERY_VALUE = re.compile(r'(X-Amz-(?:Credential|Security-Token|Signature)=)[^&"\\\s]+', flags=re.IGNORECASE)


def redact_file_response(response: dict[str, Any]) -> dict[str, Any]:
    """Redact temporary file-access credentials while preserving normal cassette normalization."""
    response = normalize_response(response)
    if isinstance(content := response.get('content'), str):
        response['content'] = SIGNED_QUERY_VALUE.sub(r'\1secret...', content)
    return response
