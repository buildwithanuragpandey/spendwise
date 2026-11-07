"""
SpendWise – Smart Personal Expense Tracker
A beginner-friendly Tkinter + SQLite desktop finance application.

Run: python app.py
Optional charts: pip install matplotlib pillow
Tkinter and SQLite are included with most standard Python installations.
"""
import csv
import sqlite3
from datetime import date, datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

try:
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

APP_DIR = Path(__file__).resolve().parent
DB_PATH = APP_DIR / "spendwise.db"

BG = "#10141F"
SIDEBAR = "#171D2B"
CARD = "#20293A"
CARD_ALT = "#252F43"
ACCENT = "#6C63FF"
SUCCESS = "#27C997"
WARNING = "#FFB84D"
DANGER = "#FF6B78"
WHITE = "#FFFFFF"
MUTED = "#A0AEC0"
BORDER = "#303B50"
CATEGORIES = ["Food", "Shopping", "Transportation", "Education",
              "Entertainment", "Healthcare", "Bills", "Others"]


class Database:
    """Handles SQLite setup and all transaction CRUD operations."""
    def __init__(self, path=DB_PATH):
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.create_tables()
        self.add_demo_data_if_empty()

    def create_tables(self):
        self.connection.executescript("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                amount REAL NOT NULL,
                category TEXT NOT NULL,
                transaction_date TEXT NOT NULL,
                description TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS income (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                amount REAL NOT NULL,
                transaction_date TEXT NOT NULL,
                description TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS budgets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                month TEXT NOT NULL,
                category TEXT NOT NULL,
                amount REAL NOT NULL,
                UNIQUE(month, category)
            );
        """)
        self.connection.commit()

    def add_demo_data_if_empty(self):
        count = self.connection.execute("SELECT COUNT(*) FROM expenses").fetchone()[0]
        if count:
            return
        today = date.today()
        samples = [
            ("Groceries", 1250, "Food", today.replace(day=2).isoformat(), "Weekly groceries"),
            ("Metro card", 450, "Transportation", today.replace(day=4).isoformat(), "Commute"),
            ("Course materials", 899, "Education", today.replace(day=7).isoformat(), "Reference books"),
            ("Cafe lunch", 320, "Food", today.replace(day=10).isoformat(), "Lunch with friends"),
            ("Movie night", 600, "Entertainment", today.replace(day=13).isoformat(), "Weekend"),
            ("Mobile bill", 499, "Bills", today.replace(day=15).isoformat(), "Monthly recharge"),
        ]
        self.connection.executemany(
            "INSERT INTO expenses(name,amount,category,transaction_date,description) VALUES(?,?,?,?,?)",
            samples)
        self.connection.executemany(
            "INSERT INTO income(source,amount,transaction_date,description) VALUES(?,?,?,?)",
            [("Monthly allowance", 12000, today.replace(day=1).isoformat(), "Demo income"),
             ("Freelance work", 2500, today.replace(day=12).isoformat(), "Demo income")])
        month = today.strftime("%Y-%m")
        self.connection.execute(
            "INSERT OR IGNORE INTO budgets(month,category,amount) VALUES(?,?,?)",
            (month, "Overall", 10000))
        for category, amount in [("Food", 2500), ("Shopping", 1500),
                                 ("Transportation", 1000), ("Education", 2000)]:
            self.connection.execute(
                "INSERT OR IGNORE INTO budgets(month,category,amount) VALUES(?,?,?)",
                (month, category, amount))
        self.connection.commit()

    def all_expenses(self, search=""):
        return self.connection.execute(
            """SELECT * FROM expenses
               WHERE name LIKE ? OR category LIKE ? OR description LIKE ?
               ORDER BY transaction_date DESC, id DESC""",
            (f"%{search}%", f"%{search}%", f"%{search}%")).fetchall()

    def all_income(self):
        return self.connection.execute(
            "SELECT * FROM income ORDER BY transaction_date DESC, id DESC").fetchall()

    def save_expense(self, values, record_id=None):
        if record_id:
            self.connection.execute(
                """UPDATE expenses SET name=?,amount=?,category=?,transaction_date=?,description=?
                   WHERE id=?""", (*values, record_id))
        else:
            self.connection.execute(
                """INSERT INTO expenses(name,amount,category,transaction_date,description)
                   VALUES(?,?,?,?,?)""", values)
        self.connection.commit()

    def save_income(self, values, record_id=None):
        if record_id:
            self.connection.execute(
                """UPDATE income SET source=?,amount=?,transaction_date=?,description=?
                   WHERE id=?""", (*values, record_id))
        else:
            self.connection.execute(
                """INSERT INTO income(source,amount,transaction_date,description) VALUES(?,?,?,?)""",
                values)
        self.connection.commit()

    def delete_record(self, table, record_id):
        if table not in ("expenses", "income"):
            raise ValueError("Unsupported table")
        self.connection.execute(f"DELETE FROM {table} WHERE id=?", (record_id,))
        self.connection.commit()

    def set_budget(self, month, category, amount):
        self.connection.execute(
            """INSERT INTO budgets(month,category,amount) VALUES(?,?,?)
               ON CONFLICT(month,category) DO UPDATE SET amount=excluded.amount""",
            (month, category, amount))
        self.connection.commit()

    def budgets_for_month(self, month):
        return self.connection.execute(
            "SELECT * FROM budgets WHERE month=? ORDER BY category", (month,)).fetchall()

    def month_totals(self, month):
        expense = self.connection.execute(
            "SELECT COALESCE(SUM(amount),0) FROM expenses WHERE substr(transaction_date,1,7)=?",
            (month,)).fetchone()[0]
        income = self.connection.execute(
            "SELECT COALESCE(SUM(amount),0) FROM income WHERE substr(transaction_date,1,7)=?",
            (month,)).fetchone()[0]
        return income, expense

    def total_balance(self):
        income = self.connection.execute("SELECT COALESCE(SUM(amount),0) FROM income").fetchone()[0]
        expense = self.connection.execute("SELECT COALESCE(SUM(amount),0) FROM expenses").fetchone()[0]
        return income - expense

    def close(self):
        self.connection.close()


class SpendWiseApp:
    def __init__(self, root):
        self.root = root
        self.db = Database()
        self.selected_expense_id = None
        self.selected_income_id = None
        self.current_page = "Dashboard"
        self.setup_window()
        self.setup_styles()
        self.build_shell()
        self.show_dashboard()
        self.update_clock()
        self.root.protocol("WM_DELETE_WINDOW", self.close_app)

    def setup_window(self):
        self.root.title("SpendWise | Personal Finance")
        self.root.geometry("1320x820")
        self.root.minsize(1080, 700)
        self.root.configure(bg=BG)

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background=CARD, foreground=WHITE,
                        fieldbackground=CARD, rowheight=34, borderwidth=0,
                        font=("Segoe UI", 10))
        style.configure("Treeview.Heading", background=SIDEBAR, foreground=MUTED,
                        font=("Segoe UI", 9, "bold"), relief="flat")
        style.map("Treeview", background=[("selected", ACCENT)])
        style.configure("TCombobox", fieldbackground=CARD, background=CARD,
                        foreground=WHITE, arrowcolor=WHITE)
        style.configure("Horizontal.TProgressbar", troughcolor=SIDEBAR,
                        background=SUCCESS, bordercolor=SIDEBAR, lightcolor=SUCCESS,
                        darkcolor=SUCCESS)

    def build_shell(self):
        self.sidebar = tk.Frame(self.root, bg=SIDEBAR, width=230)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        tk.Label(self.sidebar, text="◈  SpendWise", bg=SIDEBAR, fg=WHITE,
                 font=("Segoe UI", 19, "bold")).pack(anchor="w", padx=22, pady=(28, 4))
        tk.Label(self.sidebar, text="PERSONAL FINANCE", bg=SIDEBAR, fg=MUTED,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=25, pady=(0, 30))
        self.nav_buttons = {}
        for label, icon in [("Dashboard", "▦"), ("Expenses", "↘"),
                            ("Income", "↗"), ("Budgets", "◷"),
                            ("Analytics", "▥")]:
            button = tk.Button(self.sidebar, text=f"  {icon}    {label}",
                               command=lambda page=label: self.navigate(page),
                               anchor="w", relief="flat", bd=0, padx=18, pady=13,
                               bg=SIDEBAR, fg=MUTED, activebackground=CARD,
                               activeforeground=WHITE, font=("Segoe UI", 11),
                               cursor="hand2")
            button.pack(fill="x", padx=12, pady=3)
            self.nav_buttons[label] = button
            button.bind("<Enter>", lambda e, b=button: b.configure(bg=CARD))
            button.bind("<Leave>", lambda e, b=button, p=label:
                        b.configure(bg=ACCENT if self.current_page == p else SIDEBAR))
        tk.Frame(self.sidebar, bg=BORDER, height=1).pack(fill="x", padx=20, pady=22)
        tk.Label(self.sidebar, text="YOUR MONEY, IN FOCUS.", bg=SIDEBAR, fg=MUTED,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=23)
        tk.Label(self.sidebar, text="Track • Plan • Grow", bg=SIDEBAR, fg=WHITE,
                 font=("Segoe UI", 10)).pack(anchor="w", padx=23, pady=7)

        self.main = tk.Frame(self.root, bg=BG)
        self.main.pack(side="left", fill="both", expand=True)
        header = tk.Frame(self.main, bg=BG)
        header.pack(fill="x", padx=30, pady=(22, 12))
        self.page_title = tk.Label(header, text="Dashboard", bg=BG, fg=WHITE,
                                   font=("Segoe UI", 22, "bold"))
        self.page_title.pack(side="left")
        self.clock_label = tk.Label(header, text="", bg=BG, fg=MUTED,
                                    font=("Segoe UI", 10))
        self.clock_label.pack(side="right", pady=8)
        self.content = tk.Frame(self.main, bg=BG)
        self.content.pack(fill="both", expand=True, padx=30, pady=(5, 25))

    def update_clock(self):
        self.clock_label.configure(text=datetime.now().strftime("%A, %d %B %Y  •  %I:%M:%S %p"))
        self.root.after(1000, self.update_clock)

    def clear_content(self):
        for widget in self.content.winfo_children():
            widget.destroy()

    def navigate(self, page):
        self.current_page = page
        for name, button in self.nav_buttons.items():
            button.configure(bg=ACCENT if name == page else SIDEBAR,
                             fg=WHITE if name == page else MUTED)
        self.page_title.configure(text=page)
        {"Dashboard": self.show_dashboard, "Expenses": self.show_expenses,
         "Income": self.show_income, "Budgets": self.show_budgets,
         "Analytics": self.show_analytics}[page]()

    def card(self, parent, title, value, subtitle="", accent=ACCENT):
        frame = tk.Frame(parent, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        tk.Label(frame, text=title.upper(), bg=CARD, fg=MUTED,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=18, pady=(16, 7))
        tk.Label(frame, text=value, bg=CARD, fg=WHITE,
                 font=("Segoe UI", 22, "bold")).pack(anchor="w", padx=18)
        tk.Label(frame, text=subtitle, bg=CARD, fg=accent,
                 font=("Segoe UI", 9)).pack(anchor="w", padx=18, pady=(5, 16))
        return frame

    def section_title(self, parent, title, subtitle=None):
        tk.Label(parent, text=title, bg=BG, fg=WHITE,
                 font=("Segoe UI", 13, "bold")).pack(anchor="w")
        if subtitle:
            tk.Label(parent, text=subtitle, bg=BG, fg=MUTED,
                     font=("Segoe UI", 9)).pack(anchor="w", pady=(3, 9))

    def money(self, amount):
        return f"₹{amount:,.2f}"

    def show_dashboard(self):
        self.clear_content()
        month = date.today().strftime("%Y-%m")
        month_income, month_expense = self.db.month_totals(month)
        budgets = self.db.budgets_for_month(month)
        overall = next((b["amount"] for b in budgets if b["category"] == "Overall"), 0)
        remaining = overall - month_expense if overall else 0

        cards = tk.Frame(self.content, bg=BG)
        cards.pack(fill="x")
        values = [
            ("Total Balance", self.money(self.db.total_balance()), "All-time net balance", ACCENT),
            ("Monthly Income", self.money(month_income), "Income received this month", SUCCESS),
            ("Monthly Expenses", self.money(month_expense), "Spending this month", WARNING),
            ("Budget Remaining", self.money(remaining), "Set an overall monthly budget" if not overall else "Against your monthly limit",
             DANGER if remaining < 0 else SUCCESS)]
        for i, item in enumerate(values):
            c = self.card(cards, *item)
            c.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 12, 0), pady=4)
            cards.grid_columnconfigure(i, weight=1)

        lower = tk.Frame(self.content, bg=BG)
        lower.pack(fill="both", expand=True, pady=(22, 0))
        left = tk.Frame(lower, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        left.pack(side="left", fill="both", expand=True, padx=(0, 12))
        right = tk.Frame(lower, bg=CARD, width=330, highlightbackground=BORDER, highlightthickness=1)
        right.pack(side="right", fill="y")
        self.section_title(left, "Recent transactions", "Your latest financial activity")
        rows = self.db.connection.execute("""
            SELECT id,name AS label,amount,transaction_date,'Expense' AS kind FROM expenses
            UNION ALL
            SELECT id,source AS label,amount,transaction_date,'Income' AS kind FROM income
            ORDER BY transaction_date DESC LIMIT 7
        """).fetchall()
        tree = self.make_tree(left, [("Date", 105), ("Description", 180),
                                     ("Type", 90), ("Amount", 120)])
        for row in rows:
            tree.insert("", "end", values=(row["transaction_date"], row["label"],
                                           row["kind"], self.money(row["amount"])))
        self.section_title(right, "Monthly budget", "Budget utilisation")
        if overall:
            pct = month_expense / overall * 100
            tk.Label(right, text=f"{min(pct, 999):.1f}%", bg=CARD, fg=WHITE,
                     font=("Segoe UI", 27, "bold")).pack(anchor="w", padx=18, pady=(12, 3))
            ttk.Progressbar(right, maximum=100, value=min(pct, 100), length=270).pack(
                padx=18, fill="x", pady=10)
            tk.Label(right, text=f"{self.money(month_expense)} spent of {self.money(overall)}",
                     bg=CARD, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w", padx=18)
            if pct > 100:
                tk.Label(right, text="⚠ Budget exceeded", bg=CARD, fg=DANGER,
                         font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=18, pady=12)
        else:
            tk.Label(right, text="No monthly budget yet.", bg=CARD, fg=MUTED).pack(
                anchor="w", padx=18, pady=15)
            self.action_button(right, "Set a budget", lambda: self.navigate("Budgets")).pack(
                anchor="w", padx=18, pady=8)
        tk.Label(right, text="Quick tip", bg=CARD, fg=ACCENT,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=18, pady=(28, 4))
        tk.Label(right, text="Review your categories weekly to spot small expenses before they add up.",
                 bg=CARD, fg=MUTED, wraplength=270, justify="left",
                 font=("Segoe UI", 9)).pack(anchor="w", padx=18, pady=(0, 15))

    def make_tree(self, parent, columns):
        wrap = tk.Frame(parent, bg=CARD)
        wrap.pack(fill="both", expand=True, padx=16, pady=(12, 16))
        tree = ttk.Treeview(wrap, columns=[c[0] for c in columns], show="headings")
        for name, width in columns:
            tree.heading(name, text=name)
            tree.column(name, width=width, anchor="w")
        scrollbar = ttk.Scrollbar(wrap, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        return tree

    def action_button(self, parent, text, command, color=ACCENT):
        button = tk.Button(parent, text=text, command=command, bg=color, fg=WHITE,
                           activebackground=color, activeforeground=WHITE,
                           relief="flat", bd=0, padx=16, pady=9,
                           font=("Segoe UI", 9, "bold"), cursor="hand2")
        button.bind("<Enter>", lambda e: button.configure(bg="#817AFF"))
        button.bind("<Leave>", lambda e: button.configure(bg=color))
        return button

    def show_expenses(self):
        self.clear_content()
        toolbar = tk.Frame(self.content, bg=BG)
        toolbar.pack(fill="x", pady=(0, 12))
        self.expense_search = tk.StringVar()
        entry = tk.Entry(toolbar, textvariable=self.expense_search, bg=CARD, fg=WHITE,
                         insertbackground=WHITE, relief="flat", font=("Segoe UI", 10), width=28)
        entry.pack(side="left", ipady=9, padx=(0, 8))
        entry.insert(0, "")
        entry.bind("<KeyRelease>", lambda e: self.refresh_expenses())
        self.action_button(toolbar, "+ Add expense", lambda: self.expense_form()).pack(side="right")
        self.action_button(toolbar, "Export CSV", self.export_csv, color="#34445F").pack(
            side="right", padx=8)
        panel = tk.Frame(self.content, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        panel.pack(fill="both", expand=True)
        self.section_title(panel, "Expense history", "Search, edit or remove a transaction")
        self.expense_tree = self.make_tree(panel, [("ID", 50), ("Date", 105), ("Name", 180),
            ("Category", 140), ("Amount", 120), ("Description", 250)])
        self.expense_tree.bind("<<TreeviewSelect>>", self.select_expense)
        self.refresh_expenses()
        actions = tk.Frame(panel, bg=CARD)
        actions.pack(anchor="e", padx=18, pady=(0, 16))
        self.action_button(actions, "Edit selected", self.edit_expense, color="#34445F").pack(
            side="left", padx=5)
        self.action_button(actions, "Delete selected", self.delete_expense, color="#B84456").pack(
            side="left", padx=5)

    def refresh_expenses(self):
        if not hasattr(self, "expense_tree") or not self.expense_tree.winfo_exists():
            return
        for item in self.expense_tree.get_children():
            self.expense_tree.delete(item)
        for row in self.db.all_expenses(self.expense_search.get()):
            self.expense_tree.insert("", "end", values=(row["id"], row["transaction_date"],
                row["name"], row["category"], self.money(row["amount"]), row["description"]))

    def select_expense(self, event=None):
        selected = self.expense_tree.selection()
        self.selected_expense_id = int(self.expense_tree.item(selected[0], "values")[0]) if selected else None

    def expense_form(self, record=None):
        self.open_form("Add expense" if not record else "Edit expense",
            [("Expense name", "name", record["name"] if record else ""),
             ("Amount (₹)", "amount", str(record["amount"]) if record else ""),
             ("Category", "category", record["category"] if record else CATEGORIES[0]),
             ("Date (YYYY-MM-DD)", "date", record["transaction_date"] if record else date.today().isoformat()),
             ("Description (optional)", "description", record["description"] if record else "")],
            lambda values: self.save_expense_form(values, record["id"] if record else None),
            category_field="category")

    def save_expense_form(self, values, record_id):
        try:
            name = values["name"].strip()
            amount = float(values["amount"])
            if not name or amount <= 0:
                raise ValueError
            datetime.strptime(values["date"], "%Y-%m-%d")
            if values["category"] not in CATEGORIES:
                raise ValueError
        except (ValueError, TypeError):
            messagebox.showerror("Invalid input", "Enter a name, a positive amount and a valid date (YYYY-MM-DD).")
            return False
        self.db.save_expense((name, amount, values["category"], values["date"],
                              values["description"].strip()), record_id)
        messagebox.showinfo("Saved", "Expense saved successfully.")
        self.show_expenses()
        return True

    def edit_expense(self):
        if not self.selected_expense_id:
            messagebox.showwarning("Select a record", "Please select an expense to edit.")
            return
        row = self.db.connection.execute("SELECT * FROM expenses WHERE id=?",
                                         (self.selected_expense_id,)).fetchone()
        self.expense_form(row)

    def delete_expense(self):
        if not self.selected_expense_id:
            messagebox.showwarning("Select a record", "Please select an expense to delete.")
            return
        if messagebox.askyesno("Confirm deletion", "Permanently delete this expense?"):
            self.db.delete_record("expenses", self.selected_expense_id)
            self.selected_expense_id = None
            self.refresh_expenses()

    def show_income(self):
        self.clear_content()
        toolbar = tk.Frame(self.content, bg=BG)
        toolbar.pack(fill="x", pady=(0, 12))
        self.action_button(toolbar, "+ Add income", lambda: self.income_form()).pack(side="right")
        panel = tk.Frame(self.content, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        panel.pack(fill="both", expand=True)
        self.section_title(panel, "Income history", "All money received")
        self.income_tree = self.make_tree(panel, [("ID", 60), ("Date", 130),
            ("Source", 220), ("Amount", 150), ("Description", 300)])
        self.refresh_income()
        self.income_tree.bind("<<TreeviewSelect>>", self.select_income)
        actions = tk.Frame(panel, bg=CARD)
        actions.pack(anchor="e", padx=18, pady=(0, 16))
        self.action_button(actions, "Edit selected", self.edit_income, color="#34445F").pack(side="left", padx=5)
        self.action_button(actions, "Delete selected", self.delete_income, color="#B84456").pack(side="left", padx=5)

    def refresh_income(self):
        if not hasattr(self, "income_tree") or not self.income_tree.winfo_exists():
            return
        for item in self.income_tree.get_children():
            self.income_tree.delete(item)
        for row in self.db.all_income():
            self.income_tree.insert("", "end", values=(row["id"], row["transaction_date"],
                row["source"], self.money(row["amount"]), row["description"]))

    def select_income(self, event=None):
        selected = self.income_tree.selection()
        self.selected_income_id = int(self.income_tree.item(selected[0], "values")[0]) if selected else None

    def income_form(self, record=None):
        self.open_form("Add income" if not record else "Edit income",
            [("Income source", "source", record["source"] if record else ""),
             ("Amount (₹)", "amount", str(record["amount"]) if record else ""),
             ("Date (YYYY-MM-DD)", "date", record["transaction_date"] if record else date.today().isoformat()),
             ("Description (optional)", "description", record["description"] if record else "")],
            lambda values: self.save_income_form(values, record["id"] if record else None))

    def save_income_form(self, values, record_id):
        try:
            source = values["source"].strip()
            amount = float(values["amount"])
            if not source or amount <= 0:
                raise ValueError
            datetime.strptime(values["date"], "%Y-%m-%d")
        except (ValueError, TypeError):
            messagebox.showerror("Invalid input", "Enter a source, a positive amount and a valid date (YYYY-MM-DD).")
            return False
        self.db.save_income((source, amount, values["date"], values["description"].strip()), record_id)
        messagebox.showinfo("Saved", "Income saved successfully.")
        self.show_income()
        return True

    def edit_income(self):
        if not self.selected_income_id:
            messagebox.showwarning("Select a record", "Please select income to edit.")
            return
        row = self.db.connection.execute("SELECT * FROM income WHERE id=?",
                                         (self.selected_income_id,)).fetchone()
        self.income_form(row)

    def delete_income(self):
        if not self.selected_income_id:
            messagebox.showwarning("Select a record", "Please select income to delete.")
            return
        if messagebox.askyesno("Confirm deletion", "Permanently delete this income record?"):
            self.db.delete_record("income", self.selected_income_id)
            self.selected_income_id = None
            self.refresh_income()

    def open_form(self, title, fields, save_callback, category_field=None):
        window = tk.Toplevel(self.root)
        window.title(title)
        window.geometry("430x500")
        window.resizable(False, False)
        window.configure(bg=BG)
        window.transient(self.root)
        window.grab_set()
        tk.Label(window, text=title, bg=BG, fg=WHITE,
                 font=("Segoe UI", 18, "bold")).pack(anchor="w", padx=25, pady=(22, 18))
        variables = {}
        for label, key, initial in fields:
            tk.Label(window, text=label, bg=BG, fg=MUTED,
                     font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=25, pady=(8, 4))
            var = tk.StringVar(value=initial)
            variables[key] = var
            if key == category_field:
                widget = ttk.Combobox(window, textvariable=var, values=CATEGORIES,
                                      state="readonly", font=("Segoe UI", 10))
            else:
                widget = tk.Entry(window, textvariable=var, bg=CARD, fg=WHITE,
                                  insertbackground=WHITE, relief="flat",
                                  font=("Segoe UI", 10))
            widget.pack(fill="x", padx=25, ipady=8)
        def submit():
            values = {key: var.get() for key, var in variables.items()}
            if save_callback(values):
                window.destroy()
        self.action_button(window, "Save transaction", submit).pack(
            anchor="e", padx=25, pady=24)

    def show_budgets(self):
        self.clear_content()
        month = date.today().strftime("%Y-%m")
        income, spent = self.db.month_totals(month)
        panel = tk.Frame(self.content, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        panel.pack(fill="both", expand=True)
        self.section_title(panel, "Monthly budget planner", f"Budget period: {month}")
        form = tk.Frame(panel, bg=CARD)
        form.pack(fill="x", padx=18, pady=12)
        self.budget_category = tk.StringVar(value="Overall")
        self.budget_amount = tk.StringVar()
        tk.Label(form, text="Budget type", bg=CARD, fg=MUTED).pack(side="left", padx=(0, 8))
        ttk.Combobox(form, textvariable=self.budget_category,
                     values=["Overall"] + CATEGORIES, state="readonly", width=20).pack(side="left")
        tk.Label(form, text="Limit (₹)", bg=CARD, fg=MUTED).pack(side="left", padx=(18, 8))
        tk.Entry(form, textvariable=self.budget_amount, bg=BG, fg=WHITE,
                 insertbackground=WHITE, relief="flat", width=16).pack(side="left", ipady=7)
        self.action_button(form, "Save budget", self.save_budget).pack(side="left", padx=12)
        self.budget_list = tk.Frame(panel, bg=CARD)
        self.budget_list.pack(fill="both", expand=True, padx=18, pady=10)
        self.refresh_budgets()

    def save_budget(self):
        try:
            amount = float(self.budget_amount.get())
            if amount <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid amount", "Enter a budget greater than zero.")
            return
        self.db.set_budget(date.today().strftime("%Y-%m"), self.budget_category.get(), amount)
        self.budget_amount.set("")
        self.refresh_budgets()
        messagebox.showinfo("Budget saved", "Your budget limit has been updated.")

    def refresh_budgets(self):
        for widget in self.budget_list.winfo_children():
            widget.destroy()
        month = date.today().strftime("%Y-%m")
        budgets = self.db.budgets_for_month(month)
        expenses = self.db.connection.execute(
            """SELECT category,SUM(amount) AS total FROM expenses
               WHERE substr(transaction_date,1,7)=? GROUP BY category""", (month,)).fetchall()
        spent_by_category = {row["category"]: row["total"] for row in expenses}
        if not budgets:
            tk.Label(self.budget_list, text="No budgets set. Add an overall or category limit above.",
                     bg=CARD, fg=MUTED).pack(anchor="w", pady=20)
        for budget in budgets:
            spent = sum(spent_by_category.values()) if budget["category"] == "Overall" else spent_by_category.get(budget["category"], 0)
            pct = spent / budget["amount"] * 100
            row = tk.Frame(self.budget_list, bg=CARD_ALT)
            row.pack(fill="x", pady=6)
            tk.Label(row, text=budget["category"], bg=CARD_ALT, fg=WHITE,
                     font=("Segoe UI", 10, "bold")).pack(side="left", padx=14, pady=12)
            tk.Label(row, text=f"{self.money(spent)} / {self.money(budget['amount'])}   •   {pct:.1f}%",
                     bg=CARD_ALT, fg=DANGER if pct > 100 else MUTED,
                     font=("Segoe UI", 9)).pack(side="right", padx=14)
            ttk.Progressbar(self.budget_list, maximum=100, value=min(pct, 100)).pack(fill="x", pady=(0, 5))
            if pct > 100:
                tk.Label(self.budget_list, text=f"⚠ {budget['category']} budget exceeded",
                         bg=CARD, fg=DANGER, font=("Segoe UI", 9)).pack(anchor="w", padx=8)

    def show_analytics(self):
        self.clear_content()
        top = tk.Frame(self.content, bg=BG)
        top.pack(fill="x", pady=(0, 10))
        self.analytics_month = tk.StringVar(value=date.today().strftime("%Y-%m"))
        tk.Label(top, text="Month (YYYY-MM)", bg=BG, fg=MUTED).pack(side="left")
        tk.Entry(top, textvariable=self.analytics_month, bg=CARD, fg=WHITE,
                 insertbackground=WHITE, relief="flat", width=12).pack(side="left", padx=10, ipady=6)
        self.action_button(top, "Refresh charts", self.refresh_analytics).pack(side="left")
        self.chart_area = tk.Frame(self.content, bg=BG)
        self.chart_area.pack(fill="both", expand=True)
        self.refresh_analytics()

    def refresh_analytics(self):
        if not hasattr(self, "chart_area"):
            return
        for widget in self.chart_area.winfo_children():
            widget.destroy()
        try:
            datetime.strptime(self.analytics_month.get() + "-01", "%Y-%m-%d")
        except ValueError:
            messagebox.showerror("Invalid month", "Use YYYY-MM, for example 2026-11.")
            return
        if not MATPLOTLIB_AVAILABLE:
            tk.Label(self.chart_area, text="Charts require Matplotlib.\nRun: pip install matplotlib",
                     bg=BG, fg=WHITE, font=("Segoe UI", 14)).pack(pady=50)
            return
        month = self.analytics_month.get()
        rows = self.db.connection.execute(
            """SELECT category,SUM(amount) AS total FROM expenses
               WHERE substr(transaction_date,1,7)=? GROUP BY category""", (month,)).fetchall()
        categories = [r["category"] for r in rows]
        amounts = [r["total"] for r in rows]
        monthly = self.db.connection.execute("""
            SELECT substr(transaction_date,1,7) AS month,SUM(amount) AS total
            FROM expenses GROUP BY month ORDER BY month DESC LIMIT 6
        """).fetchall()
        monthly = list(reversed(monthly))
        fig = Figure(figsize=(11, 6), dpi=100, facecolor=BG)
        ax1 = fig.add_subplot(221)
        ax2 = fig.add_subplot(222)
        ax3 = fig.add_subplot(212)
        for ax in (ax1, ax2, ax3):
            ax.set_facecolor(CARD)
            ax.tick_params(colors=MUTED, labelsize=8)
            for spine in ax.spines.values():
                spine.set_color(BORDER)
        if amounts:
            ax1.pie(amounts, labels=categories, autopct="%1.0f%%", textprops={"color": WHITE, "fontsize": 8})
        else:
            ax1.text(.5, .5, "No expenses this month", color=MUTED, ha="center")
        ax1.set_title("Category split", color=WHITE, fontsize=11)
        ax2.bar(categories, amounts, color=ACCENT)
        ax2.set_title("Category spending", color=WHITE, fontsize=11)
        ax2.tick_params(axis="x", rotation=25)
        ax3.plot([r["month"] for r in monthly], [r["total"] for r in monthly],
                 marker="o", color=SUCCESS, linewidth=2)
        ax3.set_title("Monthly spending trend", color=WHITE, fontsize=11)
        ax3.grid(alpha=.15)
        fig.tight_layout(pad=2)
        canvas = FigureCanvasTkAgg(fig, master=self.chart_area)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

    def export_csv(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")], initialfile="spendwise_transactions.csv")
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8") as file:
                writer = csv.writer(file)
                writer.writerow(["Type", "Date", "Name / Source", "Category", "Amount", "Description"])
                for row in self.db.all_expenses():
                    writer.writerow(["Expense", row["transaction_date"], row["name"],
                                     row["category"], row["amount"], row["description"]])
                for row in self.db.all_income():
                    writer.writerow(["Income", row["transaction_date"], row["source"],
                                     "Income", row["amount"], row["description"]])
            messagebox.showinfo("Export complete", f"Transactions exported to:\n{path}")
        except OSError as error:
            messagebox.showerror("Export failed", str(error))

    def close_app(self):
        self.db.close()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = SpendWiseApp(root)
    root.mainloop()
