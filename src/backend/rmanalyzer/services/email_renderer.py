"""Service for rendering email content."""

from typing import List, Optional
from ..models import Category, Group
from ..utils import to_currency


class EmailRenderer:
    """Service for rendering email content."""

    @staticmethod
    def _render_error_section(errors: Optional[List[str]]) -> str:
        """Renders the error section using f-strings."""
        if not errors:
            return ""

        error_items = "".join([f"<li>{e}</li>" for e in errors])
        return f"""
        <div style="background-color: #fff4f4; border-left: 5px solid #d13438; padding: 15px; margin-bottom: 20px;">
            <h3 style="color: #d13438; margin-top: 0; font-size: 18px;">⚠️ Warning: Some transactions were skipped</h3>
            <ul style="margin-bottom: 0; padding-left: 20px;">
                {error_items}
            </ul>
        </div>
        """

    @classmethod
    def render_error_body(cls, errors: List[str]) -> str:
        """Renders the body for an error email."""
        return f"""
        <html>
        <body style="font-family: 'Segoe UI', sans-serif; color: #333; line-height: 1.6; background-color: #f4f4f4; margin: 0; padding: 20px;">
            <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                <div style="background-color: #d13438; padding: 20px; text-align: center; color: white;">
                    <h2 style="margin: 0;">Upload Failed</h2>
                </div>
                <div style="padding: 20px;">
                    <p>The uploaded CSV could not be processed due to the following errors:</p>
                    {cls._render_error_section(errors)}
                </div>
            </div>
        </body>
        </html>
        """

    @staticmethod
    def _render_rows(group: Group, tracked_categories: List[Category]) -> str:
        """Helper to render table rows."""
        rows_html = ""
        for p in group.members:
            row_cells = f"<td>{p.name}</td>"
            for c in tracked_categories:
                row_cells += f"<td>{to_currency(p.get_expenses(c))}</td>"
            row_cells += (
                f"<td style='font-weight: bold;'>{to_currency(p.get_expenses())}</td>"
            )
            rows_html += f"<tr>{row_cells}</tr>"

        # Difference Row (if 2 members)
        if len(group.members) == 2:
            p1, p2 = group.members
            diff_cells = "<td>Difference</td>"
            for c in tracked_categories:
                diff_cells += (
                    f"<td>{to_currency(group.get_expenses_difference(p1, p2, c))}</td>"
                )
            diff_cells += (
                f"<td style='font-weight: bold;'>"
                f"{to_currency(group.get_expenses_difference(p1, p2))}</td>"
            )
            rows_html += f"<tr style='background-color: #f8f9fa;'>{diff_cells}</tr>"
        return rows_html

    @classmethod
    def render_body(cls, group: Group, errors: Optional[List[str]] = None) -> str:
        """Generate the HTML body of the email based on the group's expenses."""
        tracked_categories: List[Category] = [
            c for c in Category if c != Category.OTHER
        ]

        # Build Table Headers
        headers_html = "<th></th>"
        for c in tracked_categories:
            headers_html += f"<th>{c.value}</th>"
        headers_html += "<th>Total</th>"

        # Build Table Rows
        rows_html = cls._render_rows(group, tracked_categories)

        # Debt Message
        debt_html = ""
        if len(group.members) == 2:
            p1, p2 = group.members
            msg = (
                f"{p1.name} owes {p2.name}: "
                f"<strong>{to_currency(group.get_debt(p1, p2))}</strong>"
            )
            debt_html = f"""
            <div style="margin-top: 25px; font-size: 16px; background-color: #f0f6ff; padding: 15px; border-radius: 4px; border: 1px solid #c7e0f4; color: #005a9e; text-align: center;">
                {msg}
            </div>
            """

        # Construct Full Body
        min_date = group.get_oldest_transaction()
        max_date = group.get_newest_transaction()
        date_range = (
            f"{min_date.strftime('%m/%d/%y')} - {max_date.strftime('%m/%d/%y')}"
        )

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; color: #333; line-height: 1.6; background-color: #f4f4f4; margin: 0; padding: 20px;">
            <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                <!-- Header -->
                <div style="background-color: #0078D4; padding: 20px; text-align: center; color: white;">
                    <h2 style="margin: 0; font-weight: 600;">Expense Summary</h2>
                    <p style="margin: 5px 0 0; opacity: 0.9;">{date_range}</p>
                </div>

                <div style="padding: 20px;">
                    {cls._render_error_section(errors)}

                    <div style="overflow-x: auto;">
                        <table style="width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 14px;">
                            <thead>
                                <tr style="background-color: #f8f9fa; text-align: left;">
                                    {headers_html}
                                </tr>
                            </thead>
                            <tbody>
                                {rows_html}
                            </tbody>
                        </table>
                    </div>

                    {debt_html}
                </div>

                <!-- Footer -->
                <div style="padding: 15px; text-align: center; font-size: 12px; color: #666; border-top: 1px solid #eee;">
                    <p>Generated by RM Analyzer</p>
                </div>
            </div>

            <!-- CSS for Table Cells (Inline styles are safest for email, but this helps in some clients) -->
            <style>
                th, td {{ padding: 12px; border-bottom: 1px solid #e0e0e0; }}
                th {{ font-weight: 600; color: #666; }}
                tr:last-child td {{ border-bottom: none; }}
            </style>
        </body>
        </html>
        """

    @staticmethod
    def render_subject(group: Group) -> str:
        """Generate the email subject based on the transaction date range."""
        min_date = group.get_oldest_transaction()
        max_date = group.get_newest_transaction()
        return (
            f"Transactions Summary: {min_date.strftime('%m/%d/%y')} - "
            f"{max_date.strftime('%m/%d/%y')}"
        )
