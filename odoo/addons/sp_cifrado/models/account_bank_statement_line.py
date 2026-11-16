from odoo import models

from .campo import CharCifrado


class AccountBankStatementLine(models.Model):
    _inherit = "account.bank.statement.line"

    account_number = CharCifrado(string="Bank Account Number")
