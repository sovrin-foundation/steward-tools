import json
import platform
import asyncio
import smtplib
from ctypes import cdll
from getpass import getpass
from pathlib import Path
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from constants import LIBRARY


INITIAL_DIR = Path.home()

loop = asyncio.get_event_loop()


def library():
    your_platform = platform.system().lower()
    return LIBRARY[your_platform] if (your_platform in LIBRARY) else 'libsovtoken.so'


def load_payment_plugin():
    try:
        payment_plugin = cdll.LoadLibrary(library())
        payment_plugin.sovtoken_init()
    except Exception as e:
        raise Exception(e)


def run_coroutine(coroutine):
    return loop.run_until_complete(coroutine)


def run_array(array: list):
    return run_coroutine(asyncio.wait(array))


def read_file(data_file):
    with open(data_file, newline='') as data_file:
        return data_file.read()


def send_email(fails, email_info_file):
    try:
        email_info = json.loads(read_file(email_info_file))
    except Exception as err:
        print("No information for email sending found: {}".format(err))
        return

    password = email_info["password"] if "password" in email_info else getpass(
        "Enter Password for Email Account \"{}\":   ".format(email_info['from']))

    lines = ["Payment Address: {},    Expected Tokens: {},    Actual Tokens: {}".format(
        address, values['expected'], values['actual']) for address, values in fails.items()]

    body = "Token Balance check failed. The following discrepancies were found: \n {}".format("\n".join(lines))

    print(body)
    print("Sending email notification to {}".format(email_info['to']))

    try:
        server = smtplib.SMTP_SSL(email_info['host'], email_info['port'])
        server.ehlo()
        server.login(email_info['from'], password)
    except Exception as err:
        print("Can not connect to email server: {}".format(err))
        return

    message = MIMEMultipart()

    message['From'] = email_info['from']
    message['To'] = email_info['to']
    message['Subject'] = email_info['subject']

    email_text = """\
Token Balance check failed
The following discrepancies were found:

%s
    """ % ("\n".join(lines))

    message.attach(MIMEText(email_text, 'plain'))

    try:
        server.sendmail(email_info['from'], email_info['to'], message.as_string())
        print("Mail has been successfully sent to {}".format(email_info['to']))
    except Exception as err:
        print("Sending email to {} failed with {}".format(email_info['to'], err))
    server.close()
