"""Currency types for type-safe financial operations with Decimal precision."""

from collections.abc import Iterator
from decimal import Decimal
from typing import Any

from pydantic import GetCoreSchemaHandler
from pydantic_core import core_schema


class CurrencyAmounts:
    """Type-safe container for currency amounts using Decimal precision.

    This class provides a consistent way to handle multi-currency amounts
    throughout the financial system, ensuring decimal precision and providing
    utility methods for common currency operations.
    """

    def __init__(
        self,
        amounts: dict[str, Decimal] | dict[str, float] | dict[str, int] | None = None,
    ):
        """Initialize with currency → amount mapping.

        Args:
            amounts: Dictionary mapping currency codes to amounts.
                    All values are converted to Decimal for precision.
        """
        if amounts is None:
            amounts = {}

        # Convert all amounts to Decimal for consistent precision
        self._amounts: dict[str, Decimal] = {}
        for currency, amount in amounts.items():
            if not currency or not isinstance(currency, str):
                raise ValueError(f"Invalid currency code: {currency}")
            self._amounts[currency.upper()] = Decimal(str(amount))

    def to_json_dict(self) -> dict[str, float]:
        """Convert to JSON-serializable dict.

        This is the ONLY place where Decimal → float conversion should happen.

        Returns:
            Dictionary with currency codes as keys and float amounts as values.
        """
        return {currency: float(amount) for currency, amount in self._amounts.items()}

    def primary_currency(self) -> str:
        """Get currency with highest total absolute amount.

        Returns:
            Currency code with the highest activity (income + expenses).
            Returns "USD" as default if no currencies present.
        """
        if not self._amounts:
            return "USD"

        return max(self._amounts.keys(), key=lambda c: abs(self._amounts[c]))

    def currencies(self) -> list[str]:
        """Get sorted list of all currencies.

        Returns:
            Alphabetically sorted list of currency codes.
        """
        return sorted(self._amounts.keys())

    def get(self, currency: str, default: Decimal | None = None) -> Decimal:
        """Get amount for specific currency.

        Args:
            currency: Currency code to lookup
            default: Default value if currency not found (defaults to Decimal('0'))

        Returns:
            Amount for the specified currency or default value.
        """
        if default is None:
            default = Decimal("0")
        return self._amounts.get(currency.upper(), default)

    def total_activity(self) -> Decimal:
        """Sum of absolute values of all amounts.

        Useful for determining which currency has the most activity.

        Returns:
            Sum of absolute values of all currency amounts.
        """
        return sum((abs(amount) for amount in self._amounts.values()), Decimal("0"))

    def __add__(self, other: "CurrencyAmounts") -> "CurrencyAmounts":
        """Add amounts by currency.

        Args:
            other: Another CurrencyAmounts instance to add

        Returns:
            New CurrencyAmounts with amounts added by currency.
        """
        if not isinstance(other, CurrencyAmounts):
            raise TypeError(f"Cannot add CurrencyAmounts with {type(other)}")

        result = {}
        all_currencies = set(self._amounts.keys()) | set(other._amounts.keys())

        for currency in all_currencies:
            self_amount = self._amounts.get(currency, Decimal("0"))
            other_amount = other._amounts.get(currency, Decimal("0"))
            result[currency] = self_amount + other_amount

        return CurrencyAmounts(result)

    def __sub__(self, other: "CurrencyAmounts") -> "CurrencyAmounts":
        """Subtract amounts by currency.

        Args:
            other: Another CurrencyAmounts instance to subtract

        Returns:
            New CurrencyAmounts with amounts subtracted by currency.
        """
        if not isinstance(other, CurrencyAmounts):
            raise TypeError(f"Cannot subtract {type(other)} from CurrencyAmounts")

        result = {}
        all_currencies = set(self._amounts.keys()) | set(other._amounts.keys())

        for currency in all_currencies:
            self_amount = self._amounts.get(currency, Decimal("0"))
            other_amount = other._amounts.get(currency, Decimal("0"))
            result[currency] = self_amount - other_amount

        return CurrencyAmounts(result)

    def calculate_rates(self, base: "CurrencyAmounts") -> dict[str, Decimal]:
        """Calculate percentage rates against base amounts.

        Args:
            base: Base amounts to calculate rates against (e.g., total income)

        Returns:
            Dictionary mapping currency codes to percentage rates as Decimal.
        """
        if not isinstance(base, CurrencyAmounts):
            raise TypeError(f"Base must be CurrencyAmounts, got {type(base)}")

        rates = {}
        all_currencies = set(self._amounts.keys()) | set(base._amounts.keys())

        for currency in all_currencies:
            self_amount = self._amounts.get(currency, Decimal("0"))
            base_amount = base._amounts.get(currency, Decimal("0"))

            if base_amount > 0:
                rates[currency] = (self_amount / base_amount) * Decimal("100")
            else:
                rates[currency] = Decimal("0")

        return rates

    def __iter__(self) -> Iterator[tuple[str, Decimal]]:
        """Iterate over (currency, amount) pairs.

        Yields:
            Tuples of (currency_code, amount) in alphabetical order by currency.
        """
        for currency in sorted(self._amounts.keys()):
            yield currency, self._amounts[currency]

    def items(self) -> Iterator[tuple[str, Decimal]]:
        """Dict-like items() method.

        Yields:
            Tuples of (currency_code, amount) in alphabetical order by currency.
        """
        return self.__iter__()

    def __bool__(self) -> bool:
        """Check if any amounts are present.

        Returns:
            True if there are any currency amounts, False otherwise.
        """
        return bool(self._amounts)

    def __len__(self) -> int:
        """Get number of currencies.

        Returns:
            Number of different currencies in this container.
        """
        return len(self._amounts)

    def __eq__(self, other: object) -> bool:
        """Check equality with another CurrencyAmounts.

        Args:
            other: Object to compare with

        Returns:
            True if both contain the same currency amounts.
        """
        if not isinstance(other, CurrencyAmounts):
            return False
        return self._amounts == other._amounts

    def __repr__(self) -> str:
        """String representation for debugging.

        Returns:
            String representation showing all currency amounts.
        """
        amounts_str = ", ".join(
            f"{currency}: {amount}" for currency, amount in self.items()
        )
        return f"CurrencyAmounts({{{amounts_str}}})"

    def __hash__(self) -> int:
        """Hash based on the frozen dictionary of amounts.

        Returns:
            Hash value based on sorted currency-amount pairs.
        """
        return hash(tuple(sorted(self._amounts.items())))

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source_type: Any,
        handler: GetCoreSchemaHandler,
    ) -> core_schema.CoreSchema:
        """Pydantic core schema for CurrencyAmounts validation and serialization."""

        def validate_currency_amounts(
            value: Any, info: Any = None
        ) -> "CurrencyAmounts":
            """Validate and convert input to CurrencyAmounts."""
            if isinstance(value, CurrencyAmounts):
                return value
            if isinstance(value, dict):
                return CurrencyAmounts(value)
            raise ValueError(f"Cannot convert {type(value)} to CurrencyAmounts")

        # Use a simple validator with no-op serializer since we have field_serializer in base class
        return core_schema.with_info_plain_validator_function(validate_currency_amounts)
