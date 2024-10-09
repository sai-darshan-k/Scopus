from flask import Flask, request, jsonify, render_template, send_file
import requests
import json
import logging
import pandas as pd
from io import BytesIO

# Load API key from configuration file
with open('config.json', 'r') as f:
    config = json.load(f)

API_KEY = config['API_KEY']

app = Flask(__name__)

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def make_request(url, params=None, headers=None):
    """Send a request to the specified URL with the given headers and params."""
    response = requests.get(url, params=params, headers=headers)
    response.raise_for_status()
    return response

def extract_scopus_data(title=None, author_name=None):
    """Extract Scopus data based on paper title and/or author name."""
    try:
        headers = {"X-ELS-APIKey": API_KEY, "Accept": "application/json"}
        query = []

        # Construct the query based on user inputs
        if title:
            query.append(f"TITLE({title})")
        if author_name:
            query.append(f"AUTHLASTNAME({author_name})")

        # Join query parts using AND to combine Title and Author searches
        combined_query = " AND ".join(query)

        # Get publications using the combined query
        publications_url = "http://api.elsevier.com/content/search/scopus"
        params = {
            "query": combined_query,
            "count": "25",  # Adjust count as necessary
            "sort": "pubyear",
        }
        resp = make_request(publications_url, params=params, headers=headers)
        results = resp.json().get("search-results", {}).get("entry", [])

        if not results:
            logging.warning(f"No results found for query: {combined_query}")
            return []

        papers = []
        for result in results:
            pub_year = int(result.get("prism:coverDate", "0")[:4]) if "prism:coverDate" in result else None
            if pub_year in range(2000, 2025):
                paper_title = result.get("dc:title", "Unknown Title")
                citations = int(result.get('citedby-count', 0))
                authors = result.get("dc:creator", "Unknown")
                papers.append({
                    "Paper Title": paper_title,
                    "Citations": citations,
                    "Year": pub_year,
                    "Authors": authors
                })

        return papers

    except requests.exceptions.RequestException as e:
        logging.error(f"An error occurred: {e}")
        return []

@app.route('/', methods=['GET'])
def scopus():
    return render_template('scopus.html')

@app.route('/get_data', methods=['GET'])
def get_data():
    title = request.args.get('title')
    author_name = request.args.get('author_name') or None  # Author name is optional
    
    scopus_data = extract_scopus_data(title=title, author_name=author_name)
    return jsonify(scopus_data)

@app.route('/download_data', methods=['GET'])
def download_data():
    title = request.args.get('title')
    author_name = request.args.get('author_name') or None  # Author name is optional

    scopus_data = extract_scopus_data(title=title, author_name=author_name)

    # Create a DataFrame
    df = pd.DataFrame(scopus_data)

    # Save to a BytesIO buffer
    output = BytesIO()
    df.to_excel(output, index=False, engine='openpyxl')
    output.seek(0)

    # Send the Excel file to the client
    return send_file(output, as_attachment=True, download_name='scopus_data.xlsx', mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

if __name__ == '__main__':
    app.run(debug=True, port=5001)
