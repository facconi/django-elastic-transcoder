import json

from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.core.mail import mail_admins

from .models import EncodeJob
from .signals import (
    transcode_onprogress,
    transcode_onerror,
    transcode_oncomplete
)

@csrf_exempt
def endpoint(request):
    """
    Receive SNS notification
    """

    try:
        data = json.loads(request.read().decode('utf-8'))
    except ValueError:
        return HttpResponseBadRequest('Invalid JSON')

    # handle SNS subscription
    if data['Type'] == 'SubscriptionConfirmation':
        subscribe_url = data['SubscribeURL']
        subscribe_body = """
        Please visit this URL below to confirm your subscription with SNS

        %s """ % subscribe_url

        mail_admins('Please confirm SNS subscription', subscribe_body)
        return HttpResponse('OK')

    
    #
    try:
        message = json.loads(data['Message'])
    except ValueError:
        assert False, data['Message']

    try:
        # Turn the dictionary into a readable string format
        formatted_str_message = json.dumps(message, indent=2)
    except (TypeError, ValueError):
        # Couldn't format it, so set it to the raw message
        formatted_str_message = data['Message']

    if message['state'] == 'PROGRESSING':
        try:
            job = EncodeJob.objects.get(pk=message['jobId'])
            job.message = 'Progress'
            job.state = 1
            job.save()
        except EncodeJob.DoesNotExist:
            job = None

        transcode_onprogress.send(sender=None, job=job, message=message)
    elif message['state'] == 'COMPLETED':
        try:
            job = EncodeJob.objects.get(pk=message['jobId'])
            job.message = 'Success'
            job.state = 4
            job.save()
        except EncodeJob.DoesNotExist:
            job = None

        transcode_oncomplete.send(sender=None, job=job, message=message)
    elif message['state'] == 'ERROR':
        try:
            job = EncodeJob.objects.get(pk=message['jobId'])

            """
            error_message = 'messageDetails' in message and message['messageDetails'] or ''
            # when you convert HLS there is no messageDetails,
            # but there are list of segements and statusDetail for each item

            if not error_message and 'outputs' in message and len(message['outputs']):
                # let's find first segment with error response
                error_segment = next((i for i in message['outputs'] if i['status'] == 'Error'), None)
                error_message = error_segment and error_segment['statusDetail'] or 'Error'

            job.message = error_message
            """
            job.message = formatted_str_message
            job.state = 2
            job.save()
        except EncodeJob.DoesNotExist:
            job = None

        transcode_onerror.send(sender=None, job=job, message=message)

    return HttpResponse('Done')
