from fiatReconciler import run
from aiohttp import web
import sys
import asyncio
import os.path
path = os.path.expanduser("~") + '/steward-tools/fiat_reconciliation/'
sys.path.append(path)
sys.path.append(os.path.expanduser("~") + '/steward-tools/local_ledger')

gotResponse = True

# Sends a request to the server which runs fiatReconciler.py on a timerange.


async def postHandle(request):
    # This acts as a lock since only one thread can access Local_Ledger at a
    # time. Prevents more than one request at once.
    global gotResponse
    if not gotResponse:
        return web.Response(text='Error: Not done processing last request. Please wait.')  # noqa

    if not request.body_exists:
        return web.Response(text='Error receiving start/end dates')
    # Parse data
    requestData = await request.read()
    parsedData = requestData.decode('ascii').split('&')
    for d in parsedData:
        if d.startswith('startdate='):
            startdate = d[len('startdate='):]
        elif d.startswith('enddate='):
            enddate = d[len('enddate='):]

    if startdate is None or enddate is None:
        return web.Response(text='Error receiving start/end dates')

    print('Dates:', startdate, enddate)

    # This contains all arguments needed to run fiatReconciler.py
    class argsContainer():
        pool_name = 'mainnet'
        wallet_name = 'junk'
        wallet_key = 'junk'
        signing_did = 'PLppMr8ttu37FnE5B4wRMu'
        start_date = None
        end_date = None
        database_dir = path + 'ledger_copy.db'

    args = argsContainer()
    args.start_date = startdate
    args.end_date = enddate

    # BUG: stalls when accidental large date value written (eg year 20190)
    # Should not matter unless post data is manually sent with this error
    # Runs the script and displays any errors
    try:
        gotResponse = False
        await run(args)
    except ValueError as e:
        print(e)
        gotResponse = True
        return web.Response(text='Error: Wrong date formatting')
    except Exception as e:
        print(e)
        gotResponse = True
        return web.Response(text='Error: ' + str(e))
    outputFilename = 'billing ' + startdate.replace('/', '-') + ' to ' + \
        enddate.replace('/', '-') + '.csv'

    try:
        # attempt to send the output file contents to the client
        text = None
        with open(outputFilename) as f:
            text = f.read()
            if text is None:
                gotResponse = True
                return web.Response(text='Error: ' + str(rv))
    except FileNotFoundError:
        gotResponse = True
        return web.Response(text='Error: ' + str(rv))

    # if we got here, everything was successful
    gotResponse = True
    return web.Response(text=text, content_type='text/html')


# Send main webpage to user that allows sending post requests
async def getHandle(request):
    text = None
    with open('/www/index.html') as f:
        text = f.read()
    return web.Response(text=text, content_type='text/html')


app = web.Application()
app.add_routes([web.get('/', getHandle),
                web.post('/', postHandle)])

web.run_app(app)
