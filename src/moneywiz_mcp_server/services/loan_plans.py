"""Split loan payments into principal and cost using MoneyWiz payment plans.

A MoneyWiz Loan account can have a payment plan (PaymentPlan) that names its
principal and interest categories (ZCATEGORYPRINCIPAL, ZCATEGORYINTEREST)
and lists every payment's amortization (PaymentPlanItem: ZDATE,
ZPRINCIPALAMOUNT1, ZINTERESTAMOUNT). The plan's scheduled transfer is split
across categories (principal, interest, often insurance).

Which split is principal comes only from the plan's principal category,
never from category names. Each month's interest comes from the plan item
due that month when there is one, because a schedule's split amounts are
fixed while the real interest falls as the loan is paid down.
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
import logging

from moneywiz_mcp_server.database.connection import DatabaseManager
from moneywiz_mcp_server.models.scheduled_transaction import CategorySplit
from moneywiz_mcp_server.utils.core_data_time import core_data_timestamp_to_datetime

logger = logging.getLogger(__name__)

ZERO = Decimal("0")
# Report interest drift above this share of the payment (0.1%).
DRIFT_THRESHOLD = Decimal("0.001")


@dataclass(frozen=True)
class PlanItem:
    principal: Decimal
    interest: Decimal


@dataclass
class LoanPlan:
    """A loan's payment plan: its categories and monthly amortization."""

    principal_category: int | None
    interest_category: int | None
    items: dict[tuple[int, int], PlanItem] = field(default_factory=dict)

    def item_for(self, when: datetime) -> PlanItem | None:
        return self.items.get((when.year, when.month))


@dataclass
class LoanPlans:
    by_id: dict[int, LoanPlan] = field(default_factory=dict)
    by_loan_account: dict[str, LoanPlan] = field(default_factory=dict)

    def for_payment(
        self, plan_id: int | None, loan_account_id: str | None
    ) -> LoanPlan | None:
        """The schedule's own plan, else the plan of the loan it pays."""
        if plan_id is not None and plan_id in self.by_id:
            return self.by_id[plan_id]
        return self.by_loan_account.get(loan_account_id or "")


class SplitStatus(StrEnum):
    SPLIT = "split"  # principal split identified by the plan
    PLAN_ONLY = "plan_only"  # no category splits; principal from the plan item
    NO_PRINCIPAL_SPLIT = "no_principal_split"  # splits, none is principal
    UNSPLIT = "unsplit"  # no plan, or nothing to split by


@dataclass(frozen=True)
class OccurrenceSplit:
    status: SplitStatus
    principal: Decimal
    cost: Decimal
    interest_drift: Decimal  # plan interest - scheduled interest split


def split_payment(
    amount: Decimal,
    splits: list[CategorySplit],
    plan: LoanPlan | None,
    when: datetime,
) -> OccurrenceSplit:
    """Split one loan payment of `amount` (positive) made on `when`.

    principal + cost always equals amount. UNSPLIT payments have principal
    and cost of zero: they stay a single debt payment.
    """
    if plan is None:
        return OccurrenceSplit(SplitStatus.UNSPLIT, ZERO, ZERO, ZERO)
    item = plan.item_for(when)

    if not splits:
        if item is None:
            return OccurrenceSplit(SplitStatus.UNSPLIT, ZERO, ZERO, ZERO)
        principal = min(item.principal, amount)
        return OccurrenceSplit(
            SplitStatus.PLAN_ONLY, principal, amount - principal, ZERO
        )

    def share(s: CategorySplit) -> Decimal:
        return abs(s.amount) if s.amount is not None else ZERO

    if not any(s.category_id == plan.principal_category for s in splits):
        return OccurrenceSplit(SplitStatus.NO_PRINCIPAL_SPLIT, ZERO, amount, ZERO)

    scheduled_interest = sum(
        (share(s) for s in splits if s.category_id == plan.interest_category), ZERO
    )
    other_costs = sum(
        (
            share(s)
            for s in splits
            if s.category_id not in (plan.principal_category, plan.interest_category)
        ),
        ZERO,
    )
    interest = item.interest if item is not None else scheduled_interest
    drift = interest - scheduled_interest if item is not None else ZERO
    cost = min(other_costs + interest, amount)
    return OccurrenceSplit(SplitStatus.SPLIT, amount - cost, cost, drift)


def drift_is_material(drift: Decimal, amount: Decimal) -> bool:
    return amount > 0 and abs(drift) > amount * DRIFT_THRESHOLD


async def load_loan_plans(db_manager: DatabaseManager) -> LoanPlans:
    """Every payment plan with its categories and items, read-only."""
    entity_map = await db_manager.get_entity_name_map()
    plan_ent = entity_map.get("PaymentPlan")
    item_ent = entity_map.get("PaymentPlanItem")
    if plan_ent is None or item_ent is None:
        return LoanPlans()
    try:
        plan_rows = await db_manager.execute_query(
            "SELECT Z_PK, ZLOANACCOUNT, ZCATEGORYPRINCIPAL, ZCATEGORYINTEREST "
            "FROM ZSYNCOBJECT WHERE Z_ENT = ?",
            (plan_ent,),
        )
        item_rows = await db_manager.execute_query(
            "SELECT ZPAYMENTPLAN1, ZDATE, ZPRINCIPALAMOUNT1, ZINTERESTAMOUNT "
            "FROM ZSYNCOBJECT WHERE Z_ENT = ? AND ZDATE IS NOT NULL",
            (item_ent,),
        )
    except Exception as e:
        logger.warning(f"Could not read loan payment plans: {e}")
        return LoanPlans()

    plans = LoanPlans()
    for row in plan_rows:
        plan = LoanPlan(
            principal_category=row.get("ZCATEGORYPRINCIPAL"),
            interest_category=row.get("ZCATEGORYINTEREST"),
        )
        plans.by_id[row["Z_PK"]] = plan
        if row.get("ZLOANACCOUNT") is not None:
            plans.by_loan_account[str(row["ZLOANACCOUNT"])] = plan
    for row in item_rows:
        plan = plans.by_id.get(row.get("ZPAYMENTPLAN1"))
        if plan is None:
            continue
        when = core_data_timestamp_to_datetime(row["ZDATE"])
        plan.items[(when.year, when.month)] = PlanItem(
            principal=Decimal(str(row.get("ZPRINCIPALAMOUNT1") or 0)),
            interest=Decimal(str(row.get("ZINTERESTAMOUNT") or 0)),
        )
    return plans
