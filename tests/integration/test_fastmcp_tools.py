"""Integration tests for FastMCP tools - Test Phase 3 advanced analytics tools."""

from unittest.mock import AsyncMock, patch

import pytest

from moneywiz_mcp_server.main import (
    analyze_category_trends,
    analyze_income_expense_trends,
    analyze_spending_trends,
    get_savings_recommendations,
    mcp,
)


@pytest.mark.integration
class TestFastMCPToolsIntegration:
    """Test suite for FastMCP tools integration."""

    @pytest.fixture
    def mock_config(self):
        """Mock configuration for testing."""
        from moneywiz_mcp_server.config import Config

        config = Config(
            database_path="/path/to/test.db",
            read_only=True,
            log_level="INFO",
            cache_ttl=300,
            max_results=1000,
        )
        return config

    @pytest.fixture
    def _setup_mcp_config(self, mock_config):
        """Setup MCP server with test configuration."""
        mcp._config = mock_config
        yield
        # Cleanup
        if hasattr(mcp, "_config"):
            delattr(mcp, "_config")

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_setup_mcp_config")
    async def test_get_savings_recommendations_tool(self):
        """Test get_savings_recommendations FastMCP tool."""
        # Mock database manager and services
        with patch("moneywiz_mcp_server.main.get_db_manager") as mock_get_db:
            mock_db = AsyncMock()
            mock_get_db.return_value = mock_db

            # Mock SavingsService
            mock_savings_data = {
                "current_state": {
                    "savings_rate": 15.0,
                    "monthly_savings": 750.0,
                    "total_income": 5000.0,
                    "total_expenses": 4250.0,
                },
                "target_state": {
                    "target_savings_rate": 20.0,
                    "projected_savings_rate": 18.0,
                    "potential_monthly_savings": 200.0,
                    "needed_expense_reduction": 250.0,
                },
                "recommendations": [
                    {
                        "type": "category_reduction",
                        "priority": "high",
                        "title": "Reduce Dining Out Spending",
                        "description": "Consider reducing dining out expenses by 25%",
                        "impact": "$150/month",
                        "difficulty": "medium",
                    }
                ],
                "insights": {
                    "fixed_vs_variable": {"fixed_percentage": 60.0},
                    "spending_patterns": {"patterns_detected": ["weekend_spike"]},
                    "category_analysis": {"concentration": {"is_concentrated": False}},
                },
            }

            with patch("moneywiz_mcp_server.main.SavingsService") as mock_service_class:
                mock_service = AsyncMock()
                mock_service.get_savings_recommendations.return_value = (
                    mock_savings_data
                )
                mock_service_class.return_value = mock_service

                # Act
                result = await get_savings_recommendations(
                    time_period="last 3 months", target_savings_rate=20.0
                )

            # Assert
            assert result.current_state.savings_rate == 15.0
            assert result.target_state.target_savings_rate == 20.0
            assert len(result.recommendations) > 0
            assert result.recommendations[0].type == "category_reduction"

            # Verify database connection was managed
            mock_db.close.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_setup_mcp_config")
    async def test_analyze_spending_trends_tool(self):
        """Test analyze_spending_trends FastMCP tool."""
        with patch("moneywiz_mcp_server.main.get_db_manager") as mock_get_db:
            mock_db = AsyncMock()
            mock_get_db.return_value = mock_db

            mock_trend_data = {
                "period": {
                    "start_date": "2024-01-01T00:00:00",
                    "end_date": "2024-06-30T00:00:00",
                    "months_analyzed": 6,
                },
                "monthly_data": [
                    {
                        "month": "2024-01",
                        "total_expenses": 3500.0,
                        "transaction_count": 45,
                        "average_transaction": 77.8,
                    }
                ],
                "statistics": {
                    "average_monthly": 3500.0,
                    "median_monthly": 3450.0,
                    "std_deviation": 200.0,
                    "trend_direction": "increasing",
                    "trend_strength": "moderate",
                    "growth_rate": 2.5,
                },
                "insights": [
                    {
                        "type": "warning",
                        "title": "Gradual Spending Increase",
                        "description": "Your spending is increasing at 2.5% per month",
                        "priority": "medium",
                    }
                ],
                "projections": [
                    {
                        "month": "2024-07",
                        "projected_amount": 3587.5,
                        "confidence": "medium",
                    }
                ],
                "visualizations": {
                    "line_chart": {
                        "labels": ["2024-01"],
                        "datasets": [{"data": [3500.0]}],
                    }
                },
            }

            with patch("moneywiz_mcp_server.main.TrendService") as mock_service_class:
                mock_service = AsyncMock()
                mock_service.analyze_spending_trends.return_value = mock_trend_data
                mock_service_class.return_value = mock_service

                # Act
                result = await analyze_spending_trends(months=6, category="Groceries")

            # Assert
            assert result.period["months_analyzed"] == 6
            assert len(result.monthly_data) > 0
            assert result.statistics["trend_direction"] == "increasing"
            assert len(result.insights) > 0
            assert len(result.projections) > 0

            # Verify service was called with correct parameters
            mock_service.analyze_spending_trends.assert_called_once_with(
                months=6, category="Groceries"
            )

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_setup_mcp_config")
    async def test_analyze_category_trends_tool(self):
        """Test analyze_category_trends FastMCP tool."""
        with patch("moneywiz_mcp_server.main.get_db_manager") as mock_get_db:
            mock_db = AsyncMock()
            mock_get_db.return_value = mock_db

            mock_category_data = {
                "period": {
                    "start_date": "2024-01-01T00:00:00",
                    "end_date": "2024-06-30T00:00:00",
                    "months_analyzed": 6,
                },
                "category_trends": [
                    {
                        "category": "Groceries",
                        "total_spent": 1800.0,
                        "percentage_of_total": 25.0,
                        "trend": "stable",
                        "growth_rate": 1.2,
                        "monthly_average": 300.0,
                        "insights": [
                            {
                                "type": "info",
                                "title": "Stable Grocery Spending",
                                "description": "Your grocery spending is well controlled",
                                "priority": "low",
                            }
                        ],
                    },
                    {
                        "category": "Entertainment",
                        "total_spent": 900.0,
                        "percentage_of_total": 12.5,
                        "trend": "increasing",
                        "growth_rate": 8.5,
                        "monthly_average": 150.0,
                        "insights": [
                            {
                                "type": "warning",
                                "title": "Rising Entertainment Costs",
                                "description": "Entertainment spending is growing rapidly",
                                "priority": "medium",
                            }
                        ],
                    },
                ],
                "overall_insights": [
                    {
                        "type": "info",
                        "title": "Category Analysis Summary",
                        "description": "2 categories analyzed with mixed trends",
                        "priority": "low",
                    }
                ],
            }

            with patch("moneywiz_mcp_server.main.TrendService") as mock_service_class:
                mock_service = AsyncMock()
                mock_service.analyze_category_trends.return_value = mock_category_data
                mock_service_class.return_value = mock_service

                # Act
                result = await analyze_category_trends(months=6, top_n=5)

            # Assert
            assert result.period["months_analyzed"] == 6
            assert len(result.category_trends) == 2
            assert result.category_trends[0]["category"] == "Groceries"
            assert result.category_trends[1]["category"] == "Entertainment"
            assert len(result.overall_insights) > 0

            # Verify service was called correctly
            mock_service.analyze_category_trends.assert_called_once_with(
                months=6, top_n=5
            )

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_setup_mcp_config")
    async def test_analyze_income_expense_trends_tool(self):
        """Test analyze_income_expense_trends FastMCP tool."""
        with patch("moneywiz_mcp_server.main.get_db_manager") as mock_get_db:
            mock_db = AsyncMock()
            mock_get_db.return_value = mock_db

            mock_income_expense_data = {
                "period": {"months_analyzed": 12},
                "monthly_data": [
                    {
                        "month": "2024-01",
                        "income": 5000.0,
                        "expenses": 4200.0,
                        "net_savings": 800.0,
                        "savings_rate": 16.0,
                    },
                    {
                        "month": "2024-02",
                        "income": 5100.0,
                        "expenses": 4150.0,
                        "net_savings": 950.0,
                        "savings_rate": 18.6,
                    },
                ],
                "trends": {
                    "income": {
                        "direction": "increasing",
                        "growth_rate": 2.0,
                        "stability": "stable",
                    },
                    "expenses": {
                        "direction": "stable",
                        "growth_rate": -0.5,
                        "stability": "stable",
                    },
                    "savings_rate": {
                        "direction": "increasing",
                        "average": 17.3,
                        "improving": True,
                    },
                },
                "insights": [
                    {
                        "type": "positive",
                        "title": "Improving Financial Health",
                        "description": "Your savings rate is trending upward",
                        "priority": "low",
                    }
                ],
            }

            with patch("moneywiz_mcp_server.main.TrendService") as mock_service_class:
                mock_service = AsyncMock()
                mock_service.analyze_income_vs_expense_trends.return_value = (
                    mock_income_expense_data
                )
                mock_service_class.return_value = mock_service

                # Act
                result = await analyze_income_expense_trends(months=12)

            # Assert
            assert result.period["months_analyzed"] == 12
            assert len(result.monthly_data) == 2
            assert result.trends["income"]["direction"] == "increasing"
            assert result.trends["savings_rate"]["improving"] is True
            assert len(result.insights) > 0

            # Verify service call
            mock_service.analyze_income_vs_expense_trends.assert_called_once_with(
                months=12
            )

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_setup_mcp_config")
    async def test_database_connection_lifecycle(self):
        """Test that database connections are properly managed in tools."""
        with patch("moneywiz_mcp_server.main.get_db_manager") as mock_get_db:
            mock_db = AsyncMock()
            mock_get_db.return_value = mock_db

            # Mock to raise an exception to test cleanup
            with patch("moneywiz_mcp_server.main.SavingsService") as mock_service_class:
                mock_service = AsyncMock()
                mock_service.get_savings_recommendations.side_effect = Exception(
                    "Test error"
                )
                mock_service_class.return_value = mock_service

                # Act & Assert - should raise the exception
                with pytest.raises(
                    RuntimeError, match="Failed to generate savings recommendations"
                ):
                    await get_savings_recommendations()

                # Even with exception, database should be closed
                mock_db.close.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_setup_mcp_config")
    async def test_error_handling_in_tools(self):
        """Test error handling in FastMCP tools."""
        with patch("moneywiz_mcp_server.main.get_db_manager") as mock_get_db:
            # Mock get_db_manager to raise an exception
            mock_get_db.side_effect = Exception("Database connection failed")

            # Act & Assert
            with pytest.raises(
                RuntimeError, match="Failed to generate savings recommendations"
            ):
                await get_savings_recommendations()

            # Verify error was logged and properly handled
            mock_get_db.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
