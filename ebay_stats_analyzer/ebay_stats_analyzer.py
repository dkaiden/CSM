# CIS 117 - Final Project
# eBay Stats Analyzer with GUI
# David Deng
# May 9, 2025

import requests
import sqlite3
import json
import os
from pathlib import Path
from datetime import datetime, timedelta
from tkinter import Tk, Label, Entry, Button, Text, Frame, END, W, WORD, messagebox, simpledialog
from tkinter.font import Font
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# --- Configuration ---
CONFIG_FILE = "ebay_config.json"
TOKEN_EXPIRY_HOURS = 2
# https://developer.ebay.com/my/api_test_tool?index=0

# --- Database Setup ---
def init_db():
    """Initialize the SQLite database for storing eBay item stats."""
    conn = sqlite3.connect("ebay_stats.db")
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS searches (
            id INTEGER PRIMARY KEY,
            search_term TEXT,
            timestamp DATETIME,
            total_listings INTEGER,
            avg_price REAL,
            min_price REAL,
            max_price REAL
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS top_prices (
            search_id INTEGER,
            price REAL,
            is_auction INTEGER,
            FOREIGN KEY (search_id) REFERENCES searches(id)
        )
    """)
    
    conn.commit()
    conn.close()

# --- Token Management ---
def save_token(token):
    """Save token to config file with expiry time"""
    config = {
        "oauth_token": token,
        "token_expiry": (datetime.now() + timedelta(hours=TOKEN_EXPIRY_HOURS)).isoformat()
    }
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f)
        if hasattr(os, 'chmod'):
            os.chmod(CONFIG_FILE, 0o600)
    except Exception as e:
        messagebox.showerror("Config Error", f"Failed to save token: {str(e)}")

def load_token():
    """Load token from config file if valid"""
    try:
        if not Path(CONFIG_FILE).exists():
            return None
            
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
            
        expiry = datetime.fromisoformat(config["token_expiry"])
        if expiry > datetime.now():
            return config["oauth_token"]
        return None
    except Exception:
        return None

def get_ebay_token():
    """Get token from storage or prompt user"""
    token = load_token()
    if token:
        return token
        
    token = simpledialog.askstring("eBay OAuth Token", 
                                 "Enter eBay OAuth token (valid 2 hours):", 
                                 parent=window)
    if token:
        save_token(token)
        return token
        
    messagebox.showerror("Error", "Token is required to use eBay API")
    return None

# --- eBay API Functions ---
def get_ebay_stats(search_query):
    """Fetch real data from eBay's Browse API"""
    try:
        token = get_ebay_token()
        if not token:
            return None
            
        endpoint = "https://api.ebay.com/buy/browse/v1/item_summary/search"
        headers = {
            "Authorization": f"Bearer {token}",
            "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"
        }
        
        params = {
            "q": search_query,
            "limit": 200,
            "filter": "conditions:{NEW|USED}"
        }
        
        response = requests.get(endpoint, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        
        if 'itemSummaries' not in data:
            messagebox.showerror("API Error", "Unexpected API response format")
            return None

        items = data.get('itemSummaries', [])
        
        if not items:
            messagebox.showinfo("No Results", "No listings found for this search term")
            return None

        buy_now_prices = []
        auction_items = []
        
        for item in items:
            price_data = item.get('price', {})
            try:
                price = float(price_data.get('value', 0))
            except (ValueError, AttributeError):
                continue  # Skip items with invalid prices
            
            buying_options = item.get('buyingOptions', [])
            
            if 'FIXED_PRICE' in buying_options:
                buy_now_prices.append(price)
            elif 'AUCTION' in buying_options:
                end_time = item.get('itemEndDate', '')
                if end_time:
                    try:
                        end_datetime = datetime.strptime(end_time, "%Y-%m-%dT%H:%M:%S.%fZ")
                        auction_items.append({
                            'price': price,
                            'end_time': end_time,
                            'end_datetime': end_datetime
                        })
                    except ValueError:
                        continue  # Skip items with invalid time format

        if not (buy_now_prices or auction_items):
            messagebox.showinfo("No Valid Prices", "Found listings but no usable price data")
            return None

        # Sort auctions by end time (soonest first) and take top 5
        auction_items.sort(key=lambda x: x['end_datetime'])
        top_auctions = auction_items[:5]

        all_prices = buy_now_prices + [item['price'] for item in auction_items]
        
        stats = {
            'total_listings': data.get('total', len(items)),
            'avg_price': sum(all_prices)/len(all_prices) if all_prices else 0,
            'min_price': min(all_prices) if all_prices else 0,
            'max_price': max(all_prices) if all_prices else 0,
            'all_prices': buy_now_prices + [item['price'] for item in auction_items],  # Add this line
            'top_buy_now': sorted(buy_now_prices)[:5] if buy_now_prices else [],
            'top_auction': [item['price'] for item in top_auctions],
            'auction_end_times': [item['end_time'] for item in top_auctions]
        }
        
        return stats
        
    except Exception as e:
        messagebox.showerror("API Error", f"eBay API request failed:\n{str(e)}")
        return None

# --- GUI Functions ---
def search_ebay():
    """Handle the search button click event."""
    query = search_entry.get().strip()
    
    if not query:
        messagebox.showerror("Error", "Please enter a search term")
        return
    
    try:
        output.delete(1.0, END)
        output.insert(END, "Searching eBay... Please wait...\n")
        output.update()
        
        stats = get_ebay_stats(query)
        
        if not stats:
            return
            
        output.delete(1.0, END)
        output.insert(END, f"Results for '{query}':\n\n")
        output.insert(END, f"Total Listings: {stats['total_listings']}\n")
        output.insert(END, f"Average Price: ${stats['avg_price']:.2f}\n")
        output.insert(END, f"Minimum Price: ${stats['min_price']:.2f}\n")
        output.insert(END, f"Maximum Price: ${stats['max_price']:.2f}\n\n")
        
        if stats['top_buy_now']:
            output.insert(END, "Lowest 5 Buy It Now Prices:\n")
            for price in stats['top_buy_now']:
                output.insert(END, f"  ${price:.2f}\n")
        else:
            output.insert(END, "No Buy It Now listings found\n")
            
        output.insert(END, "\n")
        
        if stats['top_auction']:
            output.insert(END, "5 Ending Soonest Auctions:\n")
            for i, price in enumerate(stats['top_auction']):
                try:
                    end_time = datetime.strptime(stats['auction_end_times'][i], "%Y-%m-%dT%H:%M:%S.%fZ")
                    time_left = end_time - datetime.now()
                    hours = int(time_left.total_seconds() // 3600)
                    mins = int((time_left.total_seconds() % 3600) // 60)
                    time_str = f"{hours}h {mins}m" if hours else f"{mins}m"
                    output.insert(END, f"  ${price:.2f} (Ends in {time_str})\n")
                except (ValueError, IndexError):
                    output.insert(END, f"  ${price:.2f} (End time unavailable)\n")
        else:
            output.insert(END, "No auction listings found\n")
        
        status_label.config(text=f"Search complete. Found {stats['total_listings']} listings.")
        save_to_db(query, stats)
        update_chart(stats)
        
    except Exception as e:
        messagebox.showerror("Error", f"Failed to process search:\n{str(e)}")
        output.delete(1.0, END)
        status_label.config(text="Ready")

def save_to_db(query, stats):
    """Save search results to the database."""
    conn = sqlite3.connect("ebay_stats.db")
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO searches (search_term, timestamp, total_listings, avg_price, min_price, max_price)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        query,
        datetime.now(),
        stats["total_listings"],
        stats["avg_price"],
        stats["min_price"],
        stats["max_price"],
    ))
    
    search_id = cursor.lastrowid
    
    for price in stats["top_buy_now"]:
        cursor.execute("""
            INSERT INTO top_prices (search_id, price, is_auction)
            VALUES (?, ?, ?)
        """, (search_id, price, 0))
    
    for price in stats["top_auction"]:
        cursor.execute("""
            INSERT INTO top_prices (search_id, price, is_auction)
            VALUES (?, ?, ?)
        """, (search_id, price, 1))
    
    conn.commit()
    conn.close()

def update_chart(stats):
    """Update the price distribution chart."""
    for widget in chart_frame.winfo_children():
        widget.destroy()
    
    fig, ax = plt.subplots(figsize=(5, 3), dpi=100)
    # all_prices = stats["top_buy_now"] + stats["top_auction"]
    all_prices = stats.get("all_prices", [])  # Ensure this key exists in stats
    
    if all_prices:
        ax.hist(all_prices, bins=8, edgecolor='black', alpha=0.7)
        ax.set_title('Price Distribution (All Listings)')  # More descriptive
        ax.set_xlabel('Price ($)')
        ax.set_ylabel('Frequency')
        
        canvas = FigureCanvasTkAgg(fig, master=chart_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(side="top", fill="both", expand=True)
    else:
        Label(chart_frame, 
              text="No price data available for chart", 
              bg="#f0f0f0", 
              font=("Arial", 10)).pack()

# --- Main GUI Setup ---
init_db()

window = Tk()
window.tk_setPalette(background='#f0f0f0', foreground='black',
                    activeBackground='#4a6fa5', activeForeground='white')
window.title("eBay Stats Analyzer")
window.geometry("800x700")
window.configure(bg="#f0f0f0")

def on_closing():
    if messagebox.askokcancel("Quit", "Do you want to close the application?"):
        window.destroy()
        window.quit()

window.protocol("WM_DELETE_WINDOW", on_closing)

# Custom fonts
title_font = Font(family="Helvetica", size=14, weight="bold")
label_font = Font(family="Arial", size=10)
button_font = Font(family="Arial", size=10, weight="bold")

# Header frame
header_frame = Frame(window, bg="#4a6fa5", padx=10, pady=10)
header_frame.grid(row=0, column=0, columnspan=2, sticky="ew")

Label(header_frame, 
      text="eBay Stats Analyzer", 
      font=title_font, 
      bg="#4a6fa5", 
      fg="white").pack()

Label(header_frame, 
      text="Analyze pricing trends for eBay items", 
      font=label_font, 
      bg="#4a6fa5", 
      fg="#e0e0e0").pack()

# Input frame
input_frame = Frame(window, bg="#f0f0f0", padx=10, pady=10)
input_frame.grid(row=1, column=0, sticky="w")

Label(input_frame, 
      text="Enter search term (e.g., 'ThinkPad T14s i7 16GB'):", 
      font=label_font, 
      bg="#f0f0f0").grid(row=0, column=0, sticky="w")

search_entry = Entry(input_frame, width=50, font=label_font, bd=2, relief="groove")
search_entry.grid(row=1, column=0, pady=5)

search_button = Button(
    input_frame,
    text="SEARCH",
    command=search_ebay,
    bg="#4a6fa5",
    fg="black",
    activebackground="#3a5a8c",
    activeforeground="black",
    font=button_font,
    relief='raised',
    bd=3,
    padx=15,
    pady=3
)
search_button.grid(row=1, column=1, padx=10)

# Output frame
output_frame = Frame(window, bg="#f0f0f0", padx=10, pady=10)
output_frame.grid(row=2, column=0, sticky="nsew")

Label(output_frame, 
      text="Search Results:", 
      font=label_font, 
      bg="#f0f0f0").grid(row=0, column=0, sticky="w")

output = Text(output_frame, 
             width=70, 
             height=12, 
             wrap=WORD, 
             font=label_font,
             bd=2, 
             relief="groove",
             bg="white",
             padx=5,
             pady=5)
output.grid(row=1, column=0)

# Chart frame
chart_frame = Frame(window, bg="#f0f0f0", padx=10, pady=10)
chart_frame.grid(row=3, column=0, sticky="nsew")

# Status bar
status_frame = Frame(window, bg="#e0e0e0", height=25)
status_frame.grid(row=4, column=0, sticky="ew", padx=0, pady=0)

status_label = Label(status_frame, 
                     text="Ready", 
                     bg="#e0e0e0", 
                     fg="#333333",
                     font=("Arial", 8))
status_label.pack(side="left", padx=10)

# Configure grid weights
window.grid_columnconfigure(0, weight=1)
window.grid_rowconfigure(2, weight=1)
window.grid_rowconfigure(3, weight=1)

# Start the application
window.mainloop()