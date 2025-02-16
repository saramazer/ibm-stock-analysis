import os
import pandas as pd
import io
import writer as wf
import writer.ai
import datetime
import plotly.graph_objects as go
import plotly.express as px
from dotenv import load_dotenv

load_dotenv()
writer.ai.init(os.getenv("WRITER_API_KEY"))

# Refresh the window
def _refresh_window(state):
    state["show_line_chart"] = False
    state["show_msg"] = False
    state["message"] = "Writer AI insights will be generated here"
    state["filtered_data"] = None  # Initialize filtered_data as None
    state["stock_data"] = None     # Initialize stock_data as None
    state["show_dataframe"] = False  # Hide dataframe initially
    state["line_chart"] = None     # Initialize line_chart as None
    state["file_uploaded"] = False  # Explicitly set file_uploaded to False

def generate_stock_analysis(state):
    try:
        if state["stock_data"] is None:
            raise ValueError("No stock data available for analysis.")
        complete_stock_data = state["stock_data"].to_string(index=False)

        try:
            prompt = f"""  
            Variables: 
            {complete_stock_data}
            
            Prompt:
            You will be acting as a stock market analyst. Review the provided IBM stock data and provide a concise analysis.
            Keep your total response under 250 words.

            <stock_data>
            {complete_stock_data}
            </stock_data>

            Analyze the following (keep each section brief) and give each section a title of trends, analysis, and recommendation:

            1. Provide a title in bold and put content inside <trends> tags:
            - Notable price movements (1 sentence)
            - Volume patterns (1 sentence)

            2. Provide a title in bold and put content inside <analysis> tags:
            - Recent performance summary (2 sentences)
            - Key observations (1-2 sentences)

            3. REQUIRED - Provide a title in bold and put content inside <recommendation> tags:
            - Provide ONE clear buy/hold/sell recommendation with brief rationale
            - Must start with "Recommendation: BUY/HOLD/SELL" followed by brief explanation

            4. Use the following delimiter \n to separate different sections.

            Base your analysis solely on the provided stock data. If there is insufficient information,
            state this limitation in your response.

            """

        except Exception as e:
            raise ValueError("Failed to format prompt for AI model.")
        
        submission = writer.ai.complete(
            prompt,
            config={
                "model": "palmyra-fin-32k", 
                "temperature": 0.7, 
                "max_tokens": 250
            },
        )
        
        state["analysis"] = submission.strip()
        return submission

    except Exception as e:
        error_message = f"Error generating stock analysis: {str(e)}"
        print(error_message)
        state["analysis"] = error_message

# generic message handler    
def _update_message(state, message=""):
    state["message"] = message

def handle_csv_upload(state, payload):
    try:
        uploaded_file = payload[0]
        name = uploaded_file.get("name")
        file_data = uploaded_file.get("data")
        file_like_object = io.BytesIO(file_data)
        
        # Read CSV without using the first column as an index
        df = pd.read_csv(file_like_object, index_col=None)
        
        # Convert "timestamp" to datetime format
        df["timestamp"] = pd.to_datetime(df["timestamp"], format="%Y-%m-%d")
        
        # Sort by "timestamp" in descending order (most recent first)
        df = df.sort_values(by="timestamp", ascending=False).reset_index(drop=True)
        
        # Store the processed DataFrame in state
        state["main_df_subset"] = df
        state["stock_data"] = df  # Keep as datetime for sorting purposes
        state["file_uploaded"] = True
        state["show_msg"] = True
        state["upload_msg"] = f"File '{name}' uploaded and processed successfully!\n\nGive us a minute to analyze...BRB!"
        
        # Before analysis message
        print(state["upload_msg"])
        
        # Trigger analysis after upload
        generate_stock_analysis(state)
        
        # After analysis message
        state["upload_msg"] = "Writer has completed analysis."
        print(state["upload_msg"])

    except Exception as e:
        state["show_msg"] = True
        state["file_uploaded"] = False
        state["upload_msg"] = f"Error processing file: {str(e)}"

def update_line_chart(state):
    try:
        if state["filtered_data"] is None or state["filtered_data"].empty:
            return
        
        # Create a clean copy of the data for plotting
        plot_data = state["filtered_data"].copy()
        
        # Convert close prices from string back to float
        plot_data["Close"] = plot_data["Close"].astype(float)
        
        # Convert dates and sort chronologically
        plot_data["Date"] = pd.to_datetime(plot_data["Date"])
        plot_data = plot_data.sort_values(by="Date", ascending=True)
        
        state["show_line_chart"] = True
        
        # Create the line chart with only the necessary data
        fig = px.line(
            plot_data, 
            x="Date",
            y="Close",
            title="Stock Prices Over Time",
            labels={"Date": "Date", "Close": "Close Price"}
        )
        
        # Update layout for better visualization
        fig.update_layout(
            yaxis=dict(
                autorange=True,
                title="Closing Price ($)",
                tickformat=",.2f"
            ),
            xaxis=dict(
                title="Date",
                tickangle=-45
            )
        )

        state["line_chart"] = fig
    except Exception as e:
        print(f"Error updating line chart: {str(e)}")

# Function to display all data
def display_all_data(state):
    try:
        if not state["file_uploaded"] or state["stock_data"] is None or state["stock_data"].empty:
            state["show_dataframe"] = False
            state["filtered_data"] = None
            return

        # Create a copy of stock_data for display purposes
        df = state["stock_data"].copy()

        # Sort by "timestamp" (datetime) in descending order before formatting for display
        df = df.sort_values(by="timestamp", ascending=False).reset_index(drop=True)

        # Format numeric columns to two decimal places
        numeric_columns = ["open", "high", "low", "close", "volume"]
        for col in numeric_columns:
            df[col] = df[col].apply(lambda x: f"{float(x):.2f}")

        # Add a "Date" column formatted as MM/DD/YYYY for display purposes
        df["Date"] = df["timestamp"].dt.strftime("%m/%d/%Y")

        # Drop the original "timestamp" column if not needed for display
        df = df.drop(columns=["timestamp"])

        # Move the "Date" column to the first position
        columns_order = ["Date"] + [col for col in df.columns if col != "Date"]
        df = df[columns_order]

        # Capitalize all column names
        state["filtered_data"] = df.reset_index(drop=True)
        state["filtered_data"].columns = state["filtered_data"].columns.str.capitalize()

        # Update filter mode and refresh line chart
        state["filter_mode"] = "all"
        update_line_chart(state)
    except Exception as e:
        print(f"Error displaying all data: {str(e)}")

# Function to display the last 7 days of data
def display_last_seven_days(state):
    try:
        if not state["file_uploaded"] or state["stock_data"] is None or state["stock_data"].empty:
            state["show_dataframe"] = False
            state["filtered_data"] = None
            return
        
        # Get the last 7 records instead of filtering by date
        filtered_data = state["stock_data"].copy().tail(7)  # Select the last 7 rows
        
        if filtered_data.empty:
            print("No data available for the last 7 records.")
            return
        
        # Sort by "timestamp" (datetime) in descending order before formatting for display
        filtered_data = filtered_data.sort_values(by="timestamp", ascending=False).reset_index(drop=True)
        
        # Format numeric columns to two decimal places
        numeric_columns = ["open", "high", "low", "close", "volume"]
        for col in numeric_columns:
            filtered_data[col] = filtered_data[col].apply(lambda x: f"{float(x):.2f}")
        
        # Add a "Date" column formatted as MM/DD/YYYY for display purposes
        filtered_data["Date"] = filtered_data["timestamp"].dt.strftime("%m/%d/%Y")
        
        # Drop the original "timestamp" column if not needed for display
        filtered_data = filtered_data.drop(columns=["timestamp"])

        # Move the "Date" column to the first position
        columns_order = ["Date"] + [col for col in filtered_data.columns if col != "Date"]
        filtered_data = filtered_data[columns_order]

        # Capitalize all column names
        state["filtered_data"] = filtered_data.reset_index(drop=True)
        state["filtered_data"].columns = state["filtered_data"].columns.str.capitalize()

        # Update filter mode and refresh line chart
        state["filter_mode"] = "last_seven_records"
        update_line_chart(state)
    except Exception as e:
        print(f"Error displaying last 7 entries: {str(e)}")
        
def handle_all_button_click(state):
    state["show_dataframe"] = True
    display_all_data(state)

def handle_last_seven_days_button_click(state):
    state["show_dataframe"] = True
    display_last_seven_days(state)

initial_state = wf.init_state(
    {
        "my_app": {"title": "IBM STOCK ANALYZER"},
        "df": None,
        "main_df": None,
        "df_preview": None,
        "main_df_subset": None,
        "stock_data": None,
        "line_chart": None,
        "file_uploaded": False,
        "symbol": "IBM",
        "show_dataframe": False,    # Start with dataframe hidden
        "filtered_data": None,      # Initialize as None
        "filter_mode": "all",
        "upload_msg": "Upload a CSV file to begin analysis.",
        "analysis": "Writer will analyze and add response here.",
        "show_line_chart": False,
        "show_msg": False,
        "msg": "",
    }
)

# Initialize the state
_refresh_window(initial_state)