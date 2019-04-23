import tkinter as tk

from tkinter import filedialog
from tkinter import messagebox
from tkinter.font import BOLD

from src.indy_helpers import *
from src.utils import INITIAL_DIR, load_plugin, load_config

LARGE_FONT = ('Verdana', 12)
MEDIUM_FONT = ('Verdana', 10)
ICON_FONT = ('Symbol', 12, BOLD)

TOP_LABEL = {'font': LARGE_FONT, 'pady': 20}
BACK_BUTTON = {'pady': 20, 'padx': 5, 'side': tk.LEFT, 'anchor': 'e', 'expand': 1}
STEP_BUTTON = {'pady': 20, 'padx': 5, 'side': tk.LEFT, 'anchor': 'w', 'expand': 1}
ENTRY_LABEL = {'pady': (20, 2)}
FILE_BUTTON = {'pady': (20, 0)}
FILE_LABEL = {'pady': (5, 0)}


class MainWindow(tk.Tk):
    def __init__(self, *args, **kwargs):
        tk.Tk.__init__(self, *args, **kwargs)
        self.title('Minter')
        self.geometry('300x300')

        container = tk.Frame(self)
        container.pack(side='top', fill='both', expand=True)
        container.grid_columnconfigure(0, weight=1)

        self.config = load_config()
        self.context = {}
        self.steps = {}
        self._show_frame(container, StartPage)

    def step(self, container):
        self.page += 1
        self._show_frame(container, self.action_steps[self.page])

    def step_back(self, container):
        self.page -= 1
        self._show_frame(container, self.action_steps[self.page])

    def _build_frame(self, container, page):
        frame = page(container, self)
        frame.grid(row=0, column=0, sticky='nsew')
        return frame

    def _show_frame(self, container, page):
        frame = self._build_frame(container, page)
        frame.tkraise()


class StartPage(tk.Frame):
    def __init__(self, container, controller):
        tk.Frame.__init__(self, container)

        controller.page = -1

        tk.Button(self, text='?', font=ICON_FONT, borderwidth=0,
                  command=lambda: self._on_help_click()).pack(anchor="e")

        tk.Label(self, text='What do you want?', cnf=TOP_LABEL).pack()

        tk.Button(self, text='Build Transaction', font=MEDIUM_FONT,
                  command=lambda: self._on_click(container, controller, 'BUILD')).pack(pady=10)

        tk.Button(self, text='Sign Transaction', font=MEDIUM_FONT,
                  command=lambda: self._on_click(container, controller, 'SIGN')).pack(pady=10)

        tk.Button(self, text='Send Transaction', font=MEDIUM_FONT,
                  command=lambda: self._on_click(container, controller, 'SEND')).pack(pady=10)

    def _on_help_click(self):
        messagebox.showinfo("Help", HELP_TEXT)

    def _on_click(self, container, controller, action):
        controller.action_steps = self.steps()[action]
        controller.step(container)

    def steps(self):
        return {
            'BUILD': [OpenWalletPage, BuildTransactionPage, SelectOutputFilePage, StartPage],
            'SIGN': [OpenWalletPage, SelectDidPage, SignTransactionFilePage, SelectOutputFilePage, StartPage],
            'SEND': [SendTransactionPage, StartPage],
        }


class OpenWalletPage(tk.Frame):
    def __init__(self, container, controller):
        tk.Frame.__init__(self, container)
        tk.Label(self, text='Open Wallet', cnf=TOP_LABEL).pack()

        self.name = tk.StringVar(value=container.master.context.get('wallet_name'))
        tk.Label(self, text='Name', font=MEDIUM_FONT).pack(ENTRY_LABEL)
        tk.Entry(self, textvariable=self.name).pack()

        self.key = tk.StringVar()
        tk.Label(self, text='Key', font=MEDIUM_FONT).pack(ENTRY_LABEL)
        tk.Entry(self, textvariable=self.key).pack()

        tk.Button(self, text='Back', font=MEDIUM_FONT,
                  command=lambda: controller.step_back(container)).pack(BACK_BUTTON)

        tk.Button(self, text='Open', font=MEDIUM_FONT,
                  command=lambda: self._on_click(container, controller)).pack(STEP_BUTTON)

    def _on_click(self, container, controller):
        try:
            if container.master.context.get('wallet_handle'):
                close_wallet(container.master.context['wallet_handle'])
            container.master.context['wallet_name'] = self.name.get()
            container.master.context['wallet_handle'] = open_wallet(self.name.get(), self.key.get())
        except Exception as e:
            return messagebox.showerror("Cannot open Wallet", e)

        controller.step(container)


class SelectDidPage(tk.Frame):
    def __init__(self, container, controller):
        tk.Frame.__init__(self, container)
        tk.Label(self, text='Select DID', cnf=TOP_LABEL).pack()

        self.did = tk.StringVar(value=container.master.context.get('did'))
        self.listbox = tk.Listbox(self, height=8, width=24, font=MEDIUM_FONT, listvariable=self.did)
        self.listbox.pack()

        for did_info in get_stored_dids(container.master.context['wallet_handle']):
            if not did_info['did'] in self.listbox.get(0, "end"):
                self.listbox.insert(tk.END, did_info['did'])

        tk.Button(self, text='Back', font=MEDIUM_FONT,
                  command=lambda: controller.step_back(container)).pack(BACK_BUTTON)

        tk.Button(self, text='Select', font=MEDIUM_FONT,
                  command=lambda: self._on_click(container, controller)).pack(STEP_BUTTON)

    def _on_click(self, container, controller):
        if not self.listbox.get(tk.ACTIVE):
            return messagebox.showerror("Error", "Select DID to sign")

        container.master.context['did'] = self.listbox.get(tk.ACTIVE)
        controller.step(container)


class SignTransactionFilePage(tk.Frame):
    def __init__(self, container, controller):
        tk.Frame.__init__(self, container)
        tk.Label(self, text='Sign Transaction', cnf=TOP_LABEL).pack()

        self.input_filename = tk.StringVar()
        tk.Button(self, text='Select Transaction file', font=MEDIUM_FONT,
                  command=lambda: self._select_input_file()).pack(FILE_BUTTON)
        tk.Message(self, textvariable=self.input_filename, font=MEDIUM_FONT, width=260).pack(FILE_LABEL)

        tk.Button(self, text='Back', font=MEDIUM_FONT,
                  command=lambda: controller.step_back(container)).pack(BACK_BUTTON)

        tk.Button(self, text='Sign', font=MEDIUM_FONT,
                  command=lambda: self._on_click(container, controller)).pack(STEP_BUTTON)

    def _select_input_file(self):
        self.input_filename.set(
            filedialog.askopenfilename(initialdir=INITIAL_DIR, title="Select Transaction file"))

    def _on_click(self, container, controller):
        try:
            with open(self.input_filename.get(), "r") as input_filename:
                transaction = input_filename.read()
                container.master.context['transaction'] = sign_transaction(container.master.context['wallet_handle'],
                                                                           container.master.context['did'],
                                                                           transaction)
        except Exception as e:
            return messagebox.showerror("Error", e)

        controller.step(container)


class SelectOutputFilePage(tk.Frame):
    def __init__(self, container, controller):
        tk.Frame.__init__(self, container)
        tk.Label(self, text='Save Transaction', cnf=TOP_LABEL).pack()

        self.output_filename = tk.StringVar()
        tk.Button(self, text='Select Output file', font=MEDIUM_FONT,
                  command=lambda: self._select_output_file()).pack(FILE_BUTTON)
        tk.Message(self, textvariable=self.output_filename, font=MEDIUM_FONT, width=260).pack(FILE_LABEL)

        tk.Button(self, text='Back', font=MEDIUM_FONT,
                  command=lambda: controller.step_back(container)).pack(BACK_BUTTON)

        tk.Button(self, text='Save', font=MEDIUM_FONT,
                  command=lambda: self._on_click(container, controller)).pack(STEP_BUTTON)

    def _select_output_file(self):
        self.output_filename.set(filedialog.asksaveasfilename(initialdir=INITIAL_DIR, title="Select Output File"))

    def _on_click(self, container, controller):
        try:
            with open(self.output_filename.get(), 'w+') as file:
                file.write(container.master.context['transaction'])

            messagebox.showinfo("Success", "Transaction has been saved")
        except Exception as e:
            return messagebox.showerror("Error", e)

        controller.step(container)


class BuildTransactionPage(tk.Frame):
    def __init__(self, container, controller):
        tk.Frame.__init__(self, container)
        tk.Label(self, text='Build Transaction', cnf=TOP_LABEL).pack()

        self.payment_address = tk.StringVar(value=container.master.config['payment_address'])
        tk.Label(self, text='Payment Address', font=MEDIUM_FONT).pack(ENTRY_LABEL)
        tk.Entry(self, textvariable=self.payment_address).pack()

        self.amount = tk.IntVar(value=container.master.config['tokens_amount'])
        tk.Label(self, text='Amount', font=MEDIUM_FONT).pack(ENTRY_LABEL)
        tk.Entry(self, textvariable=self.amount).pack()

        tk.Button(self, text='Back', font=MEDIUM_FONT,
                  command=lambda: controller.step_back(container)).pack(BACK_BUTTON)

        tk.Button(self, text='Build', font=MEDIUM_FONT,
                  command=lambda: self._on_click(container, controller)).pack(STEP_BUTTON)

    def _on_click(self, container, controller):
        try:
            load_plugin()
            (container.master.context['transaction'], _) = \
                build_mint_transaction(container.master.context['wallet_handle'],
                                       self.payment_address.get(), self.amount.get())
        except Exception as e:
            return messagebox.showerror("Cannot build Transaction", e)

        controller.step(container)


class SendTransactionPage(tk.Frame):
    def __init__(self, container, controller):
        tk.Frame.__init__(self, container)
        tk.Label(self, text='Send Transaction', cnf=TOP_LABEL).pack()

        self.input_filename = tk.StringVar()
        tk.Button(self, text='Select Transaction file', font=MEDIUM_FONT,
                  command=lambda: self._select_input_file()).pack(FILE_BUTTON)
        tk.Message(self, textvariable=self.input_filename, font=MEDIUM_FONT, width=260).pack(FILE_LABEL)

        tk.Button(self, text='Back', font=MEDIUM_FONT,
                  command=lambda: controller.step_back(container)).pack(BACK_BUTTON)

        tk.Button(self, text='Send', font=MEDIUM_FONT,
                  command=lambda: self._on_click(container, controller)).pack(STEP_BUTTON)

    def _select_input_file(self):
        self.input_filename.set(filedialog.askopenfilename(initialdir=INITIAL_DIR, title="Select Transaction file"))

    def _on_click(self, container, controller):
        try:
            if not container.master.context.get('pool_handle'):
                container.master.context['pool_handle'] = open_pool(container.master.config)

            with open(self.input_filename.get(), "r") as input_filename:
                self.transaction = input_filename.read()

            send_transaction(container.master.context['pool_handle'], self.transaction)

            messagebox.showinfo("Success", "Transaction has been successfully sent")
        except Exception as e:
            return messagebox.showerror("Error", e)

        controller.step(container)


def clean(self):
    if self.context.get('wallet_handle'):
        close_wallet(self.context['wallet_handle'])
    if self.context.get('pool_handle'):
        close_pool(self.context.get('pool_handle'))


if __name__ == '__main__':
    app = MainWindow()
    app.mainloop()
    clean(app)
