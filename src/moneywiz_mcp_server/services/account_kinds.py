"""Classify scheduled transfers by the TYPE of the accounts they connect.

Only MoneyWiz's account entity type is used, never account or group names:
a user-chosen label is not evidence of what an account is. A transfer whose
accounts don't fit a rule is reported as unclassified so the user can fix
the account type in MoneyWiz, instead of being guessed.

Rules (source -> destination):

    bank/savings/cash -> Loan            debt_payment  (an obligation)
    bank/savings/cash -> CreditCard      card_payment  (pays expenses already
                                                        recorded on the card)
    bank/savings/cash -> Investment/Forex savings
    bank/savings/cash -> bank/savings/cash internal
    Investment/Forex  -> bank/savings/cash internal
    Investment/Forex  -> Investment/Forex internal
    CreditCard/Loan   -> anything        non_cash      (no money leaves a bank
                                                        account, e.g. a card
                                                        charge moved to a payable)
    anything else                        unclassified
"""

from enum import StrEnum


class AccountKind(StrEnum):
    LIQUID = "liquid"
    CREDIT_CARD = "credit_card"
    LOAN = "loan"
    INVESTMENT = "investment"


ACCOUNT_KIND_BY_ENTITY: dict[str, AccountKind] = {
    "BankChequeAccount": AccountKind.LIQUID,
    "BankSavingAccount": AccountKind.LIQUID,
    "CashAccount": AccountKind.LIQUID,
    "CreditCardAccount": AccountKind.CREDIT_CARD,
    "LoanAccount": AccountKind.LOAN,
    "InvestmentAccount": AccountKind.INVESTMENT,
    "ForexAccount": AccountKind.INVESTMENT,
}


class TransferKind(StrEnum):
    DEBT_PAYMENT = "debt_payment"
    CARD_PAYMENT = "card_payment"
    SAVINGS = "savings"
    INTERNAL = "internal"
    NON_CASH = "non_cash"
    UNCLASSIFIED = "unclassified"


_FROM_LIQUID: dict[AccountKind, TransferKind] = {
    AccountKind.LOAN: TransferKind.DEBT_PAYMENT,
    AccountKind.CREDIT_CARD: TransferKind.CARD_PAYMENT,
    AccountKind.INVESTMENT: TransferKind.SAVINGS,
    AccountKind.LIQUID: TransferKind.INTERNAL,
}


def classify_transfer(
    source: AccountKind | None, destination: AccountKind | None
) -> TransferKind:
    """Kind of a transfer from its source and destination account kinds."""
    if source is None or destination is None:
        return TransferKind.UNCLASSIFIED
    if source in (AccountKind.CREDIT_CARD, AccountKind.LOAN):
        return TransferKind.NON_CASH
    if source is AccountKind.LIQUID:
        return _FROM_LIQUID[destination]
    if destination in (AccountKind.LIQUID, AccountKind.INVESTMENT):
        return TransferKind.INTERNAL  # source is an investment
    return TransferKind.UNCLASSIFIED
