"""Unit tests for scheduled transaction models."""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from moneywiz_mcp_server.models.currency_types import CurrencyAmounts
from moneywiz_mcp_server.models.scheduled_transaction import (
    CommitmentBreakdown,
    RecurrenceEndCondition,
    RecurrencePattern,
    SalaryBreakdownResponse,
    ScheduledTransactionModel,
    ScheduledTransactionResponse,
    WeekendHandling,
)
from moneywiz_mcp_server.models.transaction import TransactionType


class TestScheduledTransactionModel:
    """Test cases for ScheduledTransactionModel."""

    @pytest.fixture
    def sample_scheduled_transaction(self):
        """Create a sample scheduled transaction for testing."""
        return ScheduledTransactionModel(
            id="123",
            description="Monthly Rent",
            amount=Decimal("1500.00"),
            currency="USD",
            account_id="acc1",
            category="Housing",
            payee="Landlord",
            transaction_type=TransactionType.WITHDRAW,
            recurrence_pattern=RecurrencePattern.MONTHLY,
            recurrence_interval=1,
            next_execution_date=datetime(2024, 8, 1),
            weekend_handling=WeekendHandling.SAME_DAY,
            end_condition=RecurrenceEndCondition.AFTER_OCCURRENCES,
            total_occurrences=12,
            completed_occurrences=3,
            remaining_occurrences=9,
            final_execution_date=datetime(2025, 4, 1),
            upcoming_dates=[
                datetime(2024, 8, 1),
                datetime(2024, 9, 1),
                datetime(2024, 10, 1),
            ],
            is_active=True,
            created_date=datetime(2024, 1, 1),
            last_executed_date=datetime(2024, 7, 1),
            entity_type=32,
            database_id=123,
        )

    def test_model_creation(self, sample_scheduled_transaction):
        """Test that model can be created with valid data."""
        transaction = sample_scheduled_transaction

        assert transaction.id == "123"
        assert transaction.description == "Monthly Rent"
        assert transaction.amount == Decimal("1500.00")
        assert transaction.currency == "USD"
        assert transaction.transaction_type == TransactionType.EXPENSE
        assert transaction.recurrence_pattern == RecurrencePattern.MONTHLY
        assert transaction.end_condition == RecurrenceEndCondition.AFTER_OCCURRENCES
        assert transaction.total_occurrences == 12
        assert transaction.remaining_occurrences == 9
        assert transaction.is_active is True

    def test_will_end_within_period_property(self):
        """Test will_end_within_period property calculation."""
        # Transaction ending soon
        transaction = ScheduledTransactionModel(
            id="123",
            description="Test",
            amount=Decimal("100.00"),
            currency="USD",
            account_id="acc1",
            category="Test",
            payee="Test",
            transaction_type=TransactionType.WITHDRAW,
            recurrence_pattern=RecurrencePattern.MONTHLY,
            next_execution_date=datetime.now(),
            end_condition=RecurrenceEndCondition.AFTER_OCCURRENCES,
            total_occurrences=1,
            completed_occurrences=0,
            remaining_occurrences=1,
            final_execution_date=datetime.now() + timedelta(days=30),  # Within 6 months
            is_active=True,
            created_date=datetime.now(),
            entity_type=32,
            database_id=123,
        )

        assert transaction.will_end_within_period is True

        # Transaction ending later
        transaction.final_execution_date = datetime.now() + timedelta(
            days=365
        )  # Beyond 6 months
        assert transaction.will_end_within_period is False

        # Infinite transaction
        transaction.final_execution_date = None
        assert transaction.will_end_within_period is False

    def test_commitment_type_property(self):
        """Test commitment_type property classification."""
        base_data = {
            "id": "123",
            "description": "Test",
            "amount": Decimal("100.00"),
            "currency": "USD",
            "account_id": "acc1",
            "category": "Test",
            "payee": "Test",
            "transaction_type": TransactionType.EXPENSE,
            "recurrence_pattern": RecurrencePattern.MONTHLY,
            "next_execution_date": datetime.now(),
            "completed_occurrences": 0,
            "is_active": True,
            "created_date": datetime.now(),
            "entity_type": 32,
            "database_id": 123,
        }

        # Infinite commitment
        transaction = ScheduledTransactionModel(
            **base_data,
            end_condition=RecurrenceEndCondition.NEVER,
            total_occurrences=None,
            remaining_occurrences=None,
            final_execution_date=None,
        )
        assert transaction.commitment_type == "infinite"

        # Ending soon commitment (3 or fewer payments)
        transaction = ScheduledTransactionModel(
            **base_data,
            end_condition=RecurrenceEndCondition.AFTER_OCCURRENCES,
            total_occurrences=5,
            remaining_occurrences=2,  # 2 <= 3
            final_execution_date=datetime.now() + timedelta(days=60),
        )
        assert transaction.commitment_type == "ending_soon"

        # Finite commitment (more than 3 payments)
        transaction = ScheduledTransactionModel(
            **base_data,
            end_condition=RecurrenceEndCondition.AFTER_OCCURRENCES,
            total_occurrences=10,
            remaining_occurrences=5,  # 5 > 3
            final_execution_date=datetime.now() + timedelta(days=150),
        )
        assert transaction.commitment_type == "finite"

    def test_urgency_level_property(self):
        """Test urgency_level property calculation."""
        base_data = {
            "id": "123",
            "description": "Test",
            "amount": Decimal("100.00"),
            "currency": "USD",
            "account_id": "acc1",
            "category": "Test",
            "payee": "Test",
            "transaction_type": TransactionType.EXPENSE,
            "recurrence_pattern": RecurrencePattern.MONTHLY,
            "end_condition": RecurrenceEndCondition.AFTER_OCCURRENCES,
            "total_occurrences": 5,
            "completed_occurrences": 0,
            "remaining_occurrences": 5,
            "is_active": True,
            "created_date": datetime.now(),
            "entity_type": 32,
            "database_id": 123,
        }

        transaction = ScheduledTransactionModel(
            **base_data,
            next_execution_date=datetime.now() + timedelta(days=1),
        )
        assert transaction.urgency_level == "immediate"

        # Urgent (within a week)
        transaction = ScheduledTransactionModel(
            **base_data,
            next_execution_date=datetime.now() + timedelta(days=5),
        )
        assert transaction.urgency_level == "urgent"

        # Regular (within a month)
        transaction = ScheduledTransactionModel(
            **base_data,
            next_execution_date=datetime.now() + timedelta(days=15),
        )
        assert transaction.urgency_level == "regular"

        # Future (more than a month)
        transaction = ScheduledTransactionModel(
            **base_data,
            next_execution_date=datetime.now() + timedelta(days=45),
        )
        assert transaction.urgency_level == "future"

        # Inactive (no next execution date)
        transaction = ScheduledTransactionModel(
            **base_data,
            next_execution_date=None,
        )
        # This would cause an error in current implementation, showing a bug
        # Let's test the behavior if next_execution_date is None


class TestCommitmentBreakdown:
    """Test cases for CommitmentBreakdown model."""

    def test_commitment_breakdown_creation(self):
        """Test CommitmentBreakdown model creation."""
        commitment = CommitmentBreakdown(
            description="Car Payment",
            amount=Decimal("350.00"),
            currency="USD",
            category="Auto",
            next_date=datetime(2024, 8, 15),
            remaining_payments=24,
            final_payment_date=datetime(2026, 8, 15),
            payments_in_period=3,
            total_impact_in_period=Decimal("1050.00"),
            commitment_type="finite",
            urgency_level="regular",
        )

        assert commitment.description == "Car Payment"
        assert commitment.amount == Decimal("350.00")
        assert commitment.currency == "USD"
        assert commitment.remaining_payments == 24
        assert commitment.payments_in_period == 3
        assert commitment.total_impact_in_period == Decimal("1050.00")
        assert commitment.commitment_type == "finite"
        assert commitment.urgency_level == "regular"

    def test_commitment_breakdown_infinite(self):
        """Test CommitmentBreakdown with infinite payments."""
        commitment = CommitmentBreakdown(
            description="Rent",
            amount=Decimal("1500.00"),
            currency="USD",
            category="Housing",
            next_date=datetime(2024, 8, 1),
            remaining_payments=None,  # Infinite
            final_payment_date=None,  # No end date
            payments_in_period=1,
            total_impact_in_period=Decimal("1500.00"),
            commitment_type="infinite",
            urgency_level="urgent",
        )

        assert commitment.remaining_payments is None
        assert commitment.final_payment_date is None
        assert commitment.commitment_type == "infinite"


class TestScheduledTransactionResponse:
    """Test cases for ScheduledTransactionResponse model."""

    def test_response_model_creation(self):
        """Test ScheduledTransactionResponse creation."""
        response = ScheduledTransactionResponse(
            id="123",
            description="Monthly Subscription",
            amount=29.99,
            currency="USD",
            category="Entertainment",
            payee="Netflix",
            account_id="acc1",
            recurrence_pattern="monthly",
            next_execution_date="2024-08-01T00:00:00",
            transaction_type="expense",
            end_condition="after_occurrences",
            total_occurrences=12,
            completed_occurrences=6,
            remaining_occurrences=6,
            final_execution_date="2025-02-01T00:00:00",
            is_active=True,
            commitment_type="finite",
            urgency_level="regular",
        )

        assert response.id == "123"
        assert response.amount == 29.99
        assert response.recurrence_pattern == "monthly"
        assert response.total_occurrences == 12
        assert response.remaining_occurrences == 6
        assert response.commitment_type == "finite"


class TestSalaryBreakdownResponse:
    """Test cases for SalaryBreakdownResponse model."""

    def test_salary_breakdown_response_creation(self):
        """Test SalaryBreakdownResponse creation."""
        salary_amounts = CurrencyAmounts({"USD": Decimal("5000.00")})
        commitment_amounts = CurrencyAmounts({"USD": Decimal("3500.00")})
        remaining_amounts = CurrencyAmounts({"USD": Decimal("1500.00")})

        commitment = CommitmentBreakdown(
            description="Rent",
            amount=Decimal("1500.00"),
            currency="USD",
            category="Housing",
            next_date=datetime(2024, 8, 1),
            remaining_payments=None,
            final_payment_date=None,
            payments_in_period=1,
            total_impact_in_period=Decimal("1500.00"),
            commitment_type="infinite",
            urgency_level="urgent",
        )

        response = SalaryBreakdownResponse(
            salary_amount=salary_amounts,
            period_start="2024-08-01T00:00:00",
            period_end="2024-11-01T00:00:00",
            next_salary_date="2024-08-01T00:00:00",
            total_commitments_in_period=commitment_amounts,
            finite_commitments=[],
            infinite_commitments=[commitment],
            ending_soon_commitments=[],
            remaining_after_commitments=remaining_amounts,
            coverage_analysis="sufficient",
            commitment_end_analysis="No finite commitments found.",
            recommendations=["Your budget looks healthy!"],
            currencies_found=["USD"],
            primary_currency="USD",
        )

        assert response.salary_amount["USD"] == Decimal("5000.00")
        assert response.total_commitments_in_period["USD"] == Decimal("3500.00")
        assert response.remaining_after_commitments["USD"] == Decimal("1500.00")
        assert response.coverage_analysis == "sufficient"
        assert len(response.infinite_commitments) == 1
        assert response.infinite_commitments[0].description == "Rent"
        assert response.primary_currency == "USD"


class TestRecurrenceEnums:
    """Test cases for recurrence-related enums."""

    def test_recurrence_pattern_enum(self):
        """Test RecurrencePattern enum values."""
        assert RecurrencePattern.DAILY == "daily"
        assert RecurrencePattern.WEEKLY == "weekly"
        assert RecurrencePattern.MONTHLY == "monthly"
        assert RecurrencePattern.YEARLY == "yearly"

    def test_recurrence_end_condition_enum(self):
        """Test RecurrenceEndCondition enum values."""
        assert RecurrenceEndCondition.NEVER == "never"
        assert RecurrenceEndCondition.AFTER_OCCURRENCES == "after_occurrences"
        assert RecurrenceEndCondition.ON_DATE == "on_date"

    def test_weekend_handling_enum(self):
        """Test WeekendHandling enum values."""
        assert WeekendHandling.SAME_DAY == "same_day"
        assert WeekendHandling.NEXT_WEEKDAY == "next_weekday"
        assert WeekendHandling.PREVIOUS_WEEKDAY == "previous_weekday"


class TestModelValidation:
    """Test model validation and edge cases."""

    def test_required_fields_validation(self):
        """Test that required fields are properly validated."""
        with pytest.raises(ValueError):
            # Missing required fields should raise validation error
            ScheduledTransactionModel()

    def test_decimal_precision(self):
        """Test that decimal amounts maintain precision."""
        transaction = ScheduledTransactionModel(
            id="123",
            description="Test",
            amount=Decimal("123.456789"),  # High precision
            currency="USD",
            account_id="acc1",
            category="Test",
            payee="Test",
            transaction_type=TransactionType.WITHDRAW,
            recurrence_pattern=RecurrencePattern.MONTHLY,
            next_execution_date=datetime.now(),
            end_condition=RecurrenceEndCondition.NEVER,
            completed_occurrences=0,
            is_active=True,
            created_date=datetime.now(),
            entity_type=32,
            database_id=123,
        )

        # Decimal should maintain precision
        assert transaction.amount == Decimal("123.456789")
        assert isinstance(transaction.amount, Decimal)

    def test_date_handling(self):
        """Test that datetime fields are properly handled."""
        now = datetime.now()
        future_date = now + timedelta(days=30)

        transaction = ScheduledTransactionModel(
            id="123",
            description="Test",
            amount=Decimal("100.00"),
            currency="USD",
            account_id="acc1",
            category="Test",
            payee="Test",
            transaction_type=TransactionType.WITHDRAW,
            recurrence_pattern=RecurrencePattern.MONTHLY,
            next_execution_date=future_date,
            end_condition=RecurrenceEndCondition.ON_DATE,
            completed_occurrences=0,
            final_execution_date=future_date,
            is_active=True,
            created_date=now,
            entity_type=32,
            database_id=123,
        )

        assert isinstance(transaction.next_execution_date, datetime)
        assert isinstance(transaction.final_execution_date, datetime)
        assert isinstance(transaction.created_date, datetime)
        assert transaction.next_execution_date > transaction.created_date
