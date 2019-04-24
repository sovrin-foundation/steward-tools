#!/usr/bin/env python3
# -*- coding: utf-8 -*-
''' token-minter
A minimal GUI that simplifies the workflow necessary for a group of network
trustees to create a minting transaction, add the necessary signatures, and
submit the transaction to the Sovrin network.
'''

import os, sys
try:
    app_base_dir = os.path.dirname(__file__)
except:
    pass
if app_base_dir:
    os.sys.path.append(app_base_dir)
os.sys.path.append(os.getcwd())
 

from src import main
 

if __name__ == '__main__':
    app = main.MainWindow()
    app.mainloop()
    main.clean(app)


# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
