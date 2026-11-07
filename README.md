# SpendWise – Smart Personal Expense Tracker

A dark-themed desktop personal-finance app built with Python, Tkinter, SQLite and Matplotlib.

## Features
- Dashboard with balance, monthly income, expenses and budget remaining
- Add, edit, delete and search expense records
- Add, edit and delete income records
- Overall and category-wise monthly budgets with utilisation bars and overspend warnings
- Analytics: category pie chart, category bar chart and monthly spending trend
- Export expense and income history to CSV
- SQLite database persists automatically between launches
- First launch inserts a small set of demonstration transactions

## Project structure
```text
SpendWise/
├── app.py
├── requirements.txt
├── README.md
└── spendwise.db       # created automatically on first run
```

## Requirements
- Python 3.9 or newer
- Tkinter (usually included with Python)
- SQLite3 (included with Python)
- Matplotlib for analytics charts

Pillow is listed as an optional dependency for future image assets; the current interface uses native Tkinter widgets and does not require image files.

## Install and run

### Windows
1. Install Python from https://www.python.org/downloads/
2. During setup, enable **Add Python to PATH**.
3. Open Command Prompt in the SpendWise folder.
4. Run:
   ```bash
   py -m pip install -r requirements.txt
   py app.py
   ```

### macOS / Linux
```bash
python3 -m pip install -r requirements.txt
python3 app.py
```

If Tkinter is missing on Linux, install your distribution's Tk package (for Ubuntu/Debian: `sudo apt install python3-tk`).

## Database
`spendwise.db` is created beside `app.py`. It contains:
- `expenses`: name, amount, category, date and description
- `income`: source, amount, date and description
- `budgets`: month, category and limit

Do not delete this file if you want to keep your records. To reset the demo database, close the app and delete `spendwise.db`; it will be recreated on next launch.

## Demo data
On the first launch only, sample expenses and income for the current month are inserted. If the database already contains at least one expense, sample data is not inserted again. You can edit or delete the demo entries.

## How the main parts work
- `Database`: creates tables and performs SQL insert, select, update and delete operations.
- `SpendWiseApp`: builds the interface and connects button actions to database methods.
- `show_dashboard()`: calculates monthly totals and displays recent activity and budget progress.
- `show_expenses()` / `show_income()`: display transaction tables.
- `expense_form()` / `income_form()`: collect user input in a popup form.
- `save_expense_form()` / `save_income_form()`: validate and save form data.
- `show_budgets()` / `refresh_budgets()`: save budget limits and compare them with actual spending.
- `show_analytics()` / `refresh_analytics()`: query SQLite and draw Matplotlib charts.
- `export_csv()`: writes transaction history to a CSV file.

## Presentation tip
Explain the project in this order: problem → objective → technology stack → database tables → CRUD workflow → budget calculations → analytics → live demo.
