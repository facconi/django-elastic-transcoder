import json

from django.http import HttpResponse, HttpResponseBadRequest
from django.core.mail import mail_admins

from .models import EncodeJob
from .signals import (
    transcode_onprogress,
    transcode_onerror,
    transcode_oncomplete
)

def endpoint(request):
    """
    Receive SNS notification
    """

    try:
        data = json.loads(request.read())
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

    #
    if message['state'] == 'PROGRESSING':
        job = EncodeJob.objects.get(pk=message['jobId'])
        job.message = 'Progress'
        job.state = 1
        job.save()

        transcode_onprogress.send(sender=None, message=message)
    elif message['state'] == 'COMPLETED':
        job = EncodeJob.objects.get(pk=message['jobId'])
        job.message = 'Success'
        job.state = 4
        job.save()

        transcode_oncomplete.send(sender=None, message=message)
    elif message['state'] == 'ERROR':
        job = EncodeJob.objects.get(pk=message['jobId'])
        job.message = message['messageDetails']
        job.state = 2
        job.save()

        transcode_onerror.send(sender=None, message=message)

    return HttpResponse('Done')
