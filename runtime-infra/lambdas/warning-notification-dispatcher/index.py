import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

SLACK_API_BASE_URL = 'https://slack.com/api/'
SLACK_SNIPPET_MAX_BYTES = 1000000
REPORT_DELIVERY_MODES = ('ATTACHMENT', 'SUMMARY', 'LINK')
ALARM_STATE_COLORS = {
    'ALARM': '#D13212',
    'OK': '#2EB67D',
    'INSUFFICIENT_DATA': '#ECB22E',
}


def lambda_handler(event, context):
    if not event or 'Records' not in event:
        raise ValueError('Empty event')
    for record in event['Records']:
        handle_record(record)
    return {'processed': len(event['Records'])}


def handle_record(record):
    body = json.loads(record['body'])
    message = json.loads(body['Message'])
    print('Input event: %s' % {
        'eventId': message.get('eventId'),
        'eventType': classify_event(message),
        'producer': message.get('producer'),
        'alarmName': extract_alarm_name(message),
    })

    routes = parse_routes(os.environ.get('ROUTES', ''))
    route = select_route(routes, message)
    if route is None:
        raise ValueError('No route matched the warning message')
    channel_id = route['channel']
    print('Selected route: %s/%s -> %s (%s)' % (
        route['type'],
        route['match'],
        channel_id,
        route.get('deliveryMode', 'DEFAULT'),
    ))
    if channel_id == 'DROP':
        print(json.dumps({
            'action': 'DROP',
            'eventType': classify_event(message),
            'match': route['match'],
            'alarmName': extract_alarm_name(message),
            'producer': message.get('producer'),
            'environment': os.environ.get('ENVIRONMENT_TYPE', 'unknown'),
        }, separators=(',', ':')))
        return

    attachment = message.get('attachment')
    prepared_attachment = None
    if route['type'] == 'report' and route['deliveryMode'] == 'ATTACHMENT' and attachment:
        try:
            prepared_attachment = prepare_csv_attachment(attachment)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as error:
            prepared_attachment = {
                'filename': os.path.basename(str(attachment.get('filename', 'report.csv'))),
                'downloadError': attachment_download_error(error),
            }

    output_message = render_message(route, message, channel_id)
    if prepared_attachment and prepared_attachment.get('tooLarge'):
        output_message['blocks'].append(mrkdwn_section(
            '*CSV non allegato:* il file `%s` supera il limite di %s MiB. '
            '<%s|Scarica CSV (link temporaneo)>' % (
                prepared_attachment['filename'],
                int(os.environ.get('MAX_CSV_ATTACHMENT_BYTES', '5242880')) // 1048576,
                prepared_attachment['downloadUrl'],
            )
        ))
        output_message['unfurl_links'] = False
        output_message['unfurl_media'] = False
    elif prepared_attachment and prepared_attachment.get('downloadError'):
        output_message['blocks'].append(mrkdwn_section(
            '*CSV non allegato:* non è stato possibile scaricare `%s` da S3.' % (
                prepared_attachment['filename'],
            )
        ))
    print('Output message prepared: %s' % {
        'routeType': route['type'],
        'match': route['match'],
        'channel': channel_id,
        'deliveryMode': route.get('deliveryMode'),
        'hasAttachment': bool(prepared_attachment),
    })
    if prepared_attachment and not prepared_attachment.get('tooLarge') and not prepared_attachment.get('downloadError'):
        upload_csv_to_slack(prepared_attachment, output_message)
    else:
        post_to_slack(output_message)


def parse_routes(routes_config):
    if not routes_config:
        raise ValueError('ROUTES must contain at least one route')

    routes = []
    for position, route_config in enumerate(routes_config.split(';'), start=1):
        fields = [field.strip() for field in route_config.split(',')]
        if len(fields) not in (3, 4) or not all(fields):
            raise ValueError(
                'Invalid route at position %s: expected type,match,channel[,deliveryMode]' % position
            )

        route_type, match, channel = fields[:3]
        delivery_mode = fields[3] if len(fields) == 4 else None
        if route_type not in ('alarm', 'report'):
            raise ValueError('Unsupported route type at position %s: %s' % (position, route_type))
        if re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*', match) is None:
            raise ValueError('Invalid route match at position %s: %s' % (position, match))
        if channel != 'DROP' and re.fullmatch(r'C[A-Z0-9]+', channel) is None:
            raise ValueError('Invalid route destination for match %s' % match)
        if delivery_mode and (route_type != 'report' or channel == 'DROP'):
            raise ValueError('Delivery mode is supported only for report routes to Slack')
        if delivery_mode and delivery_mode not in REPORT_DELIVERY_MODES:
            raise ValueError('Unsupported report delivery mode at position %s: %s' % (position, delivery_mode))
        if route_type == 'report' and channel != 'DROP' and delivery_mode is None:
            delivery_mode = 'ATTACHMENT'

        route = {'type': route_type, 'match': match, 'channel': channel}
        if delivery_mode:
            route['deliveryMode'] = delivery_mode
        routes.append(route)
    return routes


def select_route(routes, message):
    for route in routes:
        if route.get('enabled', True) and route_matches(route, message):
            return route
    return None


def route_matches(route, message):
    event_type = classify_event(message)
    if route['type'] == 'alarm':
        alarm_name = extract_alarm_name(message)
        if event_type != 'cloudwatch-alarm' or not alarm_name:
            return False
        return re.search(r'(^|-)%s($|-)' % re.escape(route['match']), alarm_name) is not None
    if route['type'] == 'report':
        return event_type == 'report' and message.get('producer') == route['match']
    return False


def classify_event(message):
    if extract_alarm_name(message):
        return 'cloudwatch-alarm'
    return message.get('eventType', 'unknown')


def render_message(route, message, channel_id):
    if route['type'] == 'alarm':
        return render_cloudwatch_alarm(route, message, channel_id)
    if route['type'] == 'report':
        return render_report(route, message, channel_id)
    raise ValueError('Unsupported route type: %s' % route['type'])


def render_cloudwatch_alarm(route, message, channel_id):
    alarm_name = extract_alarm_name(message) or 'CloudWatch alarm'
    state = message.get('NewStateValue') or message.get('newStateValue') or 'UNKNOWN'
    reason = message.get('NewStateReason') or message.get('newStateReason') or 'Motivo non disponibile'
    region = message.get('Region') or message.get('region') or os.environ.get('AWS_REGION', 'unknown')
    environment = os.environ.get('ENVIRONMENT_TYPE', 'unknown')
    alarm_url = cloudwatch_alarm_url(message, alarm_name)
    alarm_blocks = [
        header_block(alarm_name),
        {
            'type': 'section',
            'fields': [
                mrkdwn_field('*Stato:*\n%s' % state),
                mrkdwn_field('*Regione:*\n%s' % region),
                mrkdwn_field('*Env:*\n%s' % environment),
            ],
        },
        mrkdwn_section('*Dettaglio:*\n%s' % reason),
    ]
    if alarm_url:
        alarm_blocks.append(mrkdwn_section('*CloudWatch:* <%s|Apri allarme>' % alarm_url))
    return {
        'channel': channel_id,
        'attachments': [{
            'fallback': '%s: %s' % (alarm_name, state),
            'color': ALARM_STATE_COLORS.get(str(state).upper(), '#808080'),
            'blocks': alarm_blocks,
        }],
    }


def render_report(route, message, channel_id):
    data = message.get('data') or {}
    metrics = data.get('metrics')
    details = data.get('details') or {}
    links = message.get('links') or {}
    title = message.get('title')
    if not title or not isinstance(metrics, dict) or not metrics:
        raise ValueError('Invalid report: title and non-empty data.metrics are required')
    if not isinstance(details, dict):
        raise ValueError('Invalid report: data.details must be an object')
    if not isinstance(links, dict):
        raise ValueError('Invalid report: links must be an object')

    environment = str(message.get('environment', os.environ.get('ENVIRONMENT_TYPE', 'unknown')))
    fields = [mrkdwn_field('*Env:*\n%s' % environment.upper())]
    for name, value in list(metrics.items())[:9]:
        fields.append(mrkdwn_field('*%s:*\n%s' % (str(name), str(value))))
    blocks = [
        header_block(str(title)),
        {'type': 'section', 'fields': fields},
    ]

    duration_ms = data.get('durationMs')
    if duration_ms is not None:
        blocks.append(mrkdwn_section('*Durata:* %.2f secondi' % (float(duration_ms) / 1000)))
    if details:
        breakdown = '\n'.join(
            '- %s: %s' % (name, value)
            for name, value in list(sorted(details.items()))[:20]
        )
        blocks.append(mrkdwn_section('*Dettaglio:*\n%s' % breakdown))

    report_links = []
    for name, url in list(links.items())[:10]:
        parsed_url = urllib.parse.urlparse(str(url))
        if parsed_url.scheme == 'https' and parsed_url.netloc:
            label = str(name).replace('_', ' ').strip().title()
            report_links.append('<%s|%s>' % (parsed_url.geturl(), label))
    if report_links:
        blocks.append(mrkdwn_section('*Link:* ' + ' | '.join(report_links)))

    result = {'channel': channel_id, 'blocks': blocks}
    if route['deliveryMode'] == 'LINK':
        _, download_url = validate_csv_attachment(message.get('attachment') or {})
        blocks.append(mrkdwn_section('*Report CSV:* <%s|Scarica CSV (link temporaneo)>' % download_url))
        result['unfurl_links'] = False
        result['unfurl_media'] = False
    return result


def header_block(text):
    return {
        'type': 'header',
        'text': {'type': 'plain_text', 'text': text[:150]},
    }


def mrkdwn_section(text):
    return {'type': 'section', 'text': {'type': 'mrkdwn', 'text': text[:3000]}}


def mrkdwn_field(text):
    return {'type': 'mrkdwn', 'text': text[:2000]}


def post_to_slack(payload):
    return slack_api('chat.postMessage', payload)


def slack_api(method, payload, form_encoded=False):
    if form_encoded:
        request_body = urllib.parse.urlencode(payload).encode('utf-8')
        content_type = 'application/x-www-form-urlencoded; charset=utf-8'
    else:
        request_body = json.dumps(payload).encode('utf-8')
        content_type = 'application/json; charset=utf-8'
    request = urllib.request.Request(
        SLACK_API_BASE_URL + method,
        data=request_body,
        headers={
            'Authorization': 'Bearer %s' % slack_token(),
            'Content-Type': content_type,
        },
        method='POST',
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            result = json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as error:
        raise RuntimeError('Slack HTTP error %s' % error.code) from error
    if not result.get('ok'):
        error_details = {
            key: result[key]
            for key in ('error', 'needed', 'provided', 'response_metadata')
            if key in result
        }
        raise RuntimeError('Slack API error: %s' % json.dumps(error_details, separators=(',', ':')))
    return result


def prepare_csv_attachment(attachment):
    filename, download_url = validate_csv_attachment(attachment)
    declared_size = attachment.get('size')
    max_size = int(os.environ.get('MAX_CSV_ATTACHMENT_BYTES', '5242880'))
    if declared_size is not None and int(declared_size) > max_size:
        return {
            'filename': filename,
            'downloadUrl': download_url,
            'size': int(declared_size),
            'tooLarge': True,
        }

    with urllib.request.urlopen(download_url, timeout=10) as response:
        csv_content = response.read(max_size + 1)
    if len(csv_content) > max_size:
        return {
            'filename': filename,
            'downloadUrl': download_url,
            'size': len(csv_content),
            'tooLarge': True,
        }
    return {'filename': filename, 'content': csv_content, 'tooLarge': False}


def validate_csv_attachment(attachment):
    filename = os.path.basename(str(attachment.get('filename', '')))
    content_type = attachment.get('contentType')
    download_url = attachment.get('downloadUrl')
    if not filename or content_type != 'text/csv' or not download_url:
        raise ValueError('Invalid CSV attachment metadata')

    parsed_url = urllib.parse.urlparse(download_url)
    hostname = parsed_url.hostname or ''
    if parsed_url.scheme != 'https' or not (
        hostname.endswith('.amazonaws.com') or hostname.endswith('.amazonaws.com.cn')
    ):
        raise ValueError('CSV attachment URL must be an HTTPS AWS URL')
    return filename, download_url


def attachment_download_error(error):
    if isinstance(error, urllib.error.HTTPError):
        response_body = error.read(2048).decode('utf-8', errors='replace')
        print('S3 attachment download failed: HTTP %s, response=%s' % (error.code, response_body))
        return 'HTTP %s' % error.code
    print('S3 attachment download failed: %s' % error)
    return str(error)


def upload_csv_to_slack(prepared_attachment, message):
    filename = prepared_attachment['filename']
    csv_content = prepared_attachment['content']
    upload_metadata = {
        'filename': filename[:255],
        'length': len(csv_content),
    }
    if len(csv_content) <= SLACK_SNIPPET_MAX_BYTES:
        upload_metadata['snippet_type'] = 'csv'
    upload_ticket = slack_api('files.getUploadURLExternal', upload_metadata, form_encoded=True)
    upload_request = urllib.request.Request(
        upload_ticket['upload_url'],
        data=csv_content,
        headers={'Content-Type': 'application/octet-stream'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(upload_request, timeout=15):
            pass
    except urllib.error.HTTPError as error:
        raise RuntimeError('Slack file upload HTTP error %s' % error.code) from error

    completion_payload = {
        'files': [{'id': upload_ticket['file_id'], 'title': filename[:255]}],
        'channel_id': message['channel'],
        'blocks': json.dumps(message['blocks'], separators=(',', ':')),
    }
    slack_api('files.completeUploadExternal', completion_payload)


def slack_token():
    secret_name = os.environ['SLACK_BOT_TOKEN_SECRET_NAME']
    port = os.environ.get('PARAMETERS_SECRETS_EXTENSION_HTTP_PORT', '2773')
    query = urllib.parse.urlencode({'secretId': secret_name})
    request = urllib.request.Request(
        'http://localhost:%s/secretsmanager/get?%s' % (port, query),
        headers={
            'X-Aws-Parameters-Secrets-Token': os.environ['AWS_SESSION_TOKEN'],
        },
        method='GET',
    )
    try:
        with urllib.request.urlopen(request, timeout=2) as response:
            secret_response = json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as error:
        raise RuntimeError('Unable to read Slack bot token from cache: HTTP %s' % error.code) from error
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError) as error:
        raise RuntimeError('Unable to read Slack bot token from cache') from error

    secret_value = secret_response.get('SecretString')
    if not secret_value:
        raise ValueError('Slack bot token secret has no SecretString value')

    token = None
    try:
        secret_json = json.loads(secret_value)
        if isinstance(secret_json, dict):
            token = secret_json.get('token') or secret_json.get('botToken') or secret_json.get('slackBotToken')
        elif isinstance(secret_json, str):
            token = secret_json
    except json.JSONDecodeError:
        token = secret_value
    if not token:
        raise ValueError('Slack bot token secret is empty or has no supported token property')
    return token


def extract_alarm_name(message):
    return message.get('AlarmName') or message.get('alarmName')


def cloudwatch_alarm_url(message, alarm_name):
    alarm_arn = message.get('AlarmArn') or message.get('alarmArn') or ''
    arn_parts = alarm_arn.split(':', 6)
    region = arn_parts[3] if len(arn_parts) == 7 else os.environ.get('AWS_REGION')
    if not region:
        return None
    return (
        'https://%s.console.aws.amazon.com/cloudwatch/home?region=%s#alarmsV2:alarm/%s'
        % (region, region, urllib.parse.quote(alarm_name, safe=''))
    )
