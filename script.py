import requests
import re
from bs4 import BeautifulSoup
import subprocess
import openai
import csv
import time  


openai.api_key = 'YOUR_API_KEY'


MAX_TOKENS = 4000  # Set the token limit for OpenAI API (adjust based on model)

def get_cik_by_ticker(ticker):
    url = "https://www.sec.gov/files/company_tickers.json"
    
    headers = {
        "User-Agent": "MyApp/1.0 (contact@example.com)"  # Replace with your actual email
    }

    # Fetch the JSON data from SEC
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        
        # Convert JSON object into a list
        companies = list(data.values())

        # Search for the ticker
        for company in companies:
            if company["ticker"].upper() == ticker.upper():
                cik = str(company["cik_str"]).zfill(10)  # Ensure CIK is 10 digits
                return cik

        return None  # If ticker is not found
    else:
        print(f"Error: {response.status_code}, {response.text}")
        return None
    


def get_recent_10k_filings(cik, max_filings=4):
    url = f"https://data.sec.gov/submissions/CIK{cik}.json"

    headers = {
        "User-Agent": "MyApp/1.0 (contact@example.com)"  # Replace with your actual email
    }

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        data = response.json()
        
        recent_filings = data.get("filings", {}).get("recent", {})

        ten_k_filings = [
            {
                "accessionNumber": accession,
                "filingDate": date,
                "form": form,
                "indexUrl": f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession.replace('-', '')}"
            }
            for accession, date, form in zip(
                recent_filings.get("accessionNumber", []),
                recent_filings.get("filingDate", []),
                recent_filings.get("form", []))
            if form == "10-K"
        ]

        return ten_k_filings[:max_filings]

    else:
        print(f"Error: {response.status_code}, {response.text}")
        return None

def get_first_matching_file(index_url, ticker):
    headers = {
        "User-Agent": "MyApp/1.0 (contact@example.com)"  # Replace with your actual email
    }

    response = requests.get(index_url, headers=headers)

    if response.status_code == 200:
        soup = BeautifulSoup(response.text, "html.parser")
        files = [link.get("href") for link in soup.find_all("a") if link.get("href")]

        # Find the first file that starts with the ticker (case-insensitive)
        ticker = ticker.lower()
        for file in files:
            if file.lower().__contains__(ticker):
                return "https://www.sec.gov" + file  # Return the full URL to the file

    print(f"No matching file found in {index_url}")
    return None

def extract_text(file_url):
    headers = {
        "User-Agent": "MyApp/1.0 (contact@example.com)"  # Replace with your actual email
    }

    response = requests.get(file_url, headers=headers)

    if response.status_code == 200:
        text = BeautifulSoup(response.text, "html.parser").get_text()

        # Clean the text: remove excessive whitespace and non-word characters
        return text[500:-200]
    else:
        print(f"Error retrieving file: {file_url} (Status Code: {response.status_code})")
        return None

def chunk_text(text, max_tokens=MAX_TOKENS):
    """Splits the text into chunks that fit within the token limit."""
    words = text.split()  # Split text by spaces
    chunks = []
    current_chunk = []
    current_chunk_length = 0

    for word in words:
        # Check the current chunk length (in terms of tokens)
        if current_chunk_length + len(word) + 1 > max_tokens:
            chunks.append(" ".join(current_chunk))  # Add the current chunk to the list
            current_chunk = [word]  # Start a new chunk
            current_chunk_length = len(word)
        else:
            current_chunk.append(word)  # Add word to the current chunk
            current_chunk_length += len(word) + 1  # Account for spaces

    if current_chunk:
        chunks.append(" ".join(current_chunk))  # Add the last chunk

    return chunks


def save_products_to_csv(products):
    # Split the products into rows (assuming 'products' is a string with the format: Company Name | Stock Name | Filing Time | New Product | Product Description'')
    products_list = products.split('\n')

    # Open CSV file in write mode
    with open('new_products.csv', 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile, delimiter='|')
        writer.writerow(['Company Name', 'Stock Name','Filing Time','New Product', 'Product Description'])  # Write the header

        # Write each product to the CSV file
        for product in products_list:
            product_details = product.split('|')
            if len(product_details) == 3:  # Ensure the product is well-formed
                writer.writerow([detail.strip() for detail in product_details])


def handle_rate_limit_error():
    """Handles rate limit errors by introducing a delay."""
    print("Rate limit exceeded, retrying in 30 seconds...")
    time.sleep(30)  # Wait for 60 seconds before retrying


# Example usage
dow_list =['MMM', 'AXP', 'AAPL', 'AMGN','BA', 'CAT', 'CVX', 'CSCO', 'KO', 'DOW', 'GS', 'HD', 'HON', 'IBM', 'INTC', 'JNJ', 'JPM', 'MCD', 'MRK', 'MSFT', 'NKE', 'PG', 'RXT','CRM', 'SBUX', 'TRV', 'UNH',  'VZ', 'V', 'WBA']
for ticker in dow_list:
    cik = get_cik_by_ticker(ticker)

    if cik:
        ten_k_filings = get_recent_10k_filings(cik, max_filings=4)

        if ten_k_filings:
            print(f"Most Recent 4 10-K Filings for {ticker}:")

            for filing in ten_k_filings:
                print(f"\nFiling Date: {filing['filingDate']}")
                print(f"Index URL: {filing['indexUrl']}")

                file_link = get_first_matching_file(filing['indexUrl'], ticker)

                if file_link:
                    print(f"First Matching File: {file_link}")

                    # Extract and process the full text in chunks
                    fulltext = extract_text(file_link)
                    if fulltext:
                        chunks = chunk_text(fulltext)

                        all_products = []

                        for chunk in chunks:
                            try:
                                completion = openai.ChatCompletion.create(
                                    model="gpt-4",
                                    messages=[{
                                        "role": "user",
                                        "content": f"Extract the new products from the following text and create a list. If there a no new products on the text, then ignore it. The output should include the following format: Company Name | Stock Name | Filing Time | New Product | Product Description {chunk}"
                                    }]
                                )

                                products = completion.choices[0].message['content']
                                all_products.append(products)

                            except openai.error.RateLimitError:
                                handle_rate_limit_error()  # Handle rate limit error by retrying
                                continue  # Continue with the next chunk after the delay

                        # Combine results from all chunks
                        combined_products = "\n".join(all_products)
                        print(combined_products)
                        save_products_to_csv(combined_products)
                    else:
                        print("Could not extract text from the file.")
                else:
                    print("No matching file found.")

        else:
            print(f"No 10-K filings found for {ticker}")
    else:
        print(f"No CIK found for ticker {ticker}")
