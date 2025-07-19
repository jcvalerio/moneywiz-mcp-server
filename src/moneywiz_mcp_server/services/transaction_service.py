"""Transaction service for MoneyWiz MCP Server."""

import logging
from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any

from ..database.connection import DatabaseManager
from ..models.transaction import TransactionModel, TransactionType, DateRange
from ..models.analytics_result import IncomeExpenseAnalysis, CategoryExpense
from ..utils.date_utils import core_data_timestamp_to_datetime, datetime_to_core_data_timestamp

logger = logging.getLogger(__name__)


class TransactionService:
    """Service for transaction operations and analysis."""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self._category_cache: Dict[int, str] = {}
        self._payee_cache: Dict[int, str] = {}
        self._account_currency_cache: Dict[int, str] = {}
    
    async def get_transactions(
        self,
        start_date: datetime,
        end_date: datetime,
        account_ids: Optional[List[int]] = None,
        categories: Optional[List[str]] = None,
        transaction_types: Optional[List[TransactionType]] = None,
        limit: Optional[int] = None
    ) -> List[TransactionModel]:
        """
        Get transactions with filtering options.
        
        Args:
            start_date: Start date for filtering
            end_date: End date for filtering
            account_ids: Optional list of account IDs to filter
            categories: Optional list of category names to filter
            transaction_types: Optional list of transaction types to filter
            limit: Optional limit on number of results
            
        Returns:
            List of TransactionModel objects
        """
        try:
            # Convert dates to Core Data timestamps
            start_timestamp = datetime_to_core_data_timestamp(start_date)
            end_timestamp = datetime_to_core_data_timestamp(end_date)
            
            # Build base query for transaction entities
            transaction_entities = [37, 45, 46, 47]  # Core transaction types
            
            # Add investment entities if needed
            if transaction_types:
                if any(tt in [TransactionType.INVESTMENT_BUY, TransactionType.INVESTMENT_SELL, 
                             TransactionType.INVESTMENT_EXCHANGE] for tt in transaction_types):
                    transaction_entities.extend([38, 40, 41])
                if TransactionType.REFUND in transaction_types:
                    transaction_entities.append(43)
                if TransactionType.RECONCILE in transaction_types:
                    transaction_entities.append(42)
                if TransactionType.TRANSFER_BUDGET in transaction_types:
                    transaction_entities.append(44)
            else:
                # Include all transaction types by default
                transaction_entities.extend([38, 40, 41, 42, 43, 44])
            
            # Build WHERE conditions
            where_conditions = [
                f"Z_ENT IN ({','.join('?' for _ in transaction_entities)})",
                "ZDATE1 >= ?",
                "ZDATE1 <= ?"
            ]
            params = list(transaction_entities) + [start_timestamp, end_timestamp]
            
            # Add account filter
            if account_ids:
                where_conditions.append(f"ZACCOUNT2 IN ({','.join('?' for _ in account_ids)})")
                params.extend(account_ids)
            
            # Build final query
            query = f"""
            SELECT * FROM ZSYNCOBJECT 
            WHERE {' AND '.join(where_conditions)}
            ORDER BY ZDATE1 DESC
            """
            
            if limit:
                query += f" LIMIT {limit}"
            
            logger.debug(f"Executing transaction query with {len(params)} parameters")
            
            # Execute query
            rows = await self.db_manager.execute_query(query, params)
            
            # Convert to TransactionModel objects
            transactions = []
            for row in rows:
                try:
                    transaction = TransactionModel.from_raw_data(row)
                    
                    # Enhance with category and payee information
                    transaction = await self._enhance_transaction(transaction)
                    
                    # Apply category filter if specified
                    if categories and transaction.category not in categories:
                        continue
                    
                    # Apply transaction type filter if specified
                    if transaction_types and transaction.transaction_type not in transaction_types:
                        continue
                    
                    transactions.append(transaction)
                    
                except Exception as e:
                    logger.warning(f"Failed to parse transaction row: {e}")
                    continue
            
            logger.info(f"Retrieved {len(transactions)} transactions")
            return transactions
            
        except Exception as e:
            logger.error(f"Failed to get transactions: {e}")
            raise RuntimeError(f"Failed to retrieve transactions: {str(e)}")
    
    async def get_expense_summary(
        self,
        start_date: datetime,
        end_date: datetime,
        group_by: str = "category"
    ) -> Dict[str, Any]:
        """
        Get expense summary grouped by category or payee.
        
        Args:
            start_date: Start date for analysis
            end_date: End date for analysis
            group_by: "category" or "payee"
            
        Returns:
            Dictionary with expense summary data
        """
        try:
            # Get all expense transactions (negative amounts)
            transactions = await self.get_transactions(start_date, end_date)
            expenses = [t for t in transactions if t.is_expense()]
            
            # Group expenses
            groups = {}
            total_expenses = Decimal('0')
            
            for expense in expenses:
                amount = abs(expense.amount)  # Make positive for display
                total_expenses += amount
                
                if group_by == "category":
                    group_key = expense.category or "Uncategorized"
                elif group_by == "payee":
                    group_key = expense.payee or "Unknown Payee"
                else:
                    group_key = "All Expenses"
                
                if group_key not in groups:
                    groups[group_key] = {
                        "total_amount": Decimal('0'),
                        "transaction_count": 0,
                        "transactions": []
                    }
                
                groups[group_key]["total_amount"] += amount
                groups[group_key]["transaction_count"] += 1
                groups[group_key]["transactions"].append(expense)
            
            # Calculate percentages and create CategoryExpense objects
            category_expenses = []
            for group_name, data in groups.items():
                percentage = float(data["total_amount"] / total_expenses * 100) if total_expenses > 0 else 0
                avg_amount = data["total_amount"] / data["transaction_count"] if data["transaction_count"] > 0 else Decimal('0')
                
                category_expense = CategoryExpense(
                    category_name=group_name,
                    category_id=None,  # Could be enhanced later
                    total_amount=data["total_amount"],
                    transaction_count=data["transaction_count"],
                    average_amount=avg_amount,
                    percentage_of_total=percentage
                )
                category_expenses.append(category_expense)
            
            # Sort by amount descending
            category_expenses.sort(key=lambda x: x.total_amount, reverse=True)
            
            return {
                "total_expenses": total_expenses,
                "category_breakdown": category_expenses,
                "analysis_period": DateRange(start_date=start_date, end_date=end_date),
                "currency": "USD",  # Default, could be enhanced
                "group_by": group_by
            }
            
        except Exception as e:
            logger.error(f"Failed to get expense summary: {e}")
            raise RuntimeError(f"Failed to generate expense summary: {str(e)}")
    
    async def get_income_vs_expense(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> IncomeExpenseAnalysis:
        """
        Analyze income vs expenses for the given period.
        
        Args:
            start_date: Start date for analysis
            end_date: End date for analysis
            
        Returns:
            IncomeExpenseAnalysis object
        """
        try:
            # Get all transactions
            transactions = await self.get_transactions(start_date, end_date)
            
            # Separate income and expenses
            income_transactions = [t for t in transactions if t.is_income()]
            expense_transactions = [t for t in transactions if t.is_expense()]
            
            # Calculate totals
            total_income = sum(t.amount for t in income_transactions)
            total_expenses = sum(abs(t.amount) for t in expense_transactions)  # Make positive
            net_savings = total_income - total_expenses
            savings_rate = float(net_savings / total_income * 100) if total_income > 0 else 0
            
            # Generate income breakdown
            income_summary = await self.get_expense_summary(start_date, end_date, "category")
            # Note: This would need to be adapted for income transactions
            
            # Generate expense breakdown
            expense_summary = await self.get_expense_summary(start_date, end_date, "category")
            
            return IncomeExpenseAnalysis(
                total_income=total_income,
                total_expenses=total_expenses,
                net_savings=net_savings,
                savings_rate=savings_rate,
                income_breakdown=[],  # Placeholder - would need income categorization
                expense_breakdown=expense_summary["category_breakdown"],
                analysis_period=DateRange(start_date=start_date, end_date=end_date),
                currency="USD",
                monthly_averages={}  # Placeholder - would need monthly breakdown
            )
            
        except Exception as e:
            logger.error(f"Failed to analyze income vs expenses: {e}")
            raise RuntimeError(f"Failed to analyze income vs expenses: {str(e)}")
    
    async def _enhance_transaction(self, transaction: TransactionModel) -> TransactionModel:
        """
        Enhance transaction with category and payee information.
        
        Args:
            transaction: Base transaction model
            
        Returns:
            Enhanced transaction model
        """
        try:
            # Get category name if category_id exists
            if transaction.category_id and transaction.category_id not in self._category_cache:
                category_query = "SELECT ZNAME FROM ZSYNCOBJECT WHERE Z_ENT = 19 AND Z_PK = ?"
                category_result = await self.db_manager.execute_query(category_query, (transaction.category_id,))
                if category_result:
                    self._category_cache[transaction.category_id] = category_result[0]["ZNAME"]
                else:
                    self._category_cache[transaction.category_id] = "Unknown Category"
            
            if transaction.category_id:
                transaction.category = self._category_cache.get(transaction.category_id, "Unknown Category")
            
            # Get payee name if payee_id exists
            if transaction.payee_id and transaction.payee_id not in self._payee_cache:
                payee_query = "SELECT ZNAME FROM ZSYNCOBJECT WHERE Z_ENT = 28 AND Z_PK = ?"
                payee_result = await self.db_manager.execute_query(payee_query, (transaction.payee_id,))
                if payee_result:
                    self._payee_cache[transaction.payee_id] = payee_result[0]["ZNAME"]
                else:
                    self._payee_cache[transaction.payee_id] = "Unknown Payee"
            
            if transaction.payee_id:
                transaction.payee = self._payee_cache.get(transaction.payee_id, "Unknown Payee")
            
            # Get account currency if not cached
            if transaction.account_id not in self._account_currency_cache:
                account_query = """
                SELECT ZCURRENCYNAME FROM ZSYNCOBJECT 
                WHERE Z_ENT BETWEEN 10 AND 16 AND Z_PK = ?
                """
                account_result = await self.db_manager.execute_query(account_query, (transaction.account_id,))
                if account_result:
                    self._account_currency_cache[transaction.account_id] = account_result[0]["ZCURRENCYNAME"]
                else:
                    self._account_currency_cache[transaction.account_id] = "USD"
            
            transaction.currency = self._account_currency_cache.get(transaction.account_id, "USD")
            
            return transaction
            
        except Exception as e:
            logger.warning(f"Failed to enhance transaction {transaction.id}: {e}")
            return transaction