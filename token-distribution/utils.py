import platform
import asyncio
from ctypes import cdll
from pathlib import Path
import csv
import os
import zipfile

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

def read_file(data_file):
    with open(data_file, newline='') as data_file:
        return data_file.read()


def read_csv_file(data_file):
    with open(data_file, 'r') as file:
        return list(csv.reader(file))


def read_zip_file(path):
    with zipfile.ZipFile(path, 'r') as zip:
        files = zip.infolist()
        if len(files) != 1:
            raise Exception("More than 1 file")
        ifile = zip.open(files[0])
        return ifile.read().decode()


def store_zip_file(data):
    out_dir = input("Enter a path to save result:    ")
    out_file = os.path.join(out_dir, 'result.zip')

    with zipfile.ZipFile(out_file, 'w', zipfile.ZIP_DEFLATED) as file:
        file.writestr('result.json', data)

    print("File has been create: {}".format(out_file))



def send_email(from_, to_, subject_, body_, password):
    email_text = """\n\
    From: %s
    To: %s
    Subject: %s

    %s
    """ % (from_, to_, subject_, body_)

    print("Email: " + email_text)

    # server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
    # server.ehlo()
    # server.login(from_, password)
    # server.sendmail(from_, to_, email_text)
    # server.close()