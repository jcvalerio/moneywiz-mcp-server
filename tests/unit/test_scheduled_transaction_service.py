"""Unit tests for ScheduledTransactionService."""

from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from moneywiz_mcp_server.database.connection import DatabaseManager
from moneywiz_mcp_server.models.scheduled_transaction import (
    RecurrenceEndCondition,
    RecurrencePattern,
    ScheduledTransactionModel,
    TransactionType,
)
from moneywiz_mcp_server.services.scheduled_transaction_service import (
    ScheduledTransactionService,
)


@pytest.fixture
def mock_db_manager():
    """Create a mock database manager."""
    db_manager = MagicMock(spec=DatabaseManager)
    db_manager.execute_query = AsyncMock()
    return db_manager


@pytest.fixture
def scheduled_service(mock_db_manager):
    """Create a ScheduledTransactionService with mock database."""
    return ScheduledTransactionService(mock_db_manager)


@pytest.fixture
def sample_database_record():
    """Sample database record for scheduled transaction."""
    return {
        "Z_PK": 123,
        "Z_ENT": 34,
        "ZAMOUNT": -500.00,
        "ZDESC1": "Rent Payment",
        "ZEXECUTEDATE": 741744000.0,  # Core Data timestamp
        "ZACCOUNT1": "1",
        "ZPAYEE1": 10,
        "ZCURRENCYNAME3": "USD",
        "ZDURATION1": 1,
        "ZDURATIONUNITS1": 8,  # Monthly
        "ZEXECUTESCOUNT": 3,
        "ZDISABLEEXECUTION": 0,
        "ZISREPEATABLE1": 1,
        "ZCREATIONDATE1": 700000000.0,
    }


class TestScheduledTransactionService:
    """Test cases for ScheduledTransactionService."""

    @pytest.mark.asyncio
    async def test_get_scheduled_transactions_empty_result(
        self, scheduled_service, mock_db_manager
    ):
        """Test getting scheduled transactions when none exist."""
        # Mock empty results for all entity types
        mock_db_manager.execute_query.return_value = []

        result = await scheduled_service.get_scheduled_transactions()

        assert result == []
        assert (
            mock_db_manager.execute_query.call_count > 0
        )  # Called for multiple entity types

    @pytest.mark.asyncio
    async def test_get_scheduled_transactions_with_data(
        self, scheduled_service, mock_db_manager, sample_database_record
    ):
        """Test getting scheduled transactions with sample data."""

        # Mock database responses - service queries for entities 33 and 34
        def mock_execute_query(query, params):
            if "ZISREPEATABLE1 = 1" in query and params[0] == 34:
                return [sample_database_record]
            elif "Z_ENT = 28" in query:  # Payee lookup
                return [{"ZNAME": "Landlord"}]
            else:
                return []

        mock_db_manager.execute_query.side_effect = mock_execute_query

        result = await scheduled_service.get_scheduled_transactions()

        assert len(result) == 1
        transaction = result[0]
        assert isinstance(transaction, ScheduledTransactionModel)
        assert transaction.id == "123"
        assert transaction.description == "Rent Payment"
        assert transaction.amount == Decimal("-500.0")
        assert transaction.currency == "USD"
        assert transaction.category == "Bills & Utilities"
        assert transaction.payee == "Landlord"
        assert transaction.transaction_type == TransactionType.WITHDRAW
        assert transaction.completed_occurrences == 3
        assert transaction.end_condition == RecurrenceEndCondition.NEVER

    @pytest.mark.asyncio
    async def test_calculate_salary_breakdown(
        self, scheduled_service, mock_db_manager, sample_database_record
    ):
        """Test salary breakdown calculation."""

        # Return empty results so service runs without DB errors
        mock_db_manager.execute_query.return_value = []

        # Test salary breakdown
        next_salary_date = datetime.now() + timedelta(days=5)
        salary_amount = Decimal("5000.00")

        result = await scheduled_service.calculate_salary_breakdown(
            next_salary_date=next_salary_date,
            salary_amount=salary_amount,
            planning_horizon_months=3,
        )

        assert "salary_amount" in result
        assert "total_commitments_in_period" in result
        assert "finite_commitments" in result
        assert "infinite_commitments" in result
        assert "ending_soon_commitments" in result
        assert "remaining_after_commitments" in result
        assert "coverage_analysis" in result
        assert "recommendations" in result

        # Check that salary amount is properly set
        assert result["salary_amount"]["USD"] == salary_amount

    def test_core_data_timestamp_conversion(self, scheduled_service):
        """Test Core Data timestamp to datetime conversion."""
        # Core Data timestamp for a known date
        timestamp = 741744000.0  # This is approximately July 2024

        result = scheduled_service._core_data_timestamp_to_datetime(timestamp)

        assert isinstance(result, datetime)
        assert (
            result.year >= 2024
        )  # Should be in the future relative to Core Data epoch

    def test_infer_recurrence_pattern(self, scheduled_service):
        """Test recurrence pattern inference from database record."""
        # Test monthly pattern (ZDURATIONUNITS1 = 8)
        record = {"ZDURATIONUNITS1": 8, "ZDURATION1": 1}
        result = scheduled_service._infer_recurrence_pattern_from_duration(record)
        assert result == RecurrencePattern.MONTHLY

        # Test weekly pattern (ZDURATIONUNITS1 = 2)
        record = {"ZDURATIONUNITS1": 2, "ZDURATION1": 1}
        result = scheduled_service._infer_recurrence_pattern_from_duration(record)
        assert result == RecurrencePattern.WEEKLY

        # Test daily pattern (ZDURATIONUNITS1 = 1)
        record = {"ZDURATIONUNITS1": 1, "ZDURATION1": 1}
        result = scheduled_service._infer_recurrence_pattern_from_duration(record)
        assert result == RecurrencePattern.DAILY

        # Test yearly pattern (ZDURATIONUNITS1 = 4)
        record = {"ZDURATIONUNITS1": 4, "ZDURATION1": 1}
        result = scheduled_service._infer_recurrence_pattern_from_duration(record)
        assert result == RecurrencePattern.YEARLY

    def test_infer_transaction_type(self, scheduled_service):
        """Test transaction type inference from amount."""
        # Negative amount should be withdraw
        result = scheduled_service._infer_transaction_type(-500.0)
        assert result == TransactionType.WITHDRAW

        # Positive amount should be deposit
        result = scheduled_service._infer_transaction_type(1000.0)
        assert result == TransactionType.DEPOSIT

    @pytest.mark.asyncio
    async def test_generate_upcoming_dates_monthly(self, scheduled_service):
        """Test generating upcoming dates for monthly recurrence."""
        next_date = datetime(2024, 7, 15)
        pattern = RecurrencePattern.MONTHLY
        remaining_occurrences = 5

        result = await scheduled_service._generate_upcoming_dates(
            next_date, pattern, remaining_occurrences
        )

        assert len(result) == 5
        assert result[0] == datetime(2024, 7, 15)
        assert result[1] == datetime(2024, 8, 15)
        assert result[2] == datetime(2024, 9, 15)
        assert result[3] == datetime(2024, 10, 15)
        assert result[4] == datetime(2024, 11, 15)

    @pytest.mark.asyncio
    async def test_generate_upcoming_dates_weekly(self, scheduled_service):
        """Test generating upcoming dates for weekly recurrence."""
        next_date = datetime(2024, 7, 15)  # Monday
        pattern = RecurrencePattern.WEEKLY
        remaining_occurrences = 3

        result = await scheduled_service._generate_upcoming_dates(
            next_date, pattern, remaining_occurrences
        )

        assert len(result) == 3
        assert result[0] == datetime(2024, 7, 15)
        assert result[1] == datetime(2024, 7, 22)
        assert result[2] == datetime(2024, 7, 29)

    @pytest.mark.asyncio
    async def test_generate_upcoming_dates_infinite(self, scheduled_service):
        """Test generating upcoming dates for infinite recurrence."""
        next_date = datetime(2024, 7, 15)
        pattern = RecurrencePattern.MONTHLY
        remaining_occurrences = None  # Infinite

        result = await scheduled_service._generate_upcoming_dates(
            next_date, pattern, remaining_occurrences, months_ahead=2
        )

        # Should generate dates for 2 months ahead
        assert len(result) > 0
        assert len(result) <= 20  # Limited by max_dates in implementation

    @pytest.mark.asyncio
    async def test_filters_application(self, scheduled_service):
        """Test that filters are properly applied."""
        # Create a sample transaction
        transaction = ScheduledTransactionModel(
            id="123",
            description="Test Transaction",
            amount=Decimal("100.00"),
            currency="USD",
            account_id="acc1",
            category="Food",
            payee="Store",
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

        # Test account filter match
        result = await scheduled_service._matches_filters(
            transaction, account_ids=["acc1"], categories=None, commitment_types=None
        )
        assert result is True

        # Test account filter no match
        result = await scheduled_service._matches_filters(
            transaction, account_ids=["acc2"], categories=None, commitment_types=None
        )
        assert result is False

        # Test category filter match
        result = await scheduled_service._matches_filters(
            transaction, account_ids=None, categories=["Food"], commitment_types=None
        )
        assert result is True

        # Test category filter no match
        result = await scheduled_service._matches_filters(
            transaction,
            account_ids=None,
            categories=["Transport"],
            commitment_types=None,
        )
        assert result is False

        # Test commitment type filter
        result = await scheduled_service._matches_filters(
            transaction,
            account_ids=None,
            categories=None,
            commitment_types=["infinite"],
        )
        assert (
            result is True
        )  # Transaction has end_condition=NEVER, so commitment_type="infinite"

    def test_generate_salary_recommendations(self, scheduled_service):
        """Test salary recommendation generation."""
        from moneywiz_mcp_server.models.scheduled_transaction import CommitmentBreakdown

        # Create sample commitments
        ending_soon = [
            CommitmentBreakdown(
                description="Phone Payment",
                amount=Decimal("50.00"),
                currency="USD",
                category="Bills",
                next_date=datetime.now(),
                remaining_payments=2,
                final_payment_date=datetime.now() + timedelta(days=60),
                payments_in_period=2,
                total_impact_in_period=Decimal("100.00"),
                commitment_type="ending_soon",
                urgency_level="regular",
            )
        ]

        finite = [
            CommitmentBreakdown(
                description="Car Loan",
                amount=Decimal("300.00"),
                currency="USD",
                category="Auto",
                next_date=datetime.now(),
                remaining_payments=24,
                final_payment_date=datetime.now() + timedelta(days=720),
                payments_in_period=3,
                total_impact_in_period=Decimal("900.00"),
                commitment_type="finite",
                urgency_level="regular",
            )
        ]

        # Test insufficient coverage
        recommendations = scheduled_service._generate_salary_recommendations(
            "insufficient", ending_soon, finite
        )
        assert any("exceed your salary" in rec for rec in recommendations)

        # Test tight coverage
        recommendations = scheduled_service._generate_salary_recommendations(
            "tight", ending_soon, finite
        )
        assert any("budget is tight" in rec for rec in recommendations)

        # Test with ending soon commitments
        recommendations = scheduled_service._generate_salary_recommendations(
            "sufficient", ending_soon, finite
        )
        assert any("ending soon will free up" in rec for rec in recommendations)
        assert any("finite commitments will end" in rec for rec in recommendations)

    def test_analyze_commitment_endings(self, scheduled_service):
        """Test commitment ending analysis."""
        from moneywiz_mcp_server.models.scheduled_transaction import CommitmentBreakdown

        # Create commitments with different ending dates
        commitments = [
            CommitmentBreakdown(
                description="This Year",
                amount=Decimal("100.00"),
                currency="USD",
                category="Bills",
                next_date=datetime.now(),
                remaining_payments=6,
                final_payment_date=datetime(datetime.now().year, 12, 31),
                payments_in_period=6,
                total_impact_in_period=Decimal("600.00"),
                commitment_type="finite",
                urgency_level="regular",
            ),
            CommitmentBreakdown(
                description="Next Year",
                amount=Decimal("200.00"),
                currency="USD",
                category="Auto",
                next_date=datetime.now(),
                remaining_payments=18,
                final_payment_date=datetime(datetime.now().year + 1, 6, 30),
                payments_in_period=3,
                total_impact_in_period=Decimal("600.00"),
                commitment_type="finite",
                urgency_level="regular",
            ),
        ]

        result = scheduled_service._analyze_commitment_endings(commitments)

        assert "ending this year" in result
        assert "ending later" in result

        # Test with no commitments
        result = scheduled_service._analyze_commitment_endings([])
        assert result == "No finite commitments found."
