import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

import boto3


SECRETS_MANAGER = boto3.client('secretsmanager')
SLACK_API_BASE_URL = 'https://slack.com/api/'
SLACK_SNIPPET_MAX_BYTES = 1000000
SLACK_TOKEN = None


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
    print('Selected route: %s/%s -> %s' % (route['type'], route['match'], channel_id))

    attachment = message.get('attachment')
    prepared_attachment = None
    if route['type'] == 'report' and attachment:
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
            '*CSV non allegato:* il file `%s` supera il limite di %s MiB.' % (
                prepared_attachment['filename'],
                int(os.environ.get('MAX_CSV_ATTACHMENT_BYTES', '5242880')) // 1048576,
            )
        ))
    elif prepared_attachment and prepared_attachment.get('downloadError'):
        output_message['blocks'].append(mrkdwn_section(
            '*CSV non allegato:* non e stato possibile scaricare `%s` da S3.' % (
                prepared_attachment['filename'],
            )
        ))
    print('########### OUTPUT MESSAGE #############')
    print(output_message)
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
        if len(fields) != 3 or not all(fields):
            raise ValueError('Invalid route at position %s: expected type,match,channel' % position)

        route_type, match, channel = fields
        if route_type not in ('alarm', 'report'):
            raise ValueError('Unsupported route type at position %s: %s' % (position, route_type))
        if re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*', match) is None:
            raise ValueError('Invalid route match at position %s: %s' % (position, match))
        if re.fullmatch(r'C[A-Z0-9]+', channel) is None:
            raise ValueError('Invalid Slack channel ID for match %s' % match)

        routes.append({'type': route_type, 'match': match, 'channel': channel})
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
    account_id = extract_alarm_account_id(message)
    environment = os.environ.get('ENVIRONMENT_TYPE', 'unknown').upper()
    title = '%s %s - %s' % (account_id, environment, alarm_name)
    return {
        'channel': channel_id,
        'text': '%s: %s' % (title, state),
        'blocks': [
            header_block(title),
            {
                'type': 'section',
                'fields': [
                    mrkdwn_field('*Stato:*\n%s' % state),
                    mrkdwn_field('*Regione:*\n%s' % region),
                ],
            },
            mrkdwn_section('*Dettaglio:*\n%s' % reason),
        ],
    }


def render_report(route, message, channel_id):
    data = message.get('data') or {}
    links = message.get('links') or {}
    required = ['findingCount', 'findingTypeCounts', 'accountId', 'accountRole']
    missing = [key for key in required if key not in data]
    if missing or not links.get('dashboard'):
        raise ValueError('Invalid IAM unused access report: missing %s' % ', '.join(missing or ['links.dashboard']))

    breakdown = '\n'.join(
        '- %s: %s' % (name, count)
        for name, count in sorted(data['findingTypeCounts'].items())
    ) or '- Nessun dettaglio disponibile'
    environment = str(message.get('environment', os.environ.get('ENVIRONMENT_TYPE', 'unknown'))).upper()
    producer = message.get('producer') or route['match']
    title = '%s %s - %s' % (data['accountId'], environment, producer)
    return {
        'channel': channel_id,
        'text': '%s: %s finding' % (title, data['findingCount']),
        'blocks': [
            header_block(title),
            {
                'type': 'section',
                'fields': [
                    mrkdwn_field('*Account:*\n%s' % data['accountId']),
                    mrkdwn_field('*Finding:*\n%s' % data['findingCount']),
                ],
            },
            mrkdwn_section('*Dettaglio per tipologia:*\n%s' % breakdown),
            mrkdwn_section('*Dashboard CloudWatch:* <%s|Apri dashboard>' % links['dashboard']),
        ],
    }


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
    filename = os.path.basename(str(attachment.get('filename', '')))
    content_type = attachment.get('contentType')
    download_url = attachment.get('downloadUrl')
    declared_size = attachment.get('size')
    if not filename or content_type != 'text/csv' or not download_url:
        raise ValueError('Invalid CSV attachment metadata')
    max_size = int(os.environ.get('MAX_CSV_ATTACHMENT_BYTES', '5242880'))
    if declared_size is not None and int(declared_size) > max_size:
        return {'filename': filename, 'size': int(declared_size), 'tooLarge': True}

    parsed_url = urllib.parse.urlparse(download_url)
    hostname = parsed_url.hostname or ''
    if parsed_url.scheme != 'https' or not (
        hostname.endswith('.amazonaws.com') or hostname.endswith('.amazonaws.com.cn')
    ):
        raise ValueError('CSV attachment URL must be an HTTPS AWS URL')

    with urllib.request.urlopen(download_url, timeout=10) as response:
        csv_content = response.read(max_size + 1)
    if len(csv_content) > max_size:
        return {'filename': filename, 'size': len(csv_content), 'tooLarge': True}
    return {'filename': filename, 'content': csv_content, 'tooLarge': False}


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
    global SLACK_TOKEN
    if SLACK_TOKEN:
        return SLACK_TOKEN
    secret_name = os.environ['SLACK_BOT_TOKEN_SECRET_NAME']
    secret_value = SECRETS_MANAGER.get_secret_value(SecretId=secret_name)['SecretString']
    try:
        secret_json = json.loads(secret_value)
        if isinstance(secret_json, dict):
            SLACK_TOKEN = secret_json.get('token') or secret_json.get('botToken') or secret_json.get('slackBotToken')
        elif isinstance(secret_json, str):
            SLACK_TOKEN = secret_json
    except json.JSONDecodeError:
        SLACK_TOKEN = secret_value
    if not SLACK_TOKEN:
        raise ValueError('Slack bot token secret is empty or has no supported token property')
    return SLACK_TOKEN


def extract_alarm_name(message):
    return message.get('AlarmName') or message.get('alarmName')


def extract_alarm_account_id(message):
    account_id = message.get('AWSAccountId') or message.get('awsAccountId')
    if account_id:
        return str(account_id)

    alarm_arn = message.get('AlarmArn') or message.get('alarmArn') or ''
    arn_parts = alarm_arn.split(':', 6)
    if len(arn_parts) == 7 and arn_parts[4]:
        return arn_parts[4]
    return 'unknown-account'
