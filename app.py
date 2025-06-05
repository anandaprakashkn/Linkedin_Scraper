from flask import Flask, request, jsonify, render_template , send_file
import os
import asyncio
from test_headless import run_scraper  # this should be your async function in test.py

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/download')
def download_file():
    file_path = 'leads_with_company_details.csv'  # 👈 Match this
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    else:
        return "No file available to download.", 404

@app.route('/start-scraping', methods=['POST'])
def start_scraping():
    data = request.get_json()
    session_cookie = data.get("sessionCookie")
    list_url = data.get("listUrl")

    if not session_cookie or not list_url:
        return jsonify({"message": "Missing input."}), 400

    # Run the async scraper using asyncio
    try:
        asyncio.run(run_scraper(session_cookie, list_url))
        return jsonify({"message": "✅ Scraping completed successfully!"})
    except Exception as e:
        return jsonify({"message": f"❌ Scraping failed: {str(e)}"}), 500

if __name__ == "__main__":
    app.run(debug=True)
